"""Cross-renderer fixtures.

Two decks carry the *same* content but use different authoring settings
(16:9 vs 4:3, native table/chart vs flattened shapes, YaHei vs Calibri).
The manifest records the expected rendering differences across LibreOffice,
PowerPoint and WPS as static notes — no actual rendering is performed.
"""

from __future__ import annotations

from pathlib import Path

from pptx.util import Emu, Pt

from genutil import (CJK_FONT, add_rect, add_textbox, add_title, blank_slide,
                     new_pres, save)

CONTENT_TITLE = "Quarterly Results"
CONTENT_BODY = "Revenue rose steadily through the year, with the strongest quarter in Q4."


def _deck_a(corpus: Path) -> Path:
    prs = new_pres()  # 16:9
    s = blank_slide(prs)
    add_title(s, CONTENT_TITLE, font_name=CJK_FONT)
    add_textbox(s, CONTENT_BODY, Emu(600000), Emu(1600000),
                Emu(10800000), Emu(1200000), size=Pt(22), font_name=CJK_FONT)
    # native table
    shape = s.shapes.add_table(3, 2, Emu(600000), Emu(3200000),
                               Emu(5000000), Emu(2000000))
    tbl = shape.table
    tbl.cell(0, 0).text = "Quarter"
    tbl.cell(0, 1).text = "Revenue"
    tbl.cell(1, 0).text = "Q1"
    tbl.cell(1, 1).text = "$1.2M"
    tbl.cell(2, 0).text = "Q4"
    tbl.cell(2, 1).text = "$1.8M"
    out = corpus / "crossrender_native_16x9.pptx"
    save(prs, out)
    return out


def _deck_b(corpus: Path) -> Path:
    prs = new_pres()
    prs.slide_width = Emu(9144000)   # 4:3
    prs.slide_height = Emu(6858000)
    s = blank_slide(prs)
    # Flattened version: same text, but table drawn as plain rectangles.
    add_title(s, CONTENT_TITLE)
    add_textbox(s, CONTENT_BODY, Emu(450000), Emu(1400000),
                Emu(8200000), Emu(1100000), size=Pt(20), font_name="Calibri")
    # fake table as rectangles
    rows = [("Quarter", "Revenue"), ("Q1", "$1.2M"), ("Q4", "$1.8M")]
    for i, (a, b) in enumerate(rows):
        y = 2800000 + i * 600000
        add_rect(s, Emu(450000), Emu(y), Emu(2200000), Emu(550000),
                 fill=(0xEE, 0xEE, 0xEE), line=(0x99, 0x99, 0x99))
        add_rect(s, Emu(2650000), Emu(y), Emu(2200000), Emu(550000),
                 fill=(0xEE, 0xEE, 0xEE), line=(0x99, 0x99, 0x99))
        add_textbox(s, a, Emu(500000), Emu(y + 80000), Emu(2100000), Emu(400000), size=Pt(14))
        add_textbox(s, b, Emu(2700000), Emu(y + 80000), Emu(2100000), Emu(400000), size=Pt(14))
    out = corpus / "crossrender_flat_4x3.pptx"
    save(prs, out)
    return out


def build(corpus_dir: Path) -> list[dict]:
    corpus_dir.mkdir(parents=True, exist_ok=True)
    _deck_a(corpus_dir)
    _deck_b(corpus_dir)
    note = (
        "Same content, different authoring. Expected renderer differences: "
        "(1) LibreOffice falls back to a metric font (e.g. Noto Sans CJK) when "
        "Microsoft YaHei is absent, slightly shifting line breaks vs PowerPoint. "
        "(2) PowerPoint renders the native table with its own theme styling; "
        "LibreOffice and WPS apply their own table borders, so column widths may "
        "reflow by a few pixels. (3) The 4:3 flattened deck has no native table, "
        "so all three renderers should agree, but the rectangles may not align to "
        "a real grid in master-view editing. (4) WPS on Linux may substitute a "
        "different CJK font than Windows PowerPoint, altering glyph metrics."
    )
    return [
        {
            "file": "crossrender_native_16x9.pptx",
            "category": "cross-renderer",
            "expected_rule_ids": [],
            "expected_severity_counts": {"error": 0, "warning": 0, "info": 0},
            "summary": "16:9, Microsoft YaHei, native 3x2 table. " + note,
        },
        {
            "file": "crossrender_flat_4x3.pptx",
            "category": "cross-renderer",
            "expected_rule_ids": ["offslide_object"],
            "expected_severity_counts": {"error": 1, "warning": 0, "info": 0},
            "summary": "4:3, Calibri, table flattened to rectangles. The title text box was authored at "
                       "the 16:9 width (~12.03 in) and overflows the 4:3 canvas (10 in) by ~2 in, which is "
                       "a genuine offslide_object finding rather than a false positive. " + note,
        },
    ]
