"""Shared builders for the new quality/security/performance test suites.

Everything here generates a *real* .pptx (python-pptx) or a real on-disk
archive (zipfile) on demand; no canned detection data is fabricated.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from pptx import Presentation
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
CORPUS_DIR = ROOT / "test_fixtures" / "corpus"


# ---------------------------------------------------------------------------
# python-pptx deck builders
# ---------------------------------------------------------------------------
def blank_prs() -> Presentation:
    return Presentation()


def add_blank_slide(prs: Presentation):
    return prs.slides.add_slide(prs.slide_layouts[6])


def add_textbox(
    slide,
    left: int | None,
    top: int | None,
    width: int | None,
    height: int | None,
    text: str = "Sample body text with enough length.",
    *,
    font_pt: float | None = None,
    name: str | None = None,
):
    box = slide.shapes.add_textbox(
        Emu(left) if left is not None else Emu(0),
        Emu(top) if top is not None else Emu(0),
        Emu(width) if width is not None else Emu(4572000),
        Emu(height) if height is not None else Emu(914400),
    )
    if name is not None:
        box.name = name
    tf = box.text_frame
    tf.text = text
    if font_pt is not None:
        for para in tf.paragraphs:
            for run in para.runs:
                run.font.size = Pt(font_pt)
    return box


def save_clean_deck(path: Path, slides: int = 1) -> Path:
    prs = blank_prs()
    for _ in range(slides):
        slide = add_blank_slide(prs)
        box = add_textbox(slide, Inches(1), Inches(1), Inches(6), Inches(1),
                          "A clean, readable deck body sentence.", font_pt=18)
    prs.save(str(path))
    return path


def save_warning_deck(path: Path) -> Path:
    """Warnings only: an unfinished placeholder prompt (warning) + blank slide."""
    prs = blank_prs()
    s1 = add_blank_slide(prs)
    add_textbox(s1, Inches(1), Inches(1), Inches(6), Inches(1),
                "Click to add title", font_pt=18)
    add_blank_slide(prs)  # empty -> blank slide warning
    prs.save(str(path))
    return path


def save_error_deck(path: Path) -> Path:
    """Deterministic ERROR findings: tiny font + off-slide object."""
    prs = blank_prs()
    slide = add_blank_slide(prs)
    tiny = add_textbox(slide, Inches(0.5), Inches(0.5), Inches(4), Inches(0.6),
                       "tiny eight point text that should be flagged.", font_pt=8)
    tiny.name = "TinyBody"
    off = add_textbox(slide, Inches(13.5), Inches(0.5), Inches(2.5), Inches(0.8),
                      "Far off to the right, outside the slide canvas.", font_pt=18)
    off.name = "OffCanvas"
    prs.save(str(path))
    return path


def tiny_png_bytes(color: tuple[int, int, int] = (200, 30, 30),
                    size: int = 8) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (size, size), color).save(buf, format="PNG")
    return buf.getvalue()


def save_info_deck(path: Path) -> Path:
    """INFO finding (missing_alt_text) only, for fail-on=info matrix tests."""
    prs = blank_prs()
    slide = add_blank_slide(prs)
    image_stream = io.BytesIO(tiny_png_bytes())
    pic = slide.shapes.add_picture(image_stream, Inches(1), Inches(1),
                                   width=Inches(2), height=Inches(2))
    pic.name = "UntitledPicture"
    # python-pptx writes the default file name into descr; remove it so the
    # picture genuinely has no alternative text.
    cnv = pic._element.find(
        ".//{http://schemas.openxmlformats.org/presentationml/2006/main}cNvPr"
    )
    if cnv is not None:
        cnv.attrib.pop("descr", None)
    prs.save(str(path))
    return path


# ---------------------------------------------------------------------------
# raw archive helpers (security tests build malformed packages directly)
# ---------------------------------------------------------------------------
def write_raw_zip(path: Path, entries: dict[str, bytes],
                  *, duplicates: list[tuple[str, bytes]] | None = None) -> Path:
    """Write a .pptx-looking zip; entries are name -> raw bytes.

    ``duplicates`` writes the same member name a second time, which legitimate
    OOXML producers never emit and which the loader must flag, not execute.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
        for name, data in duplicates or []:
            zf.writestr(name, data)
    return path


def minimal_office_parts() -> dict[str, bytes]:
    return {
        "[Content_Types].xml": (
            b'<?xml version="1.0" encoding="UTF-8"?>'
            b"<Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'>"
            b"<Default Extension='rels' ContentType='application/x-rel+xml'/>"
            b"<Default Extension='xml' ContentType='application/xml'/>"
            b"</Types>"
        ),
        "ppt/presentation.xml": b"<?xml version='1.0'?><p:presentation xmlns:p='http://schemas.openxmlformats.org/presentationml/2006/main'/>",
        "ppt/slides/slide1.xml": b"<?xml version='1.0'?><p:sld xmlns:p='http://schemas.openxmlformats.org/presentationml/2006/main'/>",
        "ppt/slides/_rels/slide1.xml.rels": (
            b'<?xml version="1.0" encoding="UTF-8"?>'
            b"<Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'/>"
        ),
    }


def corpus_files() -> list[Path]:
    return sorted(p for p in CORPUS_DIR.glob("*.pptx") if p.is_file())
