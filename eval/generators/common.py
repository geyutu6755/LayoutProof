"""Shared, self-contained helpers for the LayoutProof evaluation corpus.

Everything here lives inside ``eval/`` on purpose: it must not import from
``test_fixtures/`` or mutate ``src/``.  It wraps python-pptx primitives and a
small amount of OOXML/zip surgery used to plant deterministic defect samples.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Pt

# ---------------------------------------------------------------------------
# Slide dimensions in EMU
# ---------------------------------------------------------------------------
DIMS = {
    "16:9": (12192000, 6858000),
    "4:3": (9144000, 6858000),
}

REL_IMAGE = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
)
REL_HYPERLINK = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink"
)
REL_SLIDE = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide"
)

# Rule membership in the two shipped profiles (mirrors layoutproof.rules).
CORE_RULES = {
    "offslide_object",
    "font_too_small",
    "text_overflow",
    "unfinished_placeholder",
    "media_broken",
    "broken_reference",
    "structure_anomaly",
}
FULL_ONLY_RULES = {
    "object_overlap",
    "low_contrast",
    "blank_slide",
    "missing_alt_text",
    "cjk_typography",
}


def profile_scope(rule_id: str) -> str:
    """Return "both" (core+full), "full" (full-only), or "core"."""
    if rule_id in CORE_RULES:
        return "both"
    return "full"


def rgb(value) -> RGBColor:
    if isinstance(value, RGBColor):
        return value
    return RGBColor(*value)


def new_prs(aspect: str = "16:9") -> Presentation:
    prs = Presentation()
    w, h = DIMS[aspect]
    prs.slide_width = Emu(w)
    prs.slide_height = Emu(h)
    return prs


def blank(prs: Presentation):
    """Layout index 6 = blank layout without inherited title/body placeholders."""
    return prs.slides.add_slide(prs.slide_layouts[6])


def solid_bg(slide, color) -> None:
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = rgb(color)


def textbox(
    slide,
    text,
    x,
    y,
    w,
    h,
    *,
    size=18.0,
    color=(0x22, 0x22, 0x22),
    font_name=None,
    bold=False,
    wrap=True,
    name=None,
    align=PP_ALIGN.LEFT,
):
    tb = slide.shapes.add_textbox(Emu(x), Emu(y), Emu(w), Emu(h))
    if name:
        tb.name = name
    tf = tb.text_frame
    tf.word_wrap = wrap
    tf.vertical_anchor = MSO_ANCHOR.TOP
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    if size is not None:
        run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = rgb(color)
    if font_name:
        run.font.name = font_name
    return tb


def add_paragraph(tb, text, *, size=18.0, font_name=None, color=(0x22, 0x22, 0x22)):
    p = tb.text_frame.add_paragraph()
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.color.rgb = rgb(color)
    if font_name:
        run.font.name = font_name
    return p


def rect(
    slide,
    x,
    y,
    w,
    h,
    *,
    fill=(0xDD, 0xE6, 0xF0),
    line=(0x99, 0xAA, 0xBB),
    name=None,
    no_shadow=True,
):
    shp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Emu(x), Emu(y), Emu(w), Emu(h))
    if name:
        shp.name = name
    shp.fill.solid()
    shp.fill.fore_color.rgb = rgb(fill)
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = rgb(line)
    if no_shadow:
        shp.shadow.inherit = False
    return shp


def png_bytes(color=(110, 160, 210), size=(240, 160)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def add_pic(slide, color, x, y, w, h, *, alt=None, decorative=False, size=(240, 160)):
    bio = io.BytesIO(png_bytes(color, size))
    pic = slide.shapes.add_picture(bio, Emu(x), Emu(y), Emu(w), Emu(h))
    cnv = pic._element.find(qn("p:nvPicPr")).find(qn("p:cNvPr"))
    if alt is None:
        # python-pptx writes an auto-generated descr; remove it deliberately.
        for attr in ("descr", "title"):
            if attr in cnv.attrib:
                del cnv.attrib[attr]
    else:
        cnv.set("descr", alt)
        cnv.set("title", alt)
    if decorative:
        etree_sub = cnv.makeelement(qn("p:decorative"), {})
        cnv.append(etree_sub)
    return pic


def mark_decorative(shape) -> None:
    cnv = shape._element.find(".//" + qn("p:cNvPr"))
    if cnv is not None and cnv.find(qn("p:decorative")) is None:
        cnv.append(cnv.makeelement(qn("p:decorative"), {}))


def save(prs, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(path))


# ---------------------------------------------------------------------------
# Zip surgery helpers (deterministic defect planting; raw OOXML, no network)
# ---------------------------------------------------------------------------
def rewrite_zip(
    src: Path,
    dst: Path,
    *,
    mutate: dict[str, bytes] | None = None,
    drop: set[str] | None = None,
    extra_rels: dict[str, str] | None = None,
    xml_inject: dict[str, str] | None = None,
    duplicate_entries: list[str] | None = None,
    extra_entries: dict[str, bytes] | None = None,
) -> None:
    """Rewrite a pptx zip without extracting to disk.

    * ``mutate``       existing part name -> replacement bytes
    * ``drop``         parts to omit
    * ``extra_rels``   slide rels part -> XML fragment inserted before </Relationships>
    * ``xml_inject``   slide xml part -> fragment inserted before </p:spTree>
    * ``duplicate_entries`` part names written a second time (package anomaly probe)
    * ``extra_entries`` brand-new zip entries (not referenced; anomaly probes)
    """
    mutate = mutate or {}
    drop = drop or set()
    extra_rels = extra_rels or {}
    xml_inject = xml_inject or {}
    duplicate_entries = duplicate_entries or []
    extra_entries = extra_entries or {}

    with zipfile.ZipFile(src, "r") as zin, zipfile.ZipFile(
        dst, "w", zipfile.ZIP_DEFLATED
    ) as zout:
        infos = zin.infolist()
        for item in infos:
            name = item.filename
            if name in drop:
                continue
            data = zin.read(name)
            if name in mutate:
                data = mutate[name]
            if name in extra_rels:
                text = data.decode("utf-8")
                text = text.replace("</Relationships>", extra_rels[name] + "</Relationships>")
                data = text.encode("utf-8")
            if name in xml_inject:
                text = data.decode("utf-8")
                text = text.replace("</p:spTree>", xml_inject[name] + "</p:spTree>")
                data = text.encode("utf-8")
            zout.writestr(item, data)
            if name in duplicate_entries:
                zout.writestr(name, data)  # intentional duplicate -> anomaly
        for name, data in extra_entries.items():
            zout.writestr(name, data)


def list_media(path: Path) -> list[str]:
    with zipfile.ZipFile(path, "r") as zf:
        return sorted(n for n in zf.namelist() if n.startswith("ppt/media/"))
