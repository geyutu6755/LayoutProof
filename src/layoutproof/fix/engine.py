"""Safe, offline automatic fix engine.

Closes the loop  detect -> locate -> fix -> re-verify  without ever touching
the source file.  Every repair maps one-to-one to an :class:`Issue` raised by
the detection rules.  Issues the engine cannot repair safely (overlap, blank
slides, broken media / references, alt text) are recorded as ``skipped`` and
flagged for manual review instead of being fabricated away.
"""

from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_COLOR_TYPE, MSO_FILL
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.enum.text import MSO_AUTO_SIZE
from pptx.util import Emu, Pt

from ..config import QualityConfig
from ..engine import scan_file
from ..models import RULES, AppliedFix, FixReport, Issue
from ..parsing.geometry import Rect
from ..rules.contrast import contrast_ratio

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


# ---------------------------------------------------------------------------
# Individual repairs.  Each returns an AppliedFix on success, or None when the
# repair is not applicable in this context (caller records it as skipped).
# ---------------------------------------------------------------------------
def _fix_move_into_slide(shape, bounds: Rect, issue: Issue) -> AppliedFix | None:
    left, top, width, height = shape.left, shape.top, shape.width, shape.height
    if None in (left, top, width, height):
        return None
    old = Rect(int(left), int(top), int(width), int(height))
    new = old.clamp(bounds)
    if (new.x, new.y) == (old.x, old.y):
        return AppliedFix(
            rule_id=issue.rule_id,
            shape_id=issue.shape_id,
            action="move_into_slide",
            note="already within slide bounds",
        )
    shape.left = Emu(new.x)
    shape.top = Emu(new.y)
    return AppliedFix(
        rule_id=issue.rule_id,
        shape_id=issue.shape_id,
        action="move_into_slide",
        note=f"moved shape into bounds at x={new.x} y={new.y}",
    )


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


def _fix_autofit_text(shape, issue: Issue) -> AppliedFix | None:
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
    if fix_id == "move_into_slide":
        return _fix_move_into_slide(shape, bounds, issue)
    if fix_id == "increase_font_size":
        return _fix_increase_font_size(shape, config, issue)
    if fix_id == "autofit_text":
        return _fix_autofit_text(shape, issue)
    if fix_id == "adjust_contrast":
        return _fix_adjust_contrast(shape, slide, config, issue)
    if fix_id == "clear_placeholder":
        return _fix_clear_placeholder(shape, issue)
    if fix_id == "normalize_cjk_text":
        return _fix_normalize_cjk(shape, issue)
    return None


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
    *real* before/after state.
    """
    config = config or QualityConfig()
    src = Path(source_path)
    report = FixReport(source_path=str(src.resolve()), output_path="")

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

    def _skip(issue: Issue, why: str) -> None:
        skipped.append(
            AppliedFix(
                rule_id=issue.rule_id,
                shape_id=issue.shape_id,
                action=issue.fix_id or "manual_review",
                status="skipped",
                note=why,
            )
        )

    for issue in before.issues:
        spec = RULES[issue.rule_id]
        fix_id = spec.fix_id
        if fix_id is None:
            _skip(issue, "automatic repair not supported; requires manual review")
            continue
        if issue.slide_index < 0 or issue.slide_index >= len(shape_maps):
            _skip(issue, "document-level issue has no shape target")
            continue
        shape = shape_maps[issue.slide_index].get(issue.shape_id or "")
        if shape is None:
            _skip(issue, "target shape could not be located in the package")
            continue
        slide = prs.slides[issue.slide_index]
        try:
            result = _apply_fix(fix_id, slide, shape, issue, config, bounds)
        except Exception as exc:  # one bad repair must not abort the run
            _skip(issue, f"repair failed: {exc}")
            continue
        if result is None:
            _skip(issue, "repair not applicable in this context (skipped safely)")
        else:
            applied.append(result)

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
    if not notes:
        notes.append("all safe automatic fixes applied and re-verified")
    report.note = "; ".join(notes)
    report.success = bool(
        report.created
        and source_unchanged
        and after.status == "ok"
        and after_summary.get("total", before_total) < before_total
    )
    return report
