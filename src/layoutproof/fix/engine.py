"""Safe, offline automatic fix engine.

Closes the loop  detect -> locate -> fix -> re-verify  without ever touching
the source file.  Repairable rules use an ordered, safe fallback strategy
chain: the first strategy that can be applied without deleting content wins,
and strategies that cannot act safely are recorded as skipped instead of being
fabricated away.

* ``text_overflow`` -> enlarge text box -> explicit font shrink (never below
  the configured readable minimum) -> ``normAutofit`` catch-all.
* ``offslide_object`` -> move fully inside the slide with a small edge margin,
  choosing a collision-free slot when one exists deterministically.
* ``font_too_small`` -> raise explicit runs to the configured minimum.
* ``low_contrast`` / ``unfinished_placeholder`` / ``cjk_typography`` keep
  their dedicated repairs.

Rules without a safe automatic repair (object overlap, blank slides, broken
media / references, structural anomalies, missing alt text) stay on the
manual-review list.  After the output deck is re-scanned every targeted issue
is classified as ``resolved`` / ``unchanged`` / ``regressed`` / ``skipped``
and exposed on the report's additive outcome fields.
"""

from __future__ import annotations

import hashlib
import math
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_COLOR_TYPE, MSO_FILL
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.enum.text import MSO_AUTO_SIZE
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

from ..config import QualityConfig
from ..engine import scan_file
from ..models import RULES, AppliedFix, FixReport, Issue
from ..parsing.geometry import Rect, emu_to_pt, pt_to_emu
from ..rules.contrast import contrast_ratio
from ..rules.text_overflow import (
    _FRAME_PADDING_PT,
    _GLYPH_WIDTH_FRACTION,
    _HORIZONTAL_PADDING_PT,
    _LINE_LEADING,
)
from .outcomes import (
    REGRESSED,
    RESOLVED,
    SKIPPED,
    UNCHANGED,
    DetailedFixReport,
    FixOutcome,
)

# ---------------------------------------------------------------------------
# Geometry safety constants
# ---------------------------------------------------------------------------
#: Small inset kept between a repaired shape and the slide edge (0.1 inch).
_SAFE_MARGIN_EMU = int(Inches(0.1))
_SAFE_MARGIN_IN = 0.1

# ---------------------------------------------------------------------------
# CJK normalisation primitives (mechanical only: spacing + half-width punctuation)
# ---------------------------------------------------------------------------
_CJK_CLASS = r"㐀-䶿一-鿿"
_CJK_LATIN_SPACE_RE = re.compile(
    rf"(?<=[{_CJK_CLASS}])[ \t]+(?=[A-Za-z0-9])"
    rf"|(?<=[A-Za-z0-9])[ \t]+(?=[{_CJK_CLASS}])"
)
_CJK_RE = re.compile(rf"[{_CJK_CLASS}]")
_HALFWIDTH_TO_FULLWIDTH = {
    ",": "，",
    ";": "；",
    ":": "：",
    "!": "！",
    "?": "？",
    "(": "（",
    ")": "）",
}


def _normalize_cjk_text(text: str) -> str:
    """Mechanical CJK typography normalisation.

    Removes ASCII spaces between CJK and Latin/digit characters and converts
    half-width punctuation adjacent to CJK text to its full-width form.  It
    deliberately does *not* attempt kinsoku reflow, which needs a line breaker.
    """
    if not text or not _CJK_RE.search(text):
        return text
    text = _CJK_LATIN_SPACE_RE.sub("", text)
    # Half-width punctuation immediately after a CJK character.
    text = re.sub(
        rf"([{_CJK_CLASS}])([,;:!?()])",
        lambda m: m.group(1) + _HALFWIDTH_TO_FULLWIDTH[m.group(2)],
        text,
    )
    # Half-width punctuation immediately before a CJK character.
    text = re.sub(
        rf"([,;:!?()])([{_CJK_CLASS}])",
        lambda m: _HALFWIDTH_TO_FULLWIDTH[m.group(1)] + m.group(2),
        text,
    )
    # Period only when it is not a decimal point (digits on both sides).
    text = re.sub(rf"([{_CJK_CLASS}])\.(?![0-9])", r"\1。", text)
    text = re.sub(rf"(?<![0-9])\.([{_CJK_CLASS}])", r"。\1", text)
    return text


