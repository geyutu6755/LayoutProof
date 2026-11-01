"""Unit tests for the cjk_typography rule."""

from __future__ import annotations

from pptx import Presentation
from pptx.util import Inches

from layoutproof.config import QualityConfig
from layoutproof.parsing import build_model
from layoutproof.rules.cjk import CjkTypographyRule


def _add_text(slide, lines: list[str]):
    box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(6), Inches(2))
    tf = box.text_frame
    for i, line in enumerate(lines):
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.text = line
    return box


def _run_rule(prs, path):
    prs.save(str(path))
    model = build_model(str(path), QualityConfig())
    return list(CjkTypographyRule(QualityConfig()).check(model))


def test_cjk_typography_positive_and_negative(tmp_path):
    prs = Presentation()

    # positive: half-width comma, ASCII space between CJK and latin,
    # and a paragraph opening with a forbidden closing punctuation
    s1 = prs.slides.add_slide(prs.slide_layouts[6])
    _add_text(
        s1,
        ["你好,世界。", "、行首不应出现标点。", "这是 中文 ABC 排版示例。"],
    )

    # negative: clean Chinese, full-width punctuation, no stray spaces
    s2 = prs.slides.add_slide(prs.slide_layouts[6])
    _add_text(s2, ["你好，世界。这是正常的中文排版。"])

    # negative: no CJK at all
    s3 = prs.slides.add_slide(prs.slide_layouts[6])
    _add_text(s3, ["Hello world 123"])

    issues = _run_rule(prs, tmp_path / "cjk.pptx")

    assert len(issues) == 1
    issue = issues[0]
    assert issue.rule_id == "cjk_typography"
    assert issue.slide_index == 0
    assert issue.confidence == 0.75
    hits = set(issue.evidence["hit_types"])
    assert hits == {"kinsoku_line_start", "cjk_latin_space", "halfwidth_punct"}
    assert issue.evidence["line_start_forbidden"]
