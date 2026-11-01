"""Unit tests for the blank_slide rule."""

from __future__ import annotations

from PIL import Image
from pptx import Presentation
from pptx.util import Inches

from layoutproof.config import QualityConfig
from layoutproof.models import RuleId
from layoutproof.parsing import build_model
from layoutproof.rules.blank import BlankSlideRule


def _run(prs, path):
    target = str(path / "deck.pptx")
    prs.save(target)
    model = build_model(target)
    return list(BlankSlideRule(QualityConfig()).check(model))


def test_triggers_on_empty_slide(tmp_path):
    prs = Presentation()
    prs.slides.add_slide(prs.slide_layouts[6])

    issues = _run(prs, tmp_path)

    assert len(issues) == 1
    issue = issues[0]
    assert issue.rule_id == RuleId.BLANK_SLIDE.value
    assert issue.confidence == 0.9
    assert issue.evidence["content_shape_count"] == 0


def test_triggers_when_only_background_picture(tmp_path):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    img_path = str(tmp_path / "bg.png")
    Image.new("RGB", (80, 80), (10, 20, 30)).save(img_path)
    slide.shapes.add_picture(
        img_path, 0, 0, width=prs.slide_width, height=prs.slide_height
    )

    issues = _run(prs, tmp_path)

    assert len(issues) == 1
    assert issues[0].evidence["background_picture"] or issues[0].evidence["visible_shape_count"] >= 1


def test_slide_with_text_is_not_blank(tmp_path):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(1))
    box.text_frame.text = "Hello, real content here"

    issues = _run(prs, tmp_path)

    assert issues == []


def test_slide_with_picture_is_not_blank(tmp_path):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    img_path = str(tmp_path / "photo.png")
    Image.new("RGB", (80, 80), (200, 30, 30)).save(img_path)
    # Small, non-full-bleed picture counts as real content.
    slide.shapes.add_picture(img_path, Inches(1), Inches(1), Inches(2), Inches(2))

    issues = _run(prs, tmp_path)

    assert issues == []
