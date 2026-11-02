"""Self-contained .pptx builders and raw archive fixtures for web tests.

Kept independent of tests/helpers_decks.py so the web-specific suite never
touches files outside its own folder. All decks are real, generated on disk.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

from pptx import Presentation
from pptx.util import Inches, Pt

MINIMAL_OFFICE_PARTS = {
    "[Content_Types].xml": (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b"<Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'>"
        b"<Default Extension='rels' ContentType='application/x-rel+xml'/>"
        b"<Default Extension='xml' ContentType='application/xml'/>"
        b"</Types>"
    ),
    "ppt/presentation.xml": (
        b"<?xml version='1.0'?>"
        b"<p:presentation xmlns:p='http://schemas.openxmlformats.org/"
        b"presentationml/2006/main'/>"
    ),
    "ppt/slides/slide1.xml": (
        b"<?xml version='1.0'?>"
        b"<p:sld xmlns:p='http://schemas.openxmlformats.org/"
        b"presentationml/2006/main'/>"
    ),
    "ppt/slides/_rels/slide1.xml.rels": (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b"<Relationships xmlns='http://schemas.openxmlformats.org/"
        b"package/2006/relationships'/>"
    ),
}


def save_clean_deck(path: Path, slides: int = 1) -> Path:
    prs = Presentation()
    for _ in range(slides):
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(6), Inches(1))
        box.text_frame.text = "A clean, readable deck body sentence for testing."
        for para in box.text_frame.paragraphs:
            for run in para.runs:
                run.font.size = Pt(18)
    prs.save(str(path))
    return path


def save_broken_deck(path: Path) -> Path:
    """Tiny font + off-slide box + leftover placeholder: deterministic findings."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    tiny = slide.shapes.add_textbox(Inches(0.5), Inches(0.5), Inches(4), Inches(0.6))
    tiny.name = "TinyBody"
    run = tiny.text_frame.paragraphs[0].add_run()
    run.text = "tiny eight point text that should be flagged."
    run.font.size = Pt(8)

    off = slide.shapes.add_textbox(Inches(13.5), Inches(0.5), Inches(2.5), Inches(0.8))
    off.name = "OffCanvas"
    run = off.text_frame.paragraphs[0].add_run()
    run.text = "Far off to the right, outside the slide canvas."
    run.font.size = Pt(18)

    placeholder = slide.shapes.add_textbox(Inches(0.6), Inches(4.2), Inches(4), Inches(0.8))
    run = placeholder.text_frame.paragraphs[0].add_run()
    run.text = "Click to add title (TODO 待补充)"
    run.font.size = Pt(18)

    prs.save(str(path))
    return path


def write_raw_zip(path: Path, entries: dict[str, bytes]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return path