# ---------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------
def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _iter_shapes(shapes):
    """Yield every shape, descending into group shapes."""
    for shp in shapes:
        yield shp
        try:
            if shp.shape_type == MSO_SHAPE_TYPE.GROUP:
                yield from _iter_shapes(shp.shapes)
        except Exception:
            continue


def _build_shape_maps(prs) -> list[dict[str, object]]:
    """Map ``{shape_id: shape}`` per slide index, matching the parsed model."""
    out: list[dict[str, object]] = []
    for slide in prs.slides:
        table: dict[str, object] = {}
        for shp in _iter_shapes(slide.shapes):
            try:
                table[str(shp.shape_id)] = shp
            except Exception:
                continue
        out.append(table)
    return out


def _shape_solid_fill(shape) -> str | None:
    try:
        fill = shape.fill
        if fill.type == MSO_FILL.SOLID:
            return str(fill.fore_color.rgb)
    except Exception:
        pass
    return None


def _slide_solid_bg(slide) -> str | None:
    try:
        fill = slide.background.fill
        if fill.type == MSO_FILL.SOLID:
            return str(fill.fore_color.rgb)
    except Exception:
        pass
    return None


def _is_live_decorative(shape) -> bool:
    """True when the live OOXML element carries the ``p:decorative`` flag."""
    try:
        return bool(shape._element.findall(".//" + qn("p:decorative")))
    except Exception:
        return False


def _issue_key(issue: Issue) -> tuple[str, int, str]:
    """Stable identity of a finding across the before/after scans."""
    return (issue.rule_id, issue.slide_index, issue.shape_id or "")


# ---------------------------------------------------------------------------
# Strategy 1 (off-slide): margin-aware, collision-aware repositioning
# ---------------------------------------------------------------------------
def _collect_obstacles(slide, self_id: str) -> list[Rect]:
    """Top-level non-decorative rectangles used for deterministic avoidance."""
    obstacles: list[Rect] = []
    for shp in slide.shapes:
        try:
            if str(shp.shape_id) == self_id:
                continue
            if getattr(shp, "shape_type", None) == MSO_SHAPE_TYPE.GROUP:
                continue  # child coordinates are group-local; skip safely
            if _is_live_decorative(shp):
                continue
            left, top, width, height = shp.left, shp.top, shp.width, shp.height
            if None in (left, top, width, height):
                continue
            obstacles.append(Rect(int(left), int(top), int(width), int(height)))
        except Exception:
            continue
    return obstacles


def _choose_in_bounds_placement(
    old: Rect, inner: Rect, obstacles: list[Rect]
) -> tuple[Rect, bool, str]:
    """Return ``(rect, collision_free, note)`` inside ``inner``.

    Prefers the minimal movement that does not intersect another object; falls
    back to the minimal clamp when no free slot exists deterministically.
    """
    width, height = old.width, old.height

    def clamped(x: int, y: int) -> Rect:
        cx = min(max(x, inner.x), max(inner.x, inner.right - width))
        cy = min(max(y, inner.y), max(inner.y, inner.bottom - height))
        return Rect(cx, cy, width, height)

    base = clamped(old.x, old.y)

    def overlap_area(rect: Rect) -> int:
        total = 0
        for obs in obstacles:
            inter = rect.intersection(obs)
            if inter is not None:
                total += inter.area
        return total

    candidates = [base]
    for step in (1, 2, 3, 4):
        delta = step * _SAFE_MARGIN_EMU
        candidates.extend(
            [
                Rect(base.x + delta, base.y, width, height),
                Rect(base.x - delta, base.y, width, height),
                Rect(base.x, base.y + delta, width, height),
                Rect(base.x, base.y - delta, width, height),
            ]
        )

    best: tuple[int, int, int, int, Rect] | None = None
    for cand in candidates:
        if cand.x < inner.x or cand.right > inner.right:
            continue
        if cand.y < inner.y or cand.bottom > inner.bottom:
            continue
        inter = overlap_area(cand)
        score = (inter, abs(cand.x - old.x) + abs(cand.y - old.y), cand.x, cand.y)
        if inter == 0 and (best is None or score[:4] < best[:4]):
            best = (*score, cand)

    if best is not None:
        chosen = best[4]
        if chosen.x == base.x and chosen.y == base.y:
            return chosen, True, "inside safe margin, no collision"
        return chosen, True, "collision-free placement chosen"
    return (
        base,
        False,
        (
            "no collision-free slot inside margin; minimal clamp applied "
            "(manual overlap review recommended)"
        ),
    )


