"""Structured edge / boundary tests: deliberately awkward but valid decks.

These generate real .pptx files with python-pptx (and a little OOXML XML) and
exercising geometry primitives directly. The hard assertions are robustness
and output validity; specific rule outcomes are only asserted where the edge
case deterministically maps to a known behaviour.
"""

from __future__ import annotations

from pptx.util import Emu, Inches, Pt
from lxml import etree

import helpers_decks as decks
from layoutproof.engine import scan_file
from layoutproof.models import ScanResult
from layoutproof.parsing.geometry import Rect
from layoutproof.report import validate_output


def _scan_and_validate(path, profile="full") -> ScanResult:
    result = scan_file(path, profile=profile)
    assert isinstance(result, ScanResult)
    assert result.status in ("ok", "error")
    validate_output(result.to_dict())
    return result


# ---------------------------------------------------------------------------
# Geometry primitive boundaries (geometry.py)
# ---------------------------------------------------------------------------
def test_degenerate_rectangles_do_not_divide_or_crash():
    bounds = Rect(0, 0, 9144000, 6858000)
    zero = Rect(100, 100, 0, 0)
    assert zero.area == 0
    assert zero.fraction_outside(bounds) == 0.0
    assert zero.overlap_ratio(bounds) == 0.0
    # negative extents never produce a negative area
    negative = Rect(0, 0, -1000, -500)
    assert negative.area == 0
    assert negative.intersection(bounds) is None
    # fully outside
    far = Rect(10_000_000, 10_000_000, 100, 100)
    assert far.is_fully_outside(bounds)
    assert far.intersection(bounds) is None
    assert far.fraction_outside(bounds) == 1.0
    # clamp keeps the original size and moves the box inside
    clamped = far.clamp(bounds)
    assert clamped.x == bounds.right - clamped.width
    assert clamped.y == bounds.bottom - clamped.height
    # contains with identical bounds
    assert bounds.contains(bounds)


# ---------------------------------------------------------------------------
# Deck structural edges
# ---------------------------------------------------------------------------
def test_blank_slide_without_any_shape(tmp_path):
    path = tmp_path / "empty_deck.pptx"
    prs = decks.blank_prs()
    decks.add_blank_slide(prs)
    prs.save(str(path))
    result = _scan_and_validate(path)
    assert result.slide_count == 1


def test_empty_textbox_and_zero_length_run(tmp_path):
    path = tmp_path / "empty_runs.pptx"
    prs = decks.blank_prs()
    slide = decks.add_blank_slide(prs)
    box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(5), Inches(1))
    box.text_frame.text = ""  # deliberately empty body
    run = box.text_frame.paragraphs[0].add_run()
    run.text = ""             # zero-length run
    run.font.size = Pt(18)
    # a paragraph with only whitespace
    p2 = box.text_frame.add_paragraph()
    r2 = p2.add_run()
    r2.text = "   \t\n  "
    prs.save(str(path))
    result = _scan_and_validate(path)
    assert result.slide_count == 1


def test_zero_size_and_extreme_coordinates(tmp_path):
    path = tmp_path / "extreme_geom.pptx"
    prs = decks.blank_prs()
    slide = decks.add_blank_slide(prs)
    decks.add_textbox(slide, Emu(0), Emu(0), Emu(0), Emu(0), "zero size box")
    decks.add_textbox(slide, Emu(-80_000_000), Emu(-80_000_000),
                       Emu(9_000_000), Emu(9_000_000), "way up-left")
    decks.add_textbox(slide, Emu(10**12), Emu(10**12), Emu(500_000), Emu(500_000),
                       "astronomically far away")
    decks.add_textbox(slide, Emu(1), Emu(1), Emu(10**11), Emu(10**11),
                       "enormous box")
    prs.save(str(path))
    result = _scan_and_validate(path)
    # every emitted issue carries either null location or integer EMU fields
    for issue in result.issues:
        if issue.location is not None:
            assert all(isinstance(v, int) for v in (
                issue.location.x, issue.location.y,
                issue.location.width, issue.location.height))


def _add_deep_groups(slide, depth: int):
    current = slide.shapes.add_group_shape()
    for _ in range(depth - 1):
        current = current.shapes.add_group_shape()
    inner = current.shapes.add_textbox(Emu(500000), Emu(500000),
                                        Emu(4000000), Emu(800000))
    inner.text_frame.text = "deeply nested leaf text"
    inner.text_frame.paragraphs[0].runs[0].font.size = Pt(18)
    return depth


def test_deeply_nested_groups_do_not_hit_recursion_limit(tmp_path):
    path = tmp_path / "deep_groups.pptx"
    prs = decks.blank_prs()
    slide = decks.add_blank_slide(prs)
    depth = _add_deep_groups(slide, depth=40)
    prs.save(str(path))
    result = _scan_and_validate(path)
    assert result.slide_count == 1
    # walker must have descended; either the leaf/its ancestors produced issues
    # or the deck simply passed - the key invariant is no RecursionError/raise.
    assert depth == 40


def test_unicode_and_long_identifiers_and_text(tmp_path):
    path = tmp_path / "unicode_names.pptx"
    prs = decks.blank_prs()
    slide = decks.add_blank_slide(prs)
    weird_name = "形_" * 80 + "<>&'\""
    box = decks.add_textbox(slide, Inches(1), Inches(1), Inches(6), Inches(1),
                             "混合 English 中文 일본어 텍스트 \n tab\tline",
                             font_pt=18, name=weird_name)
    # punctuation / control-like characters in body text
    box.text_frame.add_paragraph().add_run().text = "…—、，。！？�"
    prs.save(str(path))
    result = _scan_and_validate(path)
    names = {i.shape_name for i in result.issues if i.shape_name is not None}
    # nothing in the schema rejects unicode; serialised JSON must round-trip
    payload = result.to_dict()
    validate_output(payload)


def test_hidden_shape_and_decorative_xml_flag(tmp_path):
    path = tmp_path / "hidden_decor.pptx"
    prs = decks.blank_prs()
    slide = decks.add_blank_slide(prs)
    visible = decks.add_textbox(slide, Inches(1), Inches(1), Inches(6), Inches(1),
                                  "visible content", font_pt=18)
    hidden = decks.add_textbox(slide, Inches(1), Inches(2), Inches(4), Inches(1),
                                "should stay hidden")
    cnv = hidden._element.find(".//{http://schemas.openxmlformats.org/presentationml/2006/main}cNvPr")
    if cnv is not None:
        cnv.set("hidden", "1")
        etree.SubElement(cnv, "{http://schemas.microsoft.com/office/drawing/2012/main}decorative")
    visible.name = "Background decoration"
    prs.save(str(path))
    result = _scan_and_validate(path)
    assert result.slide_count == 1


def test_many_mixed_slides_pipeline(tmp_path):
    path = tmp_path / "mixed.pptx"
    prs = decks.blank_prs()
    for i in range(8):
        slide = decks.add_blank_slide(prs)
        if i % 3 != 0:  # keep every third slide genuinely blank
            decks.add_textbox(slide, Inches(1), Inches(1), Inches(5), Inches(1),
                               f"slide {i} body", font_pt=16)
    prs.save(str(path))
    result = _scan_and_validate(path, profile="core")
    assert result.slide_count == 8
