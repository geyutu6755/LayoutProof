"""Unit tests for the heuristic text_overflow rule."""

from __future__ import annotations

from pptx import Presentation
from pptx.enum.text import MSO_AUTO_SIZE
from pptx.util import Inches, Pt

from layoutproof.config import QualityConfig
from layoutproof.models import RuleId
from layoutproof.parsing import build_model
from layoutproof.rules.text_overflow import TextOverflowRule


def _run(prs, path):
    target = str(path / "deck.pptx")
    prs.save(target)
    model = build_model(target)
    return list(TextOverflowRule(QualityConfig()).check(model))


def _add_overflowing_box(slide, top=Inches(1), height=Inches(0.5), autofit=None,
                          text="Hello world line " * 8, font_size=Pt(24)):
    box = slide.shapes.add_textbox(Inches(1), top, Inches(4), height)
    tf = box.text_frame
    tf.word_wrap = True
    if autofit is not None:
        tf.auto_size = autofit
    run = tf.paragraphs[0].add_run()
    run.text = text
    run.font.size = font_size
    return box


def test_triggers_on_dense_text(tmp_path):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_overflowing_box(slide, autofit=MSO_AUTO_SIZE.NONE)

    issues = _run(prs, tmp_path)

    assert len(issues) == 1
    issue = issues[0]
    assert issue.rule_id == RuleId.TEXT_OVERFLOW.value
    assert 0.7 <= issue.confidence <= 0.85
    assert issue.evidence["estimated_lines"] > 1
    assert issue.evidence["estimated_height_pt"] > issue.evidence["box_height_pt"]
    assert issue.evidence["autofit"] == "noAutofit"


def test_skips_when_norm_autofit_enabled(tmp_path):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    # Same dense text, but PowerPoint will auto-shrink the text itself.
    _add_overflowing_box(slide, autofit=MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE)

    issues = _run(prs, tmp_path)

    assert issues == []


def test_skips_when_box_is_tall_enough(tmp_path):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_overflowing_box(slide, height=Inches(4), autofit=MSO_AUTO_SIZE.NONE)

    issues = _run(prs, tmp_path)

    assert issues == []


def test_skips_short_text_in_normal_box(tmp_path):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_overflowing_box(
        slide, height=Inches(1), text="Hello world", autofit=MSO_AUTO_SIZE.NONE
    )

    issues = _run(prs, tmp_path)

    assert issues == []


def test_skips_inherited_font_size(tmp_path):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(0.5))
    box.text_frame.word_wrap = True
    run = box.text_frame.paragraphs[0].add_run()
    run.text = "Hello world line " * 8  # no explicit font size set

    issues = _run(prs, tmp_path)

    assert issues == []
