"""Unit tests for the object_overlap rule."""

from __future__ import annotations

from PIL import Image
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Emu, Inches, Pt

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


def _label(slide, text, left, top, width, height):
    box = slide.shapes.add_textbox(left, top, width, height)
    box.text_frame.text = text
    for para in box.text_frame.paragraphs:
        for run in para.runs:
            run.font.size = Pt(20)
    return box


def test_single_card_collision_reports_exactly_one_issue(tmp_path):
    # Mirrors corpus slide 3: two stacked cards, each carrying its own label.
    # The labels sit on their own cards; the only real collision is the two
    # card rectangles, so exactly one issue must be reported.
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Emu(2000000), Emu(1800000),
                           Emu(4000000), Emu(2200000))
    _label(slide, "Back card", Emu(2100000), Emu(1900000), Emu(3800000), Emu(600000))
    slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Emu(3000000), Emu(2400000),
                           Emu(4000000), Emu(2200000))
    _label(slide, "Front card covers the back card", Emu(3100000), Emu(2500000),
           Emu(3800000), Emu(600000))

    issues = _run(prs, tmp_path)

    assert len(issues) == 1
    assert issues[0].rule_id == RuleId.OBJECT_OVERLAP.value


def test_picture_with_partial_text_overlay_not_flagged(tmp_path):
    # Common image+text design: a text list overlaps the right part of a
    # photo (~57% coverage). This is intentional overlay, not a collision.
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    img_path = str(tmp_path / "photo.png")
    Image.new("RGB", (200, 140), (90, 130, 180)).save(img_path)
    slide.shapes.add_picture(img_path, Emu(8200000), Emu(1800000),
                             Emu(2800000), Emu(2000000))
    box = slide.shapes.add_textbox(Emu(800000), Emu(1600000),
                                   Emu(9000000), Emu(3600000))
    box.text_frame.text = "1. Goals\n2. Scope\n3. Timeline"

    issues = _run(prs, tmp_path)

    assert issues == []