def _fix_move_into_slide(shape, slide, bounds: Rect, issue: Issue) -> AppliedFix | None:
    left, top, width, height = shape.left, shape.top, shape.width, shape.height
    if None in (left, top, width, height):
        return None
    old = Rect(int(left), int(top), int(width), int(height))
    inner = Rect(
        _SAFE_MARGIN_EMU,
        _SAFE_MARGIN_EMU,
        max(0, bounds.width - 2 * _SAFE_MARGIN_EMU),
        max(0, bounds.height - 2 * _SAFE_MARGIN_EMU),
    )
    obstacles = _collect_obstacles(slide, str(shape.shape_id))
    new, _free, placement_note = _choose_in_bounds_placement(old, inner, obstacles)

    if new.x == old.x and new.y == old.y and old.fraction_outside(bounds) == 0.0:
        return AppliedFix(
            rule_id=issue.rule_id,
            shape_id=issue.shape_id,
            action="move_into_slide",
            note="already within slide bounds",
        )

    shape.left = Emu(new.x)
    shape.top = Emu(new.y)
    note = (
        f"moved inside slide with {_SAFE_MARGIN_IN:g}in edge margin "
        f"({placement_note}); x={new.x} y={new.y}"
    )
    if width > inner.width or height > inner.height:
        note += "; shape larger than slide inner area, manual resize recommended"
    return AppliedFix(
        rule_id=issue.rule_id,
        shape_id=issue.shape_id,
        action="move_into_slide",
        note=note,
    )


# ---------------------------------------------------------------------------
# Strategy 2 (font size): raise explicit runs to the configured minimum
# ---------------------------------------------------------------------------
def _fix_increase_font_size(shape, config: QualityConfig, issue: Issue) -> AppliedFix | None:
    if not getattr(shape, "has_text_frame", False):
        return None
    minimum = float(config.min_font_size_pt)
    changed = 0
    for para in shape.text_frame.paragraphs:
        for run in para.runs:
            if run.font.size is None:
                continue
            if run.font.size.pt < minimum:
                run.font.size = Pt(minimum)
                changed += 1
    if not changed:
        return None
    return AppliedFix(
        rule_id=issue.rule_id,
        shape_id=issue.shape_id,
        action="increase_font_size",
        note=f"raised {changed} run(s) to minimum {minimum:g}pt",
    )


# ---------------------------------------------------------------------------
# Strategy 3 (text overflow): ordered safe fallback chain
# ---------------------------------------------------------------------------
def _estimate_live(shape) -> tuple[int, float, float, float] | None:
    """Mirror the offline overflow heuristic for a live python-pptx shape.

    Returns ``(estimated_lines, needed_height_pt, box_height_pt, font_pt)``
    or ``None`` when the shape has no explicit font size / geometry.
    """
    if None in (shape.left, shape.top, shape.width, shape.height):
        return None
    tf = shape.text_frame
    sizes = [
        run.font.size.pt for para in tf.paragraphs for run in para.runs if run.font.size is not None
    ]
    if not sizes:
        return None
    font_pt = max(sizes)
    box_w_pt = emu_to_pt(int(shape.width))
    usable_w_pt = max(1.0, box_w_pt - _HORIZONTAL_PADDING_PT)
    chars_per_line = max(1.0, usable_w_pt / (font_pt * _GLYPH_WIDTH_FRACTION))
    wraps = tf.word_wrap is not False
    total_lines = 0
    for para in tf.paragraphs:
        text = "".join(run.text for run in para.runs).strip()
        if not text:
            continue
        total_lines += 1 if not wraps else math.ceil(len(text) / chars_per_line)
    if total_lines == 0:
        return None
    needed_pt = total_lines * font_pt * _LINE_LEADING + _FRAME_PADDING_PT
    box_h_pt = emu_to_pt(int(shape.height))
    return total_lines, needed_pt, box_h_pt, font_pt


def _fits_after(estimate: tuple[int, float, float, float] | None, threshold: float) -> bool:
    if estimate is None:
        return False
    _, needed, box_h, _ = estimate
    return needed <= box_h * (1.0 + threshold)


