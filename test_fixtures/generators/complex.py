"""Complex, information-dense decks.

Stress fixture: full-bleed background image, native table, native chart,
groups, dozens of shapes, and deliberate decorative stacking.  These are
intentionally busy but should not trigger hard errors; they exist to check
that the detector does not explode on rich layouts (and that intentional
overlap is not over-flagged).
"""

from __future__ import annotations

from pathlib import Path

from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Emu, Inches, Pt

from genutil import (add_pic, add_rect, add_textbox, add_title, blank_slide,
                     new_pres, png_stream, save, set_slide_bg)


def _background(slide) -> None:
    """Full-bleed background picture covering the whole slide."""
    slide.shapes.add_picture(png_stream((60, 80, 120), (1219, 686)),
                             Emu(0), Emu(0), Emu(12192000), Emu(6858000))


def _table(slide) -> None:
    rows, cols = 4, 3
    shape = slide.shapes.add_table(rows, cols, Emu(600000), Emu(2200000),
                                   Emu(5400000), Emu(2400000))
    table = shape.table
    headers = ["Quarter", "Revenue", "Growth"]
    for c, h in enumerate(headers):
        cell = table.cell(0, c)
        cell.text = h
        for p in cell.text_frame.paragraphs:
            for r in p.runs:
                r.font.size = Pt(16)
                r.font.bold = True
    data = [
        ("Q1", "$1.2M", "+8%"),
        ("Q2", "$1.4M", "+12%"),
        ("Q3", "$1.5M", "+7%"),
    ]
    for ri, row in enumerate(data, start=1):
        for ci, val in enumerate(row):
            table.cell(ri, ci).text = val


def _chart(slide) -> None:
    chart_data = CategoryChartData()
    chart_data.categories = ["Q1", "Q2", "Q3", "Q4"]
    chart_data.add_series("Revenue", (12, 14, 15, 18))
    chart_data.add_series("Cost", (9, 10, 11, 12))
    gframe = slide.shapes.add_chart(
        XL_CHART_TYPE.COLUMN_CLUSTERED,
        Emu(6400000), Emu(2200000), Emu(5400000), Emu(3200000),
        chart_data,
    )
    gframe.chart.has_legend = True
    gframe.chart.legend.position = XL_LEGEND_POSITION.BOTTOM


def _many_shapes(slide) -> None:
    """A grid of 40 small coloured squares (a 'heatmap' decoration)."""
    cols, rows = 10, 4
    sw, sh = Emu(700000), Emu(500000)
    for r in range(rows):
        for c in range(cols):
            shade = 120 + (r * cols + c) * 3 % 120
            shp = slide.shapes.add_shape(
                MSO_SHAPE.RECTANGLE,
                Emu(600000 + c * 720000), Emu(2000000 + r * 520000),
                sw, sh,
            )
            shp.fill.solid()
            shp.fill.fore_color.rgb = RGBColor(shade, 90, 160)
            shp.line.fill.background()
            shp.shadow.inherit = False


def build(corpus_dir: Path) -> list[dict]:
    corpus_dir.mkdir(parents=True, exist_ok=True)
    prs = new_pres()

    # Slide 1: full-bleed background + translucent overlay title + table + chart.
    s = blank_slide(prs)
    _background(s)
    # translucent title band on top of background (intentional overlap)
    band = add_rect(s, Emu(0), Emu(300000), Emu(12192000), Emu(1100000),
                    fill=(255, 255, 255), line=(255, 255, 255))
    add_textbox(s, "Annual Report — Complex Layout",
                Emu(600000), Emu(450000), Emu(11000000), Emu(800000),
                size=Pt(30), bold=True, color=(20, 20, 20))
    _table(s)
    _chart(s)

    # Slide 2: dozens of small shapes.
    s = blank_slide(prs)
    add_title(s, "Dense shape grid (heatmap)")
    _many_shapes(s)

    # Slide 3: grouped shapes + decorative stack.
    s = blank_slide(prs)
    add_title(s, "Grouped decoration")
    shapes = []
    for i in range(5):
        shp = s.shapes.add_shape(
            MSO_SHAPE.OVAL,
            Emu(2000000 + i * 900000), Emu(2200000),
            Emu(900000), Emu(900000),
        )
        shp.fill.solid()
        shp.fill.fore_color.rgb = RGBColor(80 + i * 30, 120, 200 - i * 20)
        shp.line.color.rgb = RGBColor(255, 255, 255)
        shapes.append(shp)
    # group them
    grp = s.shapes.add_group_shape(shapes)
    grp.name = "decorative_bubbles"

    out = corpus_dir / "complex_overloaded.pptx"
    save(prs, out)
    return [
        {
            "file": "complex_overloaded.pptx",
            "category": "complex",
            "expected_rule_ids": [],
            "expected_severity_counts": {"error": 0, "warning": 0, "info": 0},
            "summary": "Full-bleed background, native table, clustered-column chart, 40-square heatmap, "
                       "and a grouped oval stack.  Rich but valid; intended to stress false-positive rate.",
        }
    ]
