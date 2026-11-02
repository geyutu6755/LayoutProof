"""Tests for the multi-strategy fix engine and post-fix outcome classification.

Coverage per requirement:

* text_overflow ordered fallback: enlarge box -> safe font shrink -> normAutofit;
* offslide repair: safe edge margin, deterministic collision avoidance;
* font_too_small raised to the configured minimum;
* honest resolved / unchanged / regressed / skipped outcomes on the report;
* legacy FixReport fields and JSON schema stay backward compatible;
* source bytes untouched and no content ever deleted;
* one failing repair does not abort the whole run.
"""

from __future__ import annotations

import hashlib
import io

from PIL import Image
from pptx import Presentation
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

from layoutproof.config import QualityConfig
from layoutproof.engine import scan_file
from layoutproof.fix.engine import (
    _Attempt,
    _SAFE_MARGIN_EMU,
    _choose_in_bounds_placement,
    _classify_attempts,
    _estimate_live,
    _fix_autofit_text,
    _fix_increase_font_size,
    _make_skipped,
    _try_enlarge_box,
    _try_shrink_font,
    fix_file,
)
from layoutproof.models import AppliedFix, FixReport, Issue
from layoutproof.parsing.geometry import Rect
from layoutproof.report import validate_output

# Default python-pptx canvas: 10in x 7.5in.
_SLIDE_W = 9144000
_SLIDE_H = 6858000
_BOUNDS = Rect(0, 0, _SLIDE_W, _SLIDE_H)

#: Legacy FixReport JSON keys (schema.json, additionalProperties=false).
_LEGACY_REPORT_KEYS = {
    "schema_version",
    "source_path",
    "output_path",
    "backup_path",
    "created",
    "success",
    "applied",
    "skipped",
    "before",
    "after",
    "issues_removed",
    "note",
}


def _sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        h.update(fh.read())
    return h.hexdigest()


def _add_box(slide, x, y, w, h, text, font_pt=18.0, *, wrap=True):
    box = slide.shapes.add_textbox(Emu(int(x)), Emu(int(y)), Emu(int(w)), Emu(int(h)))
    tf = box.text_frame
    tf.word_wrap = wrap
    run = tf.paragraphs[0].add_run()
    run.text = text
    run.font.size = Pt(font_pt)
    return box


def _all_text(path) -> list[str]:
    prs = Presentation(str(path))
    texts = []
    for slide in prs.slides:
        for shp in slide.shapes:
            if getattr(shp, "has_text_frame", False):
                texts.append(shp.text_frame.text)
    return sorted(texts)


def _shape_by_id(prs, shape_id: str):
    for slide in prs.slides:
        for shp in slide.shapes:
            if str(shp.shape_id) == str(shape_id):
                return shp
    return None


def _rule_shape_ids(scan, rule_id: str) -> set[str]:
    return {i.shape_id for i in scan.issues if i.rule_id == rule_id}


# ---------------------------------------------------------------------------
# End-to-end: text overflow fallback chain
# ---------------------------------------------------------------------------
def test_overflow_prefers_box_enlargement_and_preserves_content(tmp_path):
    src = tmp_path / "ov.pptx"
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    box = _add_box(
        slide,
        Inches(0.5),
        Inches(1.0),
        Inches(4.0),
        Inches(0.4),
        "Hello world line " * 12,
        18,
    )
    original_height = int(box.height)
    original_text = box.text_frame.text
    prs.save(str(src))

    before = scan_file(src, profile="core")
    target = next(i for i in before.issues if i.rule_id == "text_overflow")

    out = tmp_path / "ov.fixed.pptx"
    report = fix_file(src, output_path=out, profile="core", make_backup=False)

    actions = {a.action for a in report.applied if a.shape_id == target.shape_id}
    assert actions == {"enlarge_text_box"}
    outcome = next(o for o in report.outcomes if o.rule_id == "text_overflow")
    assert outcome.outcome == "resolved"
    assert "enlarge_text_box" in outcome.strategies

    fixed = Presentation(str(out))
    fixed_box = _shape_by_id(fixed, target.shape_id)
    assert fixed_box is not None
    assert int(fixed_box.height) > original_height
    # No content deleted: text identical before/after.
    assert fixed_box.text_frame.text == original_text

    after = scan_file(out, profile="core")
    assert target.shape_id not in _rule_shape_ids(after, "text_overflow")
    # Content preserved on every text frame.
    assert _all_text(src) == _all_text(out)