def _try_enlarge_box(
    shape, bounds: Rect, threshold: float, obstacles: list[Rect] | None = None
) -> tuple[bool, int]:
    """Strategy A: grow the frame height downward inside the safe margin.

    Growth never pushes the frame into another content shape: the usable
    downward extent is capped by the nearest obstacle top (plus a small gap).
    When a collision would be unavoidable the growth is reverted and the
    caller falls back to the next strategy.
    """
    obstacles = obstacles or []
    estimate = _estimate_live(shape)
    if estimate is None:
        return False, 0
    _, needed, _, _ = estimate
    if _fits_after(estimate, threshold):
        return False, 0
    target_emu = pt_to_emu(needed + 1.0)
    max_bottom = bounds.bottom - _SAFE_MARGIN_EMU
    top = int(shape.top)
    old_h = int(shape.height)
    max_h = max(0, max_bottom - top)
    if max_h <= old_h:
        return False, 0
    new_h = min(target_emu, max_h)
    # Cap height so the grown frame does not intersect another shape.
    cand = Rect(int(shape.left), top, int(shape.width), new_h)
    for obs in obstacles:
        if cand.intersection(obs) is not None:
            allowed = max(0, obs.y - top - _SAFE_MARGIN_EMU)
            new_h = min(new_h, allowed)
    if new_h <= old_h:
        return False, 0
    shape.height = Emu(new_h)
    if _fits_after(_estimate_live(shape), threshold):
        return True, int(shape.height) - old_h
    shape.height = Emu(old_h)  # revert: not effective, hand over to the next strategy
    return False, 0


def _try_shrink_font(shape, config: QualityConfig, threshold: float) -> tuple[bool, int]:
    """Strategy B: step explicit sizes down, never below the readable minimum."""
    tf = shape.text_frame
    entries = [run for para in tf.paragraphs for run in para.runs if run.font.size is not None]
    if not entries:
        return False, 0
    original = [(run, run.font.size.pt) for run in entries]
    floor = float(config.min_font_size_pt)
    if max(size for _, size in original) <= floor:
        return False, 0
    changed = 0
    for _ in range(24):  # bounded deterministic loop; never deletes content
        current_max = max(run.font.size.pt for run in entries)
        if current_max <= floor:
            break
        for run in entries:
            size = run.font.size.pt
            if size > floor:
                new_size = max(floor, size - 1.0)
                if new_size != size:
                    run.font.size = Pt(new_size)
                    changed += 1
        if _fits_after(_estimate_live(shape), threshold):
            break
        if max(run.font.size.pt for run in entries) <= floor + 1e-9:
            break
    if changed and _fits_after(_estimate_live(shape), threshold):
        return True, changed
    for run, size in original:  # revert ineffective shrink
        run.font.size = Pt(size)
    return False, 0


def _fix_autofit_text(shape, issue: Issue) -> AppliedFix | None:
    """Strategy C: normAutofit lets PowerPoint shrink text itself; no deletion."""
    if not getattr(shape, "has_text_frame", False):
        return None
    tf = shape.text_frame
    tf.word_wrap = True
    # TEXT_TO_FIT_SHAPE writes <a:normAutofit/> so PowerPoint shrinks the text
    # itself; we never delete content.
    tf.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
    return AppliedFix(
        rule_id=issue.rule_id,
        shape_id=issue.shape_id,
        action="autofit_text",
        note="enabled word_wrap + normAutofit (text-to-fit-shape)",
    )


def _fix_text_overflow(
    shape, slide, bounds: Rect, config: QualityConfig, issue: Issue
) -> tuple[AppliedFix | None, list[str], list[str]]:
    """Ordered fallback chain; returns ``(fix, applied_strategies, unavailable)``."""
    if not getattr(shape, "has_text_frame", False):
        return None, [], ["enlarge_text_box", "shrink_text_font", "autofit_text"]
    threshold = float(config.overflow_ratio_threshold)
    obstacles = _collect_obstacles(slide, str(shape.shape_id))
    applied_strategies: list[str] = []
    unavailable: list[str] = []

    ok, delta = _try_enlarge_box(shape, bounds, threshold, obstacles)
    if ok:
        applied_strategies.append("enlarge_text_box")
        return (
            AppliedFix(
                rule_id=issue.rule_id,
                shape_id=issue.shape_id,
                action="enlarge_text_box",
                note=f"grew text frame height by {delta} EMU to fit estimated text",
            ),
            applied_strategies,
            unavailable,
        )
    unavailable.append("enlarge_text_box")

    ok, changed = _try_shrink_font(shape, config, threshold)
    if ok:
        applied_strategies.append("shrink_text_font")
        return (
            AppliedFix(
                rule_id=issue.rule_id,
                shape_id=issue.shape_id,
                action="shrink_text_font",
                note=(
                    f"shrank {changed} run(s) stepwise to >= "
                    f"{config.min_font_size_pt:g}pt without deleting content"
                ),
            ),
            applied_strategies,
            unavailable,
        )
    unavailable.append("shrink_text_font")

    fix = _fix_autofit_text(shape, issue)
    if fix is not None:
        applied_strategies.append("autofit_text")
        fix.note = f"normAutofit fallback; unavailable: {','.join(unavailable)}; {fix.note}"
        return fix, applied_strategies, unavailable
    unavailable.append("autofit_text")
    return None, applied_strategies, unavailable


