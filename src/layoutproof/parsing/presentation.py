"""Rich, rule-oriented in-memory model of a PowerPoint presentation.

The model normalizes python-pptx high-level access together with low-level
DrawingML details (alt text, decorative flag, auto-fit, hidden state) that
python-pptx does not expose directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.enum.dml import MSO_COLOR_TYPE
from pptx.enum.shapes import MSO_SHAPE_TYPE

from .geometry import Rect
from .package import PackageError, SafePackage


# ---------------------------------------------------------------------------
# Text model
# ---------------------------------------------------------------------------
@dataclass
class TextRun:
    text: str
    font_name: str | None = None
    font_size_pt: float | None = None
    bold: bool | None = None
    color_rgb: str | None = None
    color_theme: str | None = None


@dataclass
class Paragraph:
    runs: list[TextRun] = field(default_factory=list)
    level: int = 0
    alignment: str | None = None

    @property
    def text(self) -> str:
        return "".join(r.text for r in self.runs)


# ---------------------------------------------------------------------------
# Shape model
# ---------------------------------------------------------------------------
@dataclass
class ShapeModel:
    id: str
    name: str
    shape_type: str
    rect: Rect | None
    z_order: int
    is_placeholder: bool = False
    placeholder_type: str | None = None
    is_visible: bool = True
    is_decorative: bool = False
    is_background: bool = False
    has_alt_text: bool = False
    alt_text: str = ""
    paragraphs: list[Paragraph] = field(default_factory=list)
    is_picture: bool = False
    image_part: str | None = None
    has_table: bool = False
    has_chart: bool = False
    rotation: float = 0.0
    autofit: str | None = None          # normAutofit | spAutoFit | noAutofit | None
    wrap: str | None = None
    parent_id: str | None = None

    @property
    def text(self) -> str:
        return "\n".join(p.text for p in self.paragraphs if p.text).strip()

    @property
    def explicit_font_sizes(self) -> list[float]:
        sizes = [r.font_size_pt for p in self.paragraphs for r in p.runs if r.font_size_pt]
        return [float(s) for s in sizes if s]  # type: ignore[arg-type]


@dataclass
class Relationship:
    rId: str
    rel_type: str
    target: str
    is_external: bool
    target_exists: bool
    action: str | None = None


@dataclass
class SlideModel:
    index: int
    number: int
    part_name: str
    shapes: list[ShapeModel] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)
    background_picture: bool = False

    @property
    def visible_shapes(self) -> list[ShapeModel]:
        return [s for s in self.shapes if s.is_visible]


@dataclass
class PresentationModel:
    path: str
    width: int
    height: int
    slides: list[SlideModel] = field(default_factory=list)
    anomalies: list[str] = field(default_factory=list)

    @property
    def bounds(self) -> Rect:
        return Rect(0, 0, self.width, self.height)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _local_name(tag: str) -> str:
    return etree.QName(tag).localname if isinstance(tag, str) and "}" in tag else tag


def _has_decorative_flag(el: etree._Element) -> bool:
    for node in el.iter():
        if _local_name(node.tag) == "decorative":
            return True
    return False


def _is_hidden(el: etree._Element) -> bool:
    for value in el.xpath(".//@hidden"):
        if str(value).lower() in ("1", "true"):
            return True
    return False


def _autofit_info(el: etree._Element) -> tuple[str | None, str | None]:
    body_pr = el.find(".//{http://schemas.openxmlformats.org/drawingml/2006/main}bodyPr")
    if body_pr is None:
        return None, None
    autofit = None
    for child in body_pr:
        ln = _local_name(child.tag)
        if ln in ("normAutofit", "spAutoFit", "noAutofit"):
            autofit = ln
            break
    return autofit, body_pr.get("wrap")


def _color_info(font) -> tuple[str | None, str | None]:
    try:
        color = font.color
        if color is None:
            return None, None
        if color.type == MSO_COLOR_TYPE.RGB:
            return str(color.rgb), None
        theme = getattr(color, "theme_color", None)
        return None, str(theme) if theme is not None else None
    except Exception:
        return None, None


def _build_paragraphs(text_frame) -> list[Paragraph]:
    out: list[Paragraph] = []
    for para in text_frame.paragraphs:
        runs: list[TextRun] = []
        alignment = None
        try:
            alignment = str(para.alignment) if para.alignment is not None else None
        except Exception:
            alignment = None
        for run in para.runs:
            font = run.font
            size = None
            if font.size is not None:
                size = round(float(font.size.pt), 2)
            rgb, theme = _color_info(font)
            runs.append(
                TextRun(
                    text=run.text,
                    font_name=font.name,
                    font_size_pt=size,
                    bold=font.bold,
                    color_rgb=rgb,
                    color_theme=theme,
                )
            )
        out.append(Paragraph(runs=runs, level=getattr(para, "level", 0), alignment=alignment))
    return out


def _shape_type_name(shape) -> str:
    try:
        st = shape.shape_type
        return st.name if st is not None else "UNKNOWN"
    except Exception:
        return "UNKNOWN"


def _rect(shape) -> Rect | None:
    try:
        if None in (shape.left, shape.top, shape.width, shape.height):
            return None
        return Rect(
            int(shape.left),
            int(shape.top),
            int(shape.width),
            int(shape.height),
        )
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------
class PresentationBuilder:
    def __init__(self, path: str | Path, config=None):
        self.path = Path(path)
        self.config = config
        self._z_counter = 0

    def build(self) -> PresentationModel:
        pkg = SafePackage(self.path, self.config)
        anomalies = pkg.anomalies
        try:
            prs = Presentation(str(self.path))
            width = int(prs.slide_width)
            height = int(prs.slide_height)
            model = PresentationModel(
                path=str(self.path), width=width, height=height, anomalies=anomalies
            )
            for idx, slide in enumerate(prs.slides):
                part_name = slide.part.partname
                slide_model = SlideModel(
                    index=idx, number=idx + 1, part_name=str(part_name)
                )
                slide_model.relationships = self._relationships(slide, pkg)
                slide_model.background_picture = self._has_bg_picture(slide)
                self._z_counter = 0
                self._walk_shapes(slide.shapes, slide_model, None, model)
                self._mark_backgrounds(slide_model, model)
                model.slides.append(slide_model)
            return model
        finally:
            pkg.close()

    # ------------------------------------------------------------------
    def _walk_shapes(self, shapes, slide_model: SlideModel, parent_id: str | None,
                     model: PresentationModel) -> None:
        for shape in shapes:
            try:
                sm = self._build_shape(shape, parent_id)
            except Exception:
                continue
            slide_model.shapes.append(sm)
            if sm.shape_type == "GROUP":
                try:
                    self._walk_shapes(shape.shapes, slide_model, sm.id, model)
                except Exception:
                    pass

    def _build_shape(self, shape, parent_id: str | None) -> ShapeModel:
        el = shape._element
        self._z_counter += 1
        cnv = el.find(".//{http://schemas.openxmlformats.org/presentationml/2006/main}cNvPr")
        if cnv is None:
            cnv = el.find(".//{http://schemas.openxmlformats.org/drawingml/2006/main}cNvPr")
        shape_id = str(cnv.get("id")) if cnv is not None else str(self._z_counter)
        shape_name = str(cnv.get("name")) if cnv is not None else "shape"
        alt_text = str(cnv.get("descr") or "") if cnv is not None else ""

        is_picture = _shape_type_name(shape) == "PICTURE"
        is_placeholder = False
        ph_type = None
        try:
            is_placeholder = shape.is_placeholder
            if is_placeholder:
                ph_type = shape.placeholder_format.type.name
        except Exception:
            is_placeholder = False

        paragraphs = []
        if getattr(shape, "has_text_frame", False):
            paragraphs = _build_paragraphs(shape.text_frame)

        has_table = False
        has_chart = False
        try:
            has_table = shape.has_table
        except Exception:
            has_table = False
        st_name = _shape_type_name(shape)
        if st_name == "CHART":
            has_chart = True

        image_part = None
        if is_picture:
            try:
                image_part = str(shape.image.partname)
            except Exception:
                image_part = None

        autofit, wrap = _autofit_info(el)
        decorative = _has_decorative_flag(el)
        rotation = 0.0
        try:
            rotation = float(shape.rotation or 0.0)
        except Exception:
            rotation = 0.0

        return ShapeModel(
            id=shape_id,
            name=shape_name,
            shape_type=st_name,
            rect=_rect(shape),
            z_order=self._z_counter,
            is_placeholder=is_placeholder,
            placeholder_type=ph_type,
            is_visible=not _is_hidden(el),
            is_decorative=decorative,
            has_alt_text=bool(alt_text.strip()),
            alt_text=alt_text,
            paragraphs=paragraphs,
            is_picture=is_picture,
            image_part=image_part,
            has_table=has_table,
            has_chart=has_chart,
            rotation=rotation,
            autofit=autofit,
            wrap=wrap,
            parent_id=parent_id,
        )

    def _mark_backgrounds(self, slide_model: SlideModel, model: PresentationModel) -> None:
        bounds = model.bounds
        for sm in slide_model.shapes:
            if not sm.rect or not sm.is_picture:
                continue
            # Full-bleed picture at the back is treated as a background.
            if sm.z_order <= 1 and sm.rect.fraction_outside(bounds) < 0.02:
                covers = (
                    sm.rect.width >= 0.98 * bounds.width
                    and sm.rect.height >= 0.98 * bounds.height
                )
                if covers:
                    sm.is_background = True
                    sm.is_decorative = True

    def _has_bg_picture(self, slide) -> bool:
        try:
            bg = slide._element.find(
                ".//{http://schemas.openxmlformats.org/presentationml/2006/main}bg"
            )
            if bg is None:
                return False
            return bg.find(".//{http://schemas.openxmlformats.org/drawingml/2006/main}blip") is not None
        except Exception:
            return False

    def _relationships(self, slide, pkg: SafePackage) -> list[Relationship]:
        rels: list[Relationship] = []
        try:
            for rel in slide.part.rels.values():
                target = str(rel.target_partname) if not rel.is_external else rel.target_ref
                exists = True
                if not rel.is_external:
                    target_name = target.lstrip("/")
                    exists = pkg.has_part(target_name)
                action = None
                el = slide._element
                r_attr = (
                    "{http://schemas.openxmlformats.org/officeDocument/2006/"
                    "relationships}id"
                )
                for node in el.iter():
                    if node.get(r_attr) == rel.rId:
                        action = node.get("action")
                        break
                rels.append(
                    Relationship(
                        rId=rel.rId,
                        rel_type=rel.reltype,
                        target=target,
                        is_external=rel.is_external,
                        target_exists=exists,
                        action=action,
                    )
                )
        except Exception as exc:
            raise PackageError(f"Failed parsing relationships: {exc}") from exc
        return rels


def build_model(path: str | Path, config=None) -> PresentationModel:
    return PresentationBuilder(path, config).build()
