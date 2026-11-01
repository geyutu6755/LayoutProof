"""Unit tests for the deterministic offslide_object rule."""

from __future__ import annotations

from pptx import Presentation
from pptx.util import Inches, Pt

from layoutproof.config import QualityConfig
from layoutproof.models import RuleId
from layoutproof.parsing import build_model
from layoutproof.rules.offslide import OffslideRule


def _run(prs, tmp_path):
    target = str(tmp_path / "deck.pptx")
    prs.save(target)
    model = build_model(target)
    return list(OffslideRule(QualityConfig()).check(model))


def _box(slide, x, y=Inches(1), w=Inches(2), h=Inches(1)):
    box = slide.shapes.add_textbox(x, y, w, h)
    box.text_frame.text = "x"
    box.text_frame.paragraphs[0].runs[0].font.size = Pt(18)
    return box


def test_triggers_when_fully_outside(tmp_path):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _box(slide, Inches(14))  # fully beyond the 13.33in right edge

    issues = _run(prs, tmp_path)

    assert len(issues) == 1
    assert issues[0].rule_id == RuleId.OFFSLIDE_OBJECT.value
    assert issues[0].evidence["fully_outside"] is True


def test_triggers_when_partially_outside(tmp_path):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _box(slide, Inches(9), w=Inches(2))  # crosses the 10in right edge, still intersects

    issues = _run(prs, tmp_path)

    assert len(issues) == 1
    assert issues[0].evidence["fully_outside"] is False
    assert issues[0].evidence["fraction_outside"] > 0


def test_clean_in_slide_shape_negative(tmp_path):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _box(slide, Inches(1))

    issues = _run(prs, tmp_path)

    assert issues == []
