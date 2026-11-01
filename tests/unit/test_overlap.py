"""Unit tests for the object_overlap rule."""

from __future__ import annotations

from PIL import Image
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Inches

from layoutproof.config import QualityConfig
from layoutproof.models import RuleId
from layoutproof.parsing import build_model
from layoutproof.rules.object_overlap import ObjectOverlapRule


def _run(prs, path):
    target = str(path / "deck.pptx")
    prs.save(target)
    model = build_model(target)
    return list(ObjectOverlapRule(QualityConfig()).check(model))


def test_triggers_on_overlapping_content_shapes(tmp_path):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(2), Inches(2), Inches(2), Inches(2))
    slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(2.5), Inches(2.5), Inches(2), Inches(2))

    issues = _run(prs, tmp_path)

    assert len(issues) == 1
    issue = issues[0]
    assert issue.rule_id == RuleId.OBJECT_OVERLAP.value
    assert issue.confidence == 0.8
    assert issue.evidence["overlap_ratio"] >= QualityConfig().overlap_ratio_threshold


def test_skips_adjacent_non_overlapping_shapes(tmp_path):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(1), Inches(1), Inches(2), Inches(2))
    slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(4), Inches(1), Inches(2), Inches(2))

    issues = _run(prs, tmp_path)

    assert issues == []


def test_skips_decoratively_named_shape(tmp_path):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    rect = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, Inches(2), Inches(2), Inches(2), Inches(2)
    )
    rect.name = "Background accent"
    slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(2.5), Inches(2.5), Inches(2), Inches(2))

    issues = _run(prs, tmp_path)

    assert issues == []


def test_skips_full_bleed_background_picture(tmp_path):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    img_path = str(tmp_path / "bg.png")
    Image.new("RGB", (80, 80), (10, 20, 30)).save(img_path)
    # First shape, full-bleed: parser marks it as background.
    slide.shapes.add_picture(
        img_path, 0, 0, width=prs.slide_width, height=prs.slide_height
    )
    rect = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, Inches(1), Inches(1), Inches(4), Inches(3)
    )

    issues = _run(prs, tmp_path)

    # The background picture must not collide with the foreground rectangle.
    assert issues == []
    assert rect is not None


def test_skips_grouped_shapes(tmp_path):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    s1 = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(2), Inches(2), Inches(2), Inches(2))
    s2 = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(2.5), Inches(2.5), Inches(2), Inches(2))
    slide.shapes.add_group_shape([s1, s2])

    issues = _run(prs, tmp_path)

    # Deliberately grouped overlapping children must not be flagged.
    assert issues == []
