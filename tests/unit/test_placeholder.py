"""Unit tests for the unfinished_placeholder rule."""

from __future__ import annotations

from pptx import Presentation
from pptx.util import Inches

from layoutproof.config import QualityConfig
from layoutproof.models import RuleId
from layoutproof.parsing import build_model
from layoutproof.rules.placeholder import UnfinishedPlaceholderRule


def _run(prs, path):
    target = str(path / "deck.pptx")
    prs.save(target)
    model = build_model(target)
    return list(UnfinishedPlaceholderRule(QualityConfig()).check(model))


def _add_textbox(slide, text):
    box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(5), Inches(1))
    box.text_frame.text = text
    return box


def test_triggers_on_click_to_add_prompt(tmp_path):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_textbox(slide, "Click to add title")

    issues = _run(prs, tmp_path)

    assert len(issues) == 1
    assert issues[0].rule_id == RuleId.UNFINISHED_PLACEHOLDER.value
    assert issues[0].confidence == 0.9
    assert issues[0].evidence["matched_pattern"] == "click to add title"


def test_triggers_on_todo_marker(tmp_path):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_textbox(slide, "TODO: write the conclusion later")

    issues = _run(prs, tmp_path)

    assert len(issues) == 1
    assert issues[0].evidence["matched_pattern"] == "todo"


def test_triggers_on_lorem_ipsum(tmp_path):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_textbox(slide, "Lorem ipsum dolor sit amet, consectetur adipiscing elit")

    issues = _run(prs, tmp_path)

    assert len(issues) == 1
    assert issues[0].evidence["matched_pattern"] == "lorem ipsum"


def test_triggers_on_chinese_placeholder(tmp_path):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_textbox(slide, "此处输入正文内容")

    issues = _run(prs, tmp_path)

    assert len(issues) == 1
    assert issues[0].evidence["matched_pattern"] == "此处输入"


def test_clean_title_is_not_flagged(tmp_path):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_textbox(slide, "Quarterly Results 2026 Review")

    issues = _run(prs, tmp_path)

    assert issues == []


def test_real_chinese_content_is_not_flagged(tmp_path):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_textbox(slide, "本年度营收同比增长百分之十五")

    issues = _run(prs, tmp_path)

    assert issues == []
