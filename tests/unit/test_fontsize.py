"""Unit tests for the deterministic font_too_small rule."""

from __future__ import annotations

from pptx import Presentation
from pptx.util import Inches, Pt

from layoutproof.config import QualityConfig
from layoutproof.models import RuleId
from layoutproof.parsing import build_model
from layoutproof.rules.font_size import FontSizeRule


def _run(prs, tmp_path):
    target = str(tmp_path / "deck.pptx")
    prs.save(target)
    model = build_model(target)
    return list(FontSizeRule(QualityConfig()).check(model))


def _sized_box(slide, size):
    box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(0.8))
    box.text_frame.text = "sample text"
    if size is not None:
        box.text_frame.paragraphs[0].runs[0].font.size = Pt(size)
    return box


def test_triggers_on_tiny_explicit_font(tmp_path):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _sized_box(slide, 6)

    issues = _run(prs, tmp_path)

    assert len(issues) == 1
    assert issues[0].rule_id == RuleId.FONT_TOO_SMALL.value
    assert issues[0].evidence["min_font_size_pt"] == 6


def test_readable_font_negative(tmp_path):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _sized_box(slide, 18)

    issues = _run(prs, tmp_path)

    assert issues == []


def test_inherited_font_size_not_judged(tmp_path):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _sized_box(slide, None)  # no explicit size -> inherited

    issues = _run(prs, tmp_path)

    assert issues == []
