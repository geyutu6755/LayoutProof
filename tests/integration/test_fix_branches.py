"""Targeted branch coverage for fix/engine.py (paths the happy-path loop
does not naturally exercise)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

from layoutproof.fix.engine import fix_file, _normalize_cjk_text


# ---------------------------------------------------------------------------
# Direct unit coverage of the CJK normaliser (lines 52-70)
# ---------------------------------------------------------------------------
def test_normalize_cjk_empty_and_ascii():
    assert _normalize_cjk_text("") == ""
    assert _normalize_cjk_text("plain ascii text") == "plain ascii text"


def test_normalize_cjk_strips_latin_space():
    assert _normalize_cjk_text("LayoutProof 自动") == "LayoutProof自动"
    assert _normalize_cjk_text("自动 LayoutProof") == "自动LayoutProof"


def test_normalize_cjk_halfwidth_punct_after_cjk():
    assert _normalize_cjk_text("你好,世界") == "你好，世界"
    assert _normalize_cjk_text("你好;再见") == "你好；再见"
    assert _normalize_cjk_text("你好!") == "你好！"


def test_normalize_cjk_halfwidth_punct_before_cjk():
    assert _normalize_cjk_text("(你好)") == "（你好）"
    assert _normalize_cjk_text(":你好") == "：你好"


def test_normalize_cjk_period_not_decimal():
    assert _normalize_cjk_text("结束.下一句") == "结束。下一句"
    # Decimal points stay untouched.
    assert _normalize_cjk_text("圆周率3.14") == "圆周率3.14"


# ---------------------------------------------------------------------------
# Entry-point edge paths
# ---------------------------------------------------------------------------
def test_fix_missing_source_returns_failed_report(tmp_path):
    report = fix_file(tmp_path / "nope.pptx", make_backup=False)
    assert report.success is False
    assert "not found" in report.note


def test_fix_corrupt_deck_returns_error_report(tmp_path):
    bad = tmp_path / "bad.pptx"
    bad.write_bytes(b"PK\x03\x04 not really a pptx")
    report = fix_file(bad, make_backup=False)
    assert report.success is False


def test_fix_default_output_path(tmp_path):
    src = tmp_path / "deck.pptx"
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    box = slide.shapes.add_textbox(Inches(11.5), Inches(1), Inches(2), Inches(1))
    box.text_frame.text = "offscreen"
    box.text_frame.paragraphs[0].runs[0].font.size = Pt(18)
    prs.save(str(src))

    report = fix_file(src, make_backup=False)  # output_path -> default
    expected = tmp_path / "deck.fixed.pptx"
    assert expected.exists()
    assert report.success is True
    assert report.output_path == str(expected.resolve())


# ---------------------------------------------------------------------------
# Full-profile fixes: adjust_contrast and normalize_cjk_text
# ---------------------------------------------------------------------------
def _save(path: Path, build) -> None:
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    build(prs, slide)
    prs.save(str(path))


def test_fix_adjust_contrast_with_shape_solid_fill(tmp_path):
    src = tmp_path / "con.pptx"

    def build(prs, slide):
        box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(5), Inches(1))
        box.fill.solid()
        box.fill.fore_color.rgb = RGBColor(0xFF, 0xFF, 0xFF)  # white fill
        run = box.text_frame.paragraphs[0].add_run()
        run.text = "低对比度灰字测试"
        run.font.size = Pt(18)
        run.font.color.rgb = RGBColor(0xCC, 0xCC, 0xCC)  # light gray on white

    _save(src, build)
    out = tmp_path / "con.fixed.pptx"
    report = fix_file(src, output_path=out, profile="full", make_backup=False)

    actions = {a.action for a in report.applied}
    assert "adjust_contrast" in actions
    assert report.success is True


def test_fix_normalize_cjk_text_full_profile(tmp_path):
    src = tmp_path / "cjk.pptx"

    def build(prs, slide):
        box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(5), Inches(1))
        run = box.text_frame.paragraphs[0].add_run()
        run.text = "Hello 世界,你好"  # latin-space + halfwidth comma
        run.font.size = Pt(18)

    _save(src, build)
    out = tmp_path / "cjk.fixed.pptx"
    report = fix_file(src, output_path=out, profile="full", make_backup=False)

    actions = {a.action for a in report.applied}
    assert "normalize_cjk_text" in actions


def test_fix_nonfixable_overlap_is_skipped(tmp_path):
    src = tmp_path / "ov.pptx"

    def build(prs, slide):
        a = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(3), Inches(1))
        a.text_frame.text = "Box A content"
        a.text_frame.paragraphs[0].runs[0].font.size = Pt(18)
        b = slide.shapes.add_textbox(Inches(2.5), Inches(1.2), Inches(3), Inches(1))
        b.text_frame.text = "Box B content"
        b.text_frame.paragraphs[0].runs[0].font.size = Pt(18)

    _save(src, build)
    out = tmp_path / "ov.fixed.pptx"
    report = fix_file(src, output_path=out, profile="full", make_backup=False)

    skipped_ids = {s.rule_id for s in report.skipped}
    assert "object_overlap" in skipped_ids
    # No fix exists for overlap, so it stays -> after.total == before.total,
    # success is False but the report still lists the skipped item.
    assert report.applied == []


def test_fix_adjust_contrast_via_slide_background(tmp_path):
    """When the text box has no solid fill, the fix should fall back to the
    slide's solid background (covers _slide_solid_bg)."""
    from pptx.enum.dml import MSO_FILL

    src = tmp_path / "conbg.pptx"

    def build(prs, slide):
        slide.background.fill.solid()
        slide.background.fill.fore_color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(5), Inches(1))
        # Deliberately leave the box fill as default (no solid fill).
        run = box.text_frame.paragraphs[0].add_run()
        run.text = "依赖幻灯片背景的低对比度灰字"
        run.font.size = Pt(18)
        run.font.color.rgb = RGBColor(0xDD, 0xDD, 0xDD)

    _save(src, build)
    out = tmp_path / "conbg.fixed.pptx"
    report = fix_file(src, output_path=out, profile="full", make_backup=False)

    actions = {a.action for a in report.applied}
    assert "adjust_contrast" in actions
