"""Broken fixtures: one planted defect per slide.

``broken_all.pptx`` contains 11 slides, each demonstrating one positive sample
for a detection rule.  Two defects (corrupted media, broken internal
reference) are planted by post-processing the OOXML zip after python-pptx
saves the file.  ``broken_structure.pptx`` is a deliberately truncated zip
used as a positive sample for ``structure_anomaly`` and is *not* expected to
open cleanly.
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

from pptx.enum.text import PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Pt

from genutil import (CJK_FONT, add_pic, add_rect, add_textbox, add_title,
                     blank_slide, new_pres, png_stream, save)

SLIDE_RELS_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
SLIDE_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide"


def _build_deck(corpus: Path) -> Path:
    prs = new_pres()

    # 1. offslide_object: rectangle fully to the right of the canvas.
    s = blank_slide(prs)
    add_title(s, "Slide with an off-slide shape")
    add_rect(s, Emu(12700000), Emu(2000000), Emu(2000000), Emu(1200000),
             fill=(0xFF, 0xCC, 0xCC))  # way past slide width 12192000

    # 2. text_overflow: huge text in a tiny box.
    s = blank_slide(prs)
    add_title(s, "Overflowing text")
    add_textbox(
        s,
        "This sentence is far too long for the tiny box it lives in, so "
        "PowerPoint will either clip it or silently shrink it down.",
        Emu(600000), Emu(1600000), Emu(1800000), Emu(700000),
        size=Pt(24),
    )

    # 3. object_overlap: two cards stacked on the same spot.
    s = blank_slide(prs)
    add_title(s, "Overlapping objects")
    add_rect(s, Emu(2000000), Emu(1800000), Emu(4000000), Emu(2200000),
             fill=(0xCC, 0xDD, 0xFF))
    add_textbox(s, "Back card", Emu(2100000), Emu(1900000), Emu(3800000), Emu(600000), size=Pt(20))
    add_rect(s, Emu(3000000), Emu(2400000), Emu(4000000), Emu(2200000),
             fill=(0xFF, 0xDD, 0xCC))
    add_textbox(s, "Front card covers the back card", Emu(3100000), Emu(2500000), Emu(3800000), Emu(600000), size=Pt(20))

    # 4. font_too_small: 8pt footnote.
    s = blank_slide(prs)
    add_title(s, "Tiny footer")
    add_textbox(s, "8 pt footnote: this is below the readable threshold.",
                Emu(600000), Emu(3000000), Emu(10000000), Emu(600000), size=Pt(8))

    # 5. low_contrast: light grey on white.
    s = blank_slide(prs)
    add_title(s, "Low contrast text")
    add_textbox(s, "Light grey text on white background — hard to read.",
                Emu(600000), Emu(1800000), Emu(10000000), Emu(900000),
                size=Pt(24), color=(0xDD, 0xDD, 0xDD))

    # 6. blank_slide: deliberately empty.
    s = blank_slide(prs)

    # 7. unfinished_placeholder: leftover prompt / TODO / Lorem ipsum.
    s = blank_slide(prs)
    add_textbox(s, "Click to add title", Emu(600000), Emu(400000), Emu(10000000), Emu(900000), size=Pt(28))
    add_textbox(s, "TODO: fill in the Q3 numbers before review", Emu(600000), Emu(1800000), Emu(10000000), Emu(700000), size=Pt(18))
    add_textbox(s, "Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
                Emu(600000), Emu(2800000), Emu(10000000), Emu(700000), size=Pt(18))

    # 8. media_broken: a picture whose blob will be corrupted in post.
    s = blank_slide(prs)
    add_title(s, "Broken media")
    pic = s.shapes.add_picture(png_stream((200, 100, 100)), Emu(2000000), Emu(1600000),
                              Emu(4000000), Emu(2600000))
    pic._element.find(
        "{http://schemas.openxmlformats.org/drawingml/2006/main}nvPicPr"
    )  # no-op touch

    # 9. broken_reference: a hyperlink whose target we rewrite to a missing slide.
    s = blank_slide(prs)
    add_title(s, "Broken internal link")
    tb = add_textbox(s, "Jump to the appendix slide", Emu(600000), Emu(1800000),
                     Emu(10000000), Emu(900000), size=Pt(22))
    run = tb.text_frame.paragraphs[0].runs[0]
    run.hyperlink.address = "http://example.com/placeholder"

    # 10. missing_alt_text: picture with NO alt text (strip python-pptx's auto descr).
    s = blank_slide(prs)
    add_title(s, "Picture without alt text")
    pic_noalt = s.shapes.add_picture(png_stream((150, 150, 200)), Emu(2000000), Emu(1600000),
                                     Emu(4000000), Emu(2600000))
    cNvPr = pic_noalt._element.find(qn("p:nvPicPr")).find(qn("p:cNvPr"))
    if "descr" in cNvPr.attrib:
        del cNvPr.attrib["descr"]
    if "title" in cNvPr.attrib:
        del cNvPr.attrib["title"]

    # 11. cjk_typography: line starts with a comma, no CJK-Latin spacing.
    s = blank_slide(prs)
    add_title(s, "中文排版问题", font_name=CJK_FONT)
    # Second line starts with "，" (forbidden line-start punctuation).
    tb = add_textbox(s, "第一章 概述", Emu(600000), Emu(1600000), Emu(10000000), Emu(700000),
                     size=Pt(22), font_name=CJK_FONT)
    # append a line break + a paragraph that begins with a comma
    p2 = tb.text_frame.add_paragraph()
    r2 = p2.add_run()
    r2.text = "，此处分行错误，逗号落到了行首"
    r2.font.size = Pt(22)
    r2.font.name = CJK_FONT
    # CJK glued to Latin/digits with no spacing
    add_textbox(s, "使用Python3编写脚本v2.0完成部署",
                Emu(600000), Emu(2800000), Emu(10000000), Emu(700000),
                size=Pt(20), font_name=CJK_FONT)

    out = corpus / "broken_all.pptx"
    save(prs, out)
    _post_process(out)
    return out


def _post_process(path: Path) -> None:
    """Corrupt the media part on slide 8 and rewrite the slide-9 hyperlink to a
    non-existent internal slide target."""
    tmp = path.with_suffix(".tmp.pptx")

    with zipfile.ZipFile(path, "r") as zin:
        names = zin.namelist()
        data = {n: zin.read(n) for n in names}

    # --- 1. find slide8 rels -> media target, corrupt that media file ---
    s8_rels = data["ppt/slides/_rels/slide8.xml.rels"].decode("utf-8")
    m = re.search(r'Target="(\.\./media/[^"]+)"', s8_rels)
    if not m:
        raise RuntimeError("slide8 rels has no media target")
    media_entry = "ppt/" + m.group(1).lstrip("./").replace("../", "")
    # normalise: ../media/image1.png -> ppt/media/image1.png
    media_entry = "ppt/media/" + m.group(1).split("/")[-1]
    data[media_entry] = b"\x00\x01NOT_A_REAL_PNG\x02\x03 corrupted payload"

    # --- 2. rewrite slide9 hyperlink rel to a missing internal slide ---
    s9_rels_name = "ppt/slides/_rels/slide9.xml.rels"
    s9_rels = data[s9_rels_name].decode("utf-8")
    # Replace the external hyperlink rel with an internal one pointing at a
    # slide that does not exist in the package.
    s9_rels_new = re.sub(
        r'<Relationship[^>]*Type="[^"]/hyperlink"[^>]*/>',
        '<Relationship Id="rId99" '
        f'Type="{SLIDE_REL_TYPE}" Target="../slides/slide_missing_appendix.xml"/>',
        s9_rels,
    )
    # The hlinkClick r:id must already match rId99; python-pptx assigned its own
    # rId to the external link, so also patch the slide XML to reference rId99.
    data[s9_rels_name] = s9_rels_new.encode("utf-8")

    s9_xml_name = "ppt/slides/slide9.xml"
    s9_xml = data[s9_xml_name].decode("utf-8")
    # Replace whatever r:id the hlinkClick currently points at with rId99.
    s9_xml_new = re.sub(
        r'(<a:hlinkClick[^>]*r:id=")[^"]+(")',
        r"\g<1>rId99\g<2>",
        s9_xml,
    )
    data[s9_xml_name] = s9_xml_new.encode("utf-8")

    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for n in names:
            zout.writestr(n, data[n])

    tmp.replace(path)


def _structure(corpus: Path) -> Path:
    prs = new_pres()
    s = blank_slide(prs)
    add_title(s, "This file is intentionally corrupted")
    out = corpus / "broken_structure.pptx"
    save(prs, out)
    # Truncate the last 300 bytes to destroy the zip central directory.
    raw = out.read_bytes()
    out.write_bytes(raw[:-300])
    return out


def build(corpus_dir: Path) -> list[dict]:
    corpus_dir.mkdir(parents=True, exist_ok=True)
    _build_deck(corpus_dir)
    _structure(corpus_dir)
    return [
        {
            "file": "broken_all.pptx",
            "category": "broken",
            "expected_rule_ids": [
                "offslide_object", "text_overflow", "object_overlap",
                "font_too_small", "low_contrast", "blank_slide",
                "unfinished_placeholder", "media_broken", "broken_reference",
                "missing_alt_text", "cjk_typography",
            ],
            "expected_severity_counts": {"error": 4, "warning": 6, "info": 1},
            "summary": "One defect per slide: off-slide shape, overflowing box, overlap, 8pt text, "
                       "grey-on-white contrast, blank slide, TODO/Lorem placeholders, corrupted PNG, "
                       "hyperlink to missing slide, alt-less image, CJK kinsoku violation.",
        },
        {
            "file": "broken_structure.pptx",
            "category": "broken",
            "expected_rule_ids": ["structure_anomaly"],
            "expected_severity_counts": {"error": 1, "warning": 0, "info": 0},
            "summary": "Truncated OOXML zip; expected to fail python-pptx open (positive sample for structure_anomaly).",
        },
    ]