def test_overflow_falls_back_to_normautofit_when_box_cannot_grow(tmp_path):
    src = tmp_path / "af.pptx"
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    # Parked at the bottom so it cannot grow downward; font at the readable
    # floor so explicit shrinking is also unavailable -> normAutofit fallback.
    _add_box(
        slide,
        Inches(0.5),
        Inches(7.1),
        Inches(4.0),
        Inches(0.4),
        "Auto fit demo text line " * 10,
        12.0,
    )
    prs.save(str(src))

    before = scan_file(src, profile="core")
    assert any(i.rule_id == "text_overflow" for i in before.issues)
    assert not any(i.rule_id == "font_too_small" for i in before.issues)

    out = tmp_path / "af.fixed.pptx"
    report = fix_file(src, output_path=out, profile="core", make_backup=False)

    actions = {a.action for a in report.applied}
    assert "autofit_text" in actions
    assert "enlarge_text_box" not in actions
    assert "shrink_text_font" not in actions
    outcome = next(o for o in report.outcomes if o.rule_id == "text_overflow")
    assert outcome.outcome == "resolved"

    after = scan_file(out, profile="core")
    assert not any(i.rule_id == "text_overflow" for i in after.issues)
    assert not any(i.rule_id == "font_too_small" for i in after.issues)
    assert _all_text(src) == _all_text(out)


# ---------------------------------------------------------------------------
# End-to-end: offslide margin + collision avoidance
# ---------------------------------------------------------------------------
def test_offslide_repair_keeps_a_safe_margin(tmp_path):
    src = tmp_path / "off.pptx"
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    off = _add_box(slide, Inches(11.5), Inches(1.0), Inches(2.0), Inches(0.3), "offscreen note")
    off_id = str(off.shape_id)
    prs.save(str(src))

    before = scan_file(src, profile="core")
    assert off_id in _rule_shape_ids(before, "offslide_object")

    out = tmp_path / "off.fixed.pptx"
    report = fix_file(src, output_path=out, profile="core", make_backup=False)
    assert any(a.action == "move_into_slide" for a in report.applied)
    outcome = next(o for o in report.outcomes if o.shape_id == off_id)
    assert outcome.outcome == "resolved"

    fixed = Presentation(str(out))
    shp = _shape_by_id(fixed, off_id)
    assert shp.left >= _SAFE_MARGIN_EMU
    assert shp.left + shp.width <= _SLIDE_W - _SAFE_MARGIN_EMU
    after = scan_file(out, profile="core")
    assert off_id not in _rule_shape_ids(after, "offslide_object")


def test_offslide_repair_avoids_collision_when_a_slot_exists(tmp_path):
    src = tmp_path / "col.pptx"
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    # Obstacle occupies the naive clamped slot.
    obstacle = _add_box(slide, Inches(7.9), Inches(1.0), Inches(2.0), Inches(1.0), "obstacle card")
    off = _add_box(slide, Inches(11.5), Inches(1.0), Inches(2.0), Inches(0.3), "offscreen note")
    off_id, obstacle_id = str(off.shape_id), str(obstacle.shape_id)
    prs.save(str(src))

    out = tmp_path / "col.fixed.pptx"
    fix_file(src, output_path=out, profile="core", make_backup=False)

    fixed = Presentation(str(out))
    a = _shape_by_id(fixed, off_id)
    b = _shape_by_id(fixed, obstacle_id)
    rect_a = Rect(int(a.left), int(a.top), int(a.width), int(a.height))
    rect_b = Rect(int(b.left), int(b.top), int(b.width), int(b.height))
    assert rect_a.intersection(rect_b) is None


# ---------------------------------------------------------------------------
# End-to-end: font minimum + classification + legacy compatibility
# ---------------------------------------------------------------------------
def test_font_size_raised_to_configured_minimum(tmp_path):
    src = tmp_path / "font.pptx"
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_box(slide, Inches(0.6), Inches(0.5), Inches(4.0), Inches(0.8), "too small body", 8.0)
    prs.save(str(src))

    out = tmp_path / "font.fixed.pptx"
    report = fix_file(src, output_path=out, profile="core", make_backup=False)
    assert any(a.action == "increase_font_size" for a in report.applied)

    after = scan_file(out, profile="core")
    assert not any(i.rule_id == "font_too_small" for i in after.issues)
    fixed = Presentation(str(out))
    sizes = [
        r.font.size.pt
        for s in fixed.slides[0].shapes
        if getattr(s, "has_text_frame", False)
        for p in s.text_frame.paragraphs
        for r in p.runs
        if r.font.size is not None
    ]
    assert min(sizes) >= QualityConfig().min_font_size_pt
    outcome = next(o for o in report.outcomes if o.rule_id == "font_too_small")
    assert outcome.outcome == "resolved"