# ---------------------------------------------------------------------------
# Remaining dedicated repairs (contrast / placeholder / CJK)
# ---------------------------------------------------------------------------
def _fix_adjust_contrast(shape, slide, config: QualityConfig, issue: Issue) -> AppliedFix | None:
    if not getattr(shape, "has_text_frame", False):
        return None
    bg = _shape_solid_fill(shape) or _slide_solid_bg(slide)
    if bg is None:
        # Background cannot be determined deterministically -> fail safe.
        return None
    large_pt = float(config.large_text_pt)
    normal_min = float(config.min_contrast_ratio)
    large_min = float(config.large_text_contrast_ratio)
    changed = 0
    for para in shape.text_frame.paragraphs:
        for run in para.runs:
            try:
                color = run.font.color
                if color.type != MSO_COLOR_TYPE.RGB:
                    continue
                fg = str(color.rgb)
            except Exception:
                continue
            ratio = contrast_ratio(fg, bg)
            if ratio is None:
                continue
            size = run.font.size.pt if run.font.size is not None else None
            threshold = large_min if (size is not None and size >= large_pt) else normal_min
            if ratio >= threshold:
                continue
            # Pick black or white, whichever gives the higher contrast on bg.
            best = max(("000000", "FFFFFF"), key=lambda c: contrast_ratio(c, bg) or 0.0)
            run.font.color.rgb = RGBColor.from_string(best)
            changed += 1
    if not changed:
        return None
    return AppliedFix(
        rule_id=issue.rule_id,
        shape_id=issue.shape_id,
        action="adjust_contrast",
        note=f"recolored {changed} low-contrast run(s) against background #{bg}",
    )


def _fix_clear_placeholder(shape, issue: Issue) -> AppliedFix | None:
    if not getattr(shape, "has_text_frame", False):
        return None
    shape.text_frame.text = ""
    return AppliedFix(
        rule_id=issue.rule_id,
        shape_id=issue.shape_id,
        action="clear_placeholder",
        note="cleared leftover placeholder text",
    )


def _fix_normalize_cjk(shape, issue: Issue) -> AppliedFix | None:
    if not getattr(shape, "has_text_frame", False):
        return None
    changed = 0
    for para in shape.text_frame.paragraphs:
        for run in para.runs:
            new = _normalize_cjk_text(run.text)
            if new != run.text:
                run.text = new
                changed += 1
    if not changed:
        return None
    return AppliedFix(
        rule_id=issue.rule_id,
        shape_id=issue.shape_id,
        action="normalize_cjk_text",
        note=f"normalised CJK text on {changed} run(s)",
    )


def _apply_fix(
    fix_id: str, slide, shape, issue, config: QualityConfig, bounds: Rect
) -> AppliedFix | None:
    if fix_id == "increase_font_size":
        return _fix_increase_font_size(shape, config, issue)
    if fix_id == "adjust_contrast":
        return _fix_adjust_contrast(shape, slide, config, issue)
    if fix_id == "clear_placeholder":
        return _fix_clear_placeholder(shape, issue)
    if fix_id == "normalize_cjk_text":
        return _fix_normalize_cjk(shape, issue)
    return None


# ---------------------------------------------------------------------------
# Internal bookkeeping for post-fix classification
# ---------------------------------------------------------------------------
@dataclass
class _Attempt:
    issue: Issue
    status: str = "pending"  # applied | skipped
    fix: AppliedFix | None = None
    record: AppliedFix | None = None
    strategies: list[str] = field(default_factory=list)
    reason: str = ""


def _make_skipped(issue: Issue, action: str, why: str) -> AppliedFix:
    return AppliedFix(
        rule_id=issue.rule_id,
        shape_id=issue.shape_id,
        action=action,
        status="skipped",
        note=why,
    )


