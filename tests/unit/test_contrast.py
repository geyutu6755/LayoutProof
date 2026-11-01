"""Unit tests for the low_contrast rule."""

from __future__ import annotations

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

from layoutproof.config import QualityConfig
from layoutproof.parsing import build_model
from layoutproof.rules.contrast import LowContrastRule, contrast_ratio


GRAY = RGBColor(0x99, 0x99, 0x99)
DARK = RGBColor(0x00, 0x00, 0x00)
MID = RGBColor(0x88, 0x88, 0x88)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)


def _add_text(slide, text, size_pt, color):
    box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(6), Inches(1))
    tf = box.text_frame
    run = tf.paragraphs[0].add_run()
    run.text = text
    run.font.size = Pt(size_pt)
    run.font.color.rgb = color
    return box


def _run_rule(prs, path):
    prs.save(str(path))
    model = build_model(str(path), QualityConfig())
    return list(LowContrastRule(QualityConfig()).check(model))


def test_contrast_math():
    # black on white == 21:1 (WCAG reference)
    assert abs(contrast_ratio("000000", "FFFFFF") - 21.0) < 0.01
    # gray 999 on white ≈ 2.85:1, below 4.5 but also below 3.0
    ratio = contrast_ratio("999999", "FFFFFF")
    assert ratio is not None
    assert 2.8 < ratio < 3.0


def test_low_contrast_positive_and_negative(tmp_path):
    prs = Presentation()

    # positive 1: small gray text on explicit solid white (normal threshold 4.5)
    s1 = prs.slides.add_slide(prs.slide_layouts[6])
    s1.background.fill.solid()
    s1.background.fill.fore_color.rgb = WHITE
    _add_text(s1, "灰色小字", 12, GRAY)

    # positive 2: large gray text on solid white (large threshold 3.0)
    s2 = prs.slides.add_slide(prs.slide_layouts[6])
    s2.background.fill.solid()
    s2.background.fill.fore_color.rgb = WHITE
    _add_text(s2, "灰色大字", 24, GRAY)

    # negative 1: black 24pt on white passes even the large threshold
    s3 = prs.slides.add_slide(prs.slide_layouts[6])
    s3.background.fill.solid()
    s3.background.fill.fore_color.rgb = WHITE
    _add_text(s3, "黑色大字", 24, DARK)

    # negative 2: unknown background -> fail open, never reported
    s4 = prs.slides.add_slide(prs.slide_layouts[6])
    _add_text(s4, "默认背景灰字", 12, GRAY)

    # positive 3: shape-fill basis (text on its own solid gray box, ratio 1:1)
    s5 = prs.slides.add_slide(prs.slide_layouts[6])
    box = _add_text(s5, "同色填充", 12, MID)
    box.fill.solid()
    box.fill.fore_color.rgb = MID

    issues = _run_rule(prs, tmp_path / "contrast.pptx")

    assert len(issues) == 3
    slide_idx = sorted(i.slide_index for i in issues)
    assert slide_idx == [0, 1, 4]

    for issue in issues:
        assert issue.rule_id == "low_contrast"
        assert issue.confidence == 0.8

    bases = {i.evidence["basis"] for i in issues}
    assert bases == {"slide_bg", "shape_fill"}

    # the two slide-bg findings both report white as background
    slide_bg_issues = [i for i in issues if i.evidence["basis"] == "slide_bg"]
    assert all(i.evidence["background"] == "FFFFFF" for i in slide_bg_issues)
    # large text uses 3.0 threshold, small uses 4.5
    thresholds = {r["threshold"] for i in slide_bg_issues for r in i.evidence["bad_runs"]}
    assert thresholds == {4.5, 3.0}