def test_classification_reports_resolved_vs_manual_review(tmp_path):
    src = tmp_path / "mix.pptx"
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    # One repairable ERROR finding.
    _add_box(slide, Inches(11.5), Inches(1.0), Inches(2.0), Inches(0.5), "outside")
    # Two overlapping text boxes -> object_overlap has no automatic repair.
    _add_box(slide, Inches(1.0), Inches(1.0), Inches(3.0), Inches(1.0), "box alpha content")
    _add_box(slide, Inches(2.0), Inches(1.1), Inches(3.0), Inches(1.0), "box beta content here")
    prs.save(str(src))

    out = tmp_path / "mix.fixed.pptx"
    report = fix_file(src, output_path=out, profile="full", make_backup=False)

    assert report.resolved_count >= 1
    assert report.manual_review_count >= 1
    assert isinstance(report, FixReport)
    outcomes_by_rule = {o.rule_id: o.outcome for o in report.outcomes}
    assert outcomes_by_rule["offslide_object"] == "resolved"
    assert outcomes_by_rule["object_overlap"] == "skipped"

    # Legacy dictionary contract: same keys, no additions; schema still valid.
    data = report.to_dict()
    assert set(data) == _LEGACY_REPORT_KEYS
    assert validate_output(data) == "FixReport"
    assert len(data["applied"]) == len(report.applied)
    assert len(data["skipped"]) == len(report.skipped)


def test_failing_repair_does_not_abort_run(tmp_path, monkeypatch):
    from layoutproof.fix import engine as eng

    def _boom(*_args, **_kwargs):
        raise RuntimeError("synthetic repair failure")

    monkeypatch.setattr(eng, "_fix_increase_font_size", _boom)

    src = tmp_path / "mixed.pptx"
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_box(slide, Inches(0.6), Inches(0.5), Inches(4.0), Inches(0.8), "tiny body", 8.0)
    _add_box(slide, Inches(11.5), Inches(1.0), Inches(2.0), Inches(0.5), "outside box")
    prs.save(str(src))

    out = tmp_path / "mixed.fixed.pptx"
    report = fix_file(src, output_path=out, profile="core", make_backup=False)

    assert report.created
    # The crashing repair was recorded as skipped; the sibling repair ran.
    assert any(a.rule_id == "font_too_small" and a.status == "skipped" for a in report.skipped)
    assert any(a.action == "move_into_slide" for a in report.applied)
    font_outcome = [o for o in report.outcomes if o.rule_id == "font_too_small"]
    assert font_outcome and font_outcome[0].outcome == "skipped"


def test_blank_slide_is_recorded_as_manual_review(tmp_path):
    src = tmp_path / "blank.pptx"
    prs = Presentation()
    prs.slides.add_slide(prs.slide_layouts[6])  # empty: blank_slide warning
    prs.save(str(src))

    out = tmp_path / "blank.fixed.pptx"
    report = fix_file(src, output_path=out, profile="full", make_backup=False)

    # No fabricated repair: blank slides stay on the manual-review list.
    assert any(s.rule_id == "blank_slide" and s.status == "skipped" for s in report.skipped)
    assert not any(a.rule_id == "blank_slide" for a in report.applied)
    outcome = [o for o in report.outcomes if o.rule_id == "blank_slide"]
    assert outcome and outcome[0].outcome == "skipped"
    # The run still produces a valid new deck rather than aborting.
    assert report.created
    assert Presentation(str(out)) is not None


