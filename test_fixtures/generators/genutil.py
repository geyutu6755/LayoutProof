"""Shared helpers for building LayoutProof PPTX fixtures.

Every generator module exposes ``build(corpus_dir: Path) -> list[dict]`` which
writes one or more ``.pptx`` files into *corpus_dir* and returns the manifest
records describing them.  ``build_all.py`` imports each generator, calls
``build``, and collects the records into ``corpus/manifest.json``.

The helpers here deliberately keep fixtures tiny (small in-memory PNGs, plain
shapes) so every ``.pptx`` stays well under 1 MB.
"""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

# 16:9 widescreen, the default PowerPoint slide size.
SLIDE_W = Emu(12192000)
SLIDE_H = Emu(6858000)

CJK_FONT = "Microsoft YaHei"  # 微软雅黑, available on Windows; name is what we plant.


def new_pres() -> Presentation:
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H
    return prs


def blank_slide(prs: Presentation):
    """A truly blank slide (layout index 6 = blank, no inherited placeholders)."""
    return prs.slides.add_slide(prs.slide_layouts[6])


def _rgb(value) -> RGBColor:
    if isinstance(value, RGBColor):
        return value
    return RGBColor(*value)


def set_slide_bg(slide, rgb) -> None:
    """Paint the slide background a solid colour."""
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = _rgb(rgb)


def add_textbox(slide, text, left, top, width, height, *,
                size=Pt(18), bold=False, color=RGBColor(0x33, 0x33, 0x33),
                font_name: str | None = None, align=PP_ALIGN.LEFT,
                word_wrap=True):
    tb = slide.shapes.add_textbox(left, top, width, height)
    tf = tb.text_frame
    tf.word_wrap = word_wrap
    tf.vertical_anchor = MSO_ANCHOR.TOP
    p = tf.paragraphs[0]
    p.alignment = align
    r = p.add_run()
    r.text = text
    r.font.size = size
    r.font.bold = bold
    r.font.color.rgb = _rgb(color)
    if font_name:
        r.font.name = font_name
    return tb


def add_title(slide, text, *, top=Emu(380000), size=Pt(32),
              color=RGBColor(0x1F, 0x1F, 0x1F), font_name=None):
    return add_textbox(
        slide, text, Emu(600000), top, Emu(11000000), Emu(900000),
        size=size, bold=True, color=color, font_name=font_name,
    )


def png_stream(color=(110, 160, 210), size=(240, 160)) -> io.BytesIO:
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def add_pic(slide, color, left, top, width, height, alt: str | None = None):
    """Add a picture.  When *alt* is None the picture is intentionally left
    without alternative text (positive sample for missing_alt_text)."""
    pic = slide.shapes.add_picture(png_stream(color, (240, 160)), left, top, width, height)
    if alt is not None:
        cNvPr = pic._element.find(qn("p:nvPicPr")).find(qn("p:cNvPr"))
        cNvPr.set("descr", alt)
        cNvPr.set("title", alt)
    return pic


def add_rect(slide, left, top, width, height, fill=RGBColor(0xDD, 0xE6, 0xF0),
             line=RGBColor(0x88, 0xAA, 0xCC)):
    from pptx.enum.shapes import MSO_SHAPE
    shp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
    shp.fill.solid()
    shp.fill.fore_color.rgb = _rgb(fill)
    shp.line.color.rgb = _rgb(line)
    shp.shadow.inherit = False
    return shp


def save(prs, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(path))