def _classify_attempts(
    attempts: list[_Attempt], before: list[Issue], after: list[Issue]
) -> tuple[list[FixOutcome], dict[str, int]]:
    """Compare targeted issues before and after; honest four-way labels."""
    before_keys = {_issue_key(i) for i in before}
    after_keys = {_issue_key(i) for i in after}
    new_on_target: dict[tuple[int, str], list[Issue]] = {}
    for issue in after:
        if _issue_key(issue) not in before_keys:
            new_on_target.setdefault((issue.slide_index, issue.shape_id or ""), []).append(issue)

    counts = {RESOLVED: 0, UNCHANGED: 0, REGRESSED: 0, SKIPPED: 0}
    outcomes: list[FixOutcome] = []
    for attempt in attempts:
        issue = attempt.issue
        key = _issue_key(issue)
        if attempt.status != "applied":
            outcome = SKIPPED
            reason = attempt.reason or "no safe automatic repair; manual review required"
        elif key in after_keys:
            outcome = UNCHANGED
            reason = "target issue still present after re-scan"
        else:
            fresh = new_on_target.get((issue.slide_index, issue.shape_id or ""), [])
            if fresh:
                outcome = REGRESSED
                reason = "new issue(s) on repaired shape: " + ", ".join(
                    sorted({f.rule_id for f in fresh})
                )
            else:
                outcome = RESOLVED
                reason = "target issue absent after re-scan"
        counts[outcome] += 1
        outcomes.append(
            FixOutcome(
                rule_id=issue.rule_id,
                slide_index=issue.slide_index,
                shape_id=issue.shape_id,
                action=attempt.fix.action if attempt.fix else (issue.fix_id or "manual_review"),
                status=attempt.status,
                outcome=outcome,
                strategies=list(attempt.strategies),
                reason=reason,
                detail=issue.detail,
            )
        )
    return outcomes, counts


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def fix_file(
    source_path: str | Path,
    output_path: str | Path | None = None,
    config: QualityConfig | None = None,
    profile: str = "core",
    make_backup: bool = True,
) -> FixReport:
    """Apply every safe automatic fix the source deck allows.

    The source file is opened read-only and is never overwritten.  Results are
    written to ``output_path`` (default ``<stem>.fixed.pptx`` next to the
    source).  When ``make_backup`` is true a byte copy ``<stem>.bak.pptx`` is
    taken first.  The output deck is re-scanned so the report reflects the
    *real* before/after state, and every targeted issue receives a
    ``resolved`` / ``unchanged`` / ``regressed`` / ``skipped`` outcome.
    """
    config = config or QualityConfig()
    src = Path(source_path)
    report = DetailedFixReport(source_path=str(src.resolve()), output_path="")

    if not src.exists():
        report.note = f"source file not found: {src}"
        return report

    before = scan_file(src, config, profile=profile)
    before_summary = before.summarize().to_dict()
    before_total = before_summary["total"]
    report.before_summary = before_summary

    if before.status == "error":
        report.note = f"cannot scan source deck: {before.error}"
        return report

    if output_path is None:
        output_path = src.with_name(f"{src.stem}.fixed.pptx")
    out = Path(output_path)
    report.output_path = str(out.resolve())

    backup_path: Path | None = None
    if make_backup:
        backup_path = src.with_name(f"{src.stem}.bak.pptx")
        shutil.copy2(src, backup_path)
        report.backup_path = str(backup_path.resolve())

    source_hash_before = _sha256(src)

    # Open the SOURCE read/write in memory, but save to a *new* output file.
    prs = Presentation(str(src))
    bounds = Rect(0, 0, int(before.slide_width), int(before.slide_height))
    shape_maps = _build_shape_maps(prs)

    applied: list[AppliedFix] = []
    skipped: list[AppliedFix] = []
    attempts: list[_Attempt] = []

    for issue in before.issues:
        attempt = _Attempt(issue=issue)
        spec = RULES[issue.rule_id]
        fix_id = spec.fix_id

        if fix_id is None:
            attempt.status = "skipped"
            attempt.reason = "automatic repair not supported; requires manual review"
            record = _make_skipped(issue, "manual_review", attempt.reason)
            attempt.record = record
            skipped.append(record)
            attempts.append(attempt)
            continue

        if issue.slide_index < 0 or issue.slide_index >= len(shape_maps):
            attempt.status = "skipped"
            attempt.reason = "document-level issue has no shape target"
            record = _make_skipped(issue, fix_id, attempt.reason)
            attempt.record = record
            skipped.append(record)
            attempts.append(attempt)
            continue

        shape = shape_maps[issue.slide_index].get(issue.shape_id or "")
        if shape is None:
            attempt.status = "skipped"
            attempt.reason = "target shape could not be located in the package"
            record = _make_skipped(issue, fix_id, attempt.reason)
            attempt.record = record
            skipped.append(record)
            attempts.append(attempt)
            continue

        slide = prs.slides[issue.slide_index]
        result: AppliedFix | None = None
        try:
            if fix_id == "autofit_text":
                result, strategies, unavailable = _fix_text_overflow(
                    shape, slide, bounds, config, issue
                )
                attempt.strategies = strategies
                if unavailable:
                    attempt.reason = "strategies unavailable: " + ",".join(unavailable)
            elif fix_id == "move_into_slide":
                result = _fix_move_into_slide(shape, slide, bounds, issue)
                attempt.strategies = ["move_into_slide"]
            else:
                result = _apply_fix(fix_id, slide, shape, issue, config, bounds)
                attempt.strategies = [fix_id]
        except Exception as exc:  # one bad repair must not abort the run
            attempt.status = "skipped"
            attempt.reason = f"repair failed: {exc}"
            record = _make_skipped(issue, fix_id, attempt.reason)
            attempt.record = record
            skipped.append(record)
            attempts.append(attempt)
            continue

        if result is None:
            attempt.status = "skipped"
            attempt.reason = "repair not applicable in this context (skipped safely)"
            record = _make_skipped(issue, fix_id, attempt.reason)
            attempt.record = record
            skipped.append(record)
        else:
            attempt.status = "applied"
            attempt.fix = result
            applied.append(result)
        attempts.append(attempt)

    # Write to the NEW output file; the source bytes stay untouched.
    prs.save(str(out))

    # Verify the output package opens cleanly.
    try:
        Presentation(str(out))
    except Exception as exc:
        report.applied = applied
        report.skipped = skipped
        report.created = out.exists()
        report.note = f"fixed deck failed to re-open: {exc}"
        return report

    after = scan_file(out, config, profile=profile)
    after_summary = after.summarize().to_dict()

    source_hash_after = _sha256(src)
    source_unchanged = source_hash_before == source_hash_after

    outcomes, counts = _classify_attempts(attempts, before.issues, after.issues)
    report.outcomes = outcomes
    report.resolved_count = counts[RESOLVED]
    report.unchanged_count = counts[UNCHANGED]
    report.regressed_count = counts[REGRESSED]
    report.manual_review_count = counts[SKIPPED]

    # Honest labels on the legacy AppliedFix records (free-form note field).
    for attempt, outcome in zip(attempts, outcomes, strict=False):
        if attempt.fix is not None:
            attempt.fix.note = f"[{outcome.outcome}] {attempt.fix.note}"
        if attempt.record is not None:
            attempt.record.note = f"[manual] {attempt.record.note}"

    report.applied = applied
    report.skipped = skipped
    report.after_summary = after_summary
    report.created = out.exists()

    notes: list[str] = []
    if not source_unchanged:
        notes.append("WARNING: source file bytes changed during fix")
    if after.status == "error":
        notes.append(f"re-scan of output reported: {after.error}")
    removed = before_total - after_summary.get("total", before_total)
    if removed <= 0:
        notes.append("repair did not reduce the detected issue count")
    if skipped:
        notes.append(f"{len(skipped)} issue(s) require manual review")
    notes.append(
        "post-fix outcomes: "
        f"resolved={counts[RESOLVED]} unchanged={counts[UNCHANGED]} "
        f"regressed={counts[REGRESSED]} manual_review={counts[SKIPPED]}"
    )
    if counts[REGRESSED] > 0:
        notes.append(
            f"WARNING: {counts[REGRESSED]} repair(s) introduced a new issue; "
            "inspect regressed items"
        )
    if not notes:
        notes.append("all safe automatic fixes applied and re-verified")
    report.note = "; ".join(notes)
    report.success = bool(
        report.created
        and source_unchanged
        and after.status == "ok"
        and counts[REGRESSED] == 0
        and after_summary.get("total", before_total) < before_total
    )
    return report