def test_missing_alt_text_is_recorded_as_manual_review(tmp_path):
    src = tmp_path / "alt.pptx"
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    buffer = io.BytesIO()
    Image.new("RGB", (24, 24), (200, 30, 30)).save(buffer, format="PNG")
    picture = slide.shapes.add_picture(
        io.BytesIO(buffer.getvalue()),
        Inches(1),
        Inches(1),
        width=Inches(2),
        height=Inches(2),
    )
    cnv = picture._element.find(".//" + qn("p:cNvPr"))
    if cnv is not None:
        cnv.attrib.pop("descr", None)
    prs.save(str(src))
    before_hash = _sha256(src)

    out = tmp_path / "alt.fixed.pptx"
    report = fix_file(src, output_path=out, profile="full", make_backup=False)

    assert any(s.rule_id == "missing_alt_text" and s.status == "skipped" for s in report.skipped)
    assert not any(a.rule_id == "missing_alt_text" for a in report.applied)
    outcome = [o for o in report.outcomes if o.rule_id == "missing_alt_text"]
    assert outcome and outcome[0].outcome == "skipped"
    assert _sha256(src) == before_hash


def test_outcome_groups_and_unknown_label_rejected(tmp_path):
    import pytest

    from layoutproof.fix.outcomes import FixOutcome

    src = tmp_path / "grp.pptx"
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_box(slide, Inches(11.5), Inches(1.0), Inches(2.0), Inches(0.5), "outside")
    prs.save(str(src))
    report = fix_file(
        src, output_path=tmp_path / "grp.fixed.pptx", profile="core", make_backup=False
    )
    grouped = report.outcomes_by_status()
    assert grouped["resolved"] and not grouped["regressed"]
    assert report.resolved_count == len(grouped["resolved"])
    with pytest.raises(ValueError):
        FixOutcome(
            rule_id="x", slide_index=0, shape_id=None, action="a", status="applied", outcome="bogus"
        )


def test_source_bytes_unchanged_and_output_is_new_file(tmp_path):
    src = tmp_path / "keep.pptx"
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_box(slide, Inches(11.5), Inches(1.0), Inches(2.0), Inches(0.5), "outside")
    prs.save(str(src))
    before_hash = _sha256(src)

    out = tmp_path / "keep.fixed.pptx"
    report = fix_file(src, output_path=out, profile="core", make_backup=False)
    assert report.created
    assert _sha256(src) == before_hash
    assert out.exists()
    assert out.resolve() != src.resolve()
    assert "[manual]" not in " ".join(a.note for a in report.applied)


# ---------------------------------------------------------------------------
# Direct strategy helpers: positive + negative controls
# ---------------------------------------------------------------------------
def _live_box(x, y, w, h, text, font_pt=18.0):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    return slide, _add_box(slide, x, y, w, h, text, font_pt)


def test_enlarge_box_strategy_positive():
    _slide, box = _live_box(
        Inches(0.5), Inches(1.0), Inches(4.0), Inches(0.4), "Hello world line " * 12, 18
    )
    ok, delta = _try_enlarge_box(box, _BOUNDS, 0.15)
    assert ok is True and delta > 0
    assert _fits(box)


def test_enlarge_box_strategy_negative_when_no_room():
    _slide, box = _live_box(
        Inches(0.5), Inches(7.1), Inches(4.0), Inches(0.4), "Auto fit demo text line " * 10, 12
    )
    old_h = int(box.height)
    ok, delta = _try_enlarge_box(box, _BOUNDS, 0.15)
    assert ok is False and delta == 0
    assert int(box.height) == old_h  # reverted / untouched


def _fits(box) -> bool:
    est = _estimate_live(box)
    return est is not None and est[1] <= est[2] * 1.15


def test_shrink_font_strategy_positive_never_below_minimum():
    _slide, box = _live_box(
        Inches(0.5),
        Inches(7.1),
        Inches(4.0),
        Inches(0.4),
        "Shrink me short demo text line okay now",
        24.0,
    )
    config = QualityConfig(min_font_size_pt=12.0)
    ok, changed = _try_shrink_font(box, config, 0.15)
    assert ok is True and changed > 0
    sizes = [r.font.size.pt for p in box.text_frame.paragraphs for r in p.runs]
    assert min(sizes) >= 12.0
    assert _fits(box)


def test_shrink_font_strategy_negative_at_floor():
    _slide, box = _live_box(
        Inches(0.5),
        Inches(7.1),
        Inches(4.0),
        Inches(0.4),
        "Shrink me short demo text line okay now",
        12.0,
    )
    before_sizes = [r.font.size.pt for p in box.text_frame.paragraphs for r in p.runs]
    config = QualityConfig(min_font_size_pt=12.0)
    ok, changed = _try_shrink_font(box, config, 0.15)
    assert ok is False and changed == 0
    after_sizes = [r.font.size.pt for p in box.text_frame.paragraphs for r in p.runs]
    assert after_sizes == before_sizes


def test_autofit_strategy_negative_on_non_text_shape():
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    issue = Issue(rule_id="text_overflow", slide_index=0, shape_id="1")
    assert _fix_autofit_text(slide, issue) is None


def test_placement_helper_prefers_free_slot_and_respects_margin():
    inner = Rect(
        _SAFE_MARGIN_EMU,
        _SAFE_MARGIN_EMU,
        _SLIDE_W - 2 * _SAFE_MARGIN_EMU,
        _SLIDE_H - 2 * _SAFE_MARGIN_EMU,
    )
    old = Rect(int(Inches(11.5)), int(Inches(1.0)), int(Inches(2.0)), int(Inches(0.3)))
    obstacle = Rect(int(Inches(7.9)), int(Inches(1.0)), int(Inches(2.0)), int(Inches(1.0)))
    rect, free, note = _choose_in_bounds_placement(old, inner, [obstacle])
    assert free is True
    assert rect.x >= inner.x and rect.right <= inner.right
    assert rect.intersection(obstacle) is None
    assert note


def test_placement_helper_honest_when_shape_larger_than_slide():
    inner = Rect(
        _SAFE_MARGIN_EMU,
        _SAFE_MARGIN_EMU,
        _SLIDE_W - 2 * _SAFE_MARGIN_EMU,
        _SLIDE_H - 2 * _SAFE_MARGIN_EMU,
    )
    old = Rect(int(Inches(11.5)), int(Inches(1.0)), int(Inches(12.0)), int(Inches(1.0)))
    rect, free, note = _choose_in_bounds_placement(old, inner, [])
    # Geometry is never shrunk; oversized cases must be flagged for review.
    assert rect.width == old.width
    assert not free
    assert "manual" in note


def test_increase_font_size_negative_when_runs_already_at_minimum():
    _slide, box = _live_box(
        Inches(0.5),
        Inches(1.0),
        Inches(4.0),
        Inches(0.6),
        "already readable body text",
        12.0,
    )
    issue = Issue(rule_id="font_too_small", slide_index=0, shape_id="1")
    result = _fix_increase_font_size(box, QualityConfig(min_font_size_pt=12.0), issue)
    assert result is None
    sizes = [r.font.size.pt for p in box.text_frame.paragraphs for r in p.runs]
    assert sizes == [12.0]


def test_classifier_labels_resolved_unchanged_regressed_skipped():
    i_res = Issue("offslide_object", slide_index=0, shape_id="1")
    i_unchanged = Issue("font_too_small", slide_index=0, shape_id="2")
    i_regressed = Issue("text_overflow", slide_index=0, shape_id="3")
    i_skipped = Issue("object_overlap", slide_index=0, shape_id="4")

    attempts = [
        _Attempt(
            issue=i_res,
            status="applied",
            fix=AppliedFix("offslide_object", "1", "move_into_slide"),
            strategies=["move_into_slide"],
        ),
        _Attempt(
            issue=i_unchanged,
            status="applied",
            fix=AppliedFix("font_too_small", "2", "increase_font_size"),
            strategies=["increase_font_size"],
        ),
        _Attempt(
            issue=i_regressed,
            status="applied",
            fix=AppliedFix("text_overflow", "3", "enlarge_text_box"),
            strategies=["enlarge_text_box"],
        ),
        _Attempt(
            issue=i_skipped,
            status="skipped",
            record=_make_skipped(i_skipped, "manual_review", "no automatic strategy"),
            reason="no automatic strategy",
        ),
    ]
    before = [i_res, i_unchanged, i_regressed, i_skipped]
    after = [
        i_unchanged,  # repair did not resolve this target
        Issue("object_overlap", slide_index=0, shape_id="3"),  # new issue on repaired shape
    ]

    outcomes, counts = _classify_attempts(attempts, before, after)
    labels = {(o.rule_id, o.shape_id): o.outcome for o in outcomes}
    assert labels[("offslide_object", "1")] == "resolved"
    assert labels[("font_too_small", "2")] == "unchanged"
    assert labels[("text_overflow", "3")] == "regressed"
    assert labels[("object_overlap", "4")] == "skipped"
    assert counts == {"resolved": 1, "unchanged": 1, "regressed": 1, "skipped": 1}
    # The regressed record explains the newly introduced issue honestly.
    regressed = next(o for o in outcomes if o.rule_id == "text_overflow")
    assert "object_overlap" in regressed.reason
