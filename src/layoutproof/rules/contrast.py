"""Rule: insufficient WCAG contrast between text and its background.

Heuristic (confidence ~0.8): we only judge a text run when BOTH colors are
deterministically known:

* foreground  - explicit RGB color on the text run (already parsed), and
* background   - either a solid fill on the text-bearing shape, or a solid
  background fill on the slide.

If either side is a theme color, gradient, picture or otherwise unresolvable we
fail open and emit nothing rather than risk a false alarm.

Readable thresholds come from the config: normal text uses
``min_contrast_ratio`` while text at ``>= large_text_pt`` uses the more
lenient ``large_text_contrast_ratio``.
"""

from __future__ import annotations

from collections.abc import Iterable

from ..models import Issue, RuleId
from ..parsing import PresentationModel
from .base import Rule, register_rule


# ---------------------------------------------------------------------------
# WCAG contrast math (relative luminance, sRGB)
# ---------------------------------------------------------------------------
def _linear_channel(channel: float) -> float:
    c = channel / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_rgb: str) -> float | None:
    """WCAG 2.x relative luminance for an 'RRGGBB' hex string."""
    try:
        h = hex_rgb.lstrip("#")
        if len(h) != 6:
            return None
        r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    except (TypeError, ValueError, AttributeError):
        return None
    return 0.2126 * _linear_channel(r) + 0.7152 * _linear_channel(g) + 0.0722 * _linear_channel(b)


def contrast_ratio(hex_a: str, hex_b: str) -> float | None:
    """Contrast ratio between two 'RRGGBB' colors (>= 1.0). None if unparsable."""
    la = relative_luminance(hex_a)
    lb = relative_luminance(hex_b)
    if la is None or lb is None:
        return None
    light, dark = max(la, lb), min(la, lb)
    return (light + 0.05) / (dark + 0.05)


# ---------------------------------------------------------------------------
# Background discovery (re-open the deck; the parsed model does not carry
# fill colors, so we resolve them straight from python-pptx).
# ---------------------------------------------------------------------------
def _slide_solid_bg(slide) -> str | None:
    try:
        from pptx.enum.dml import MSO_FILL

        fill = slide.background.fill
        if fill.type == MSO_FILL.SOLID:
            return str(fill.fore_color.rgb)
    except Exception:
        pass
    return None


def _shape_solid_fill(shape) -> str | None:
    try:
        from pptx.enum.dml import MSO_FILL

        fill = shape.fill
        if fill.type == MSO_FILL.SOLID:
            return str(fill.fore_color.rgb)
    except Exception:
        pass
    return None


def _background_maps(model: PresentationModel) -> tuple[dict[int, str | None], dict[tuple[int, str], str | None]]:
    """Return (slide bg map, shape fill map) keyed by slide index / shape id."""
    slide_bg: dict[int, str | None] = {}
    shape_fill: dict[tuple[int, str], str | None] = {}
    try:
        from pptx import Presentation

        prs = Presentation(model.path)
    except Exception:
        return slide_bg, shape_fill

    for idx, slide in enumerate(prs.slides):
        slide_bg[idx] = _slide_solid_bg(slide)
        try:
            shapes = list(iter(slide.shapes))
        except Exception:
            shapes = []
        for shape in shapes:
            try:
                key = (idx, str(shape.shape_id))
            except Exception:
                continue
            rgb = _shape_solid_fill(shape)
            if rgb is not None:
                shape_fill[key] = rgb
    return slide_bg, shape_fill


# ---------------------------------------------------------------------------
@register_rule
class LowContrastRule(Rule):
    rule_id = RuleId.LOW_CONTRAST
    confidence = 0.8

    def check(self, model: PresentationModel) -> Iterable[Issue]:
        slide_bg, shape_fill = _background_maps(model)
        large_pt = float(self.config.large_text_pt)
        normal_min = float(self.config.min_contrast_ratio)
        large_min = float(self.config.large_text_contrast_ratio)

        for slide in model.slides:
            slide_bg_rgb = slide_bg.get(slide.index)
            for shape in slide.visible_shapes:
                if not shape.paragraphs:
                    continue
                # Prefer the text-bearing shape's own solid fill, then the
                # slide's solid background; anything else is unknown.
                bg = shape_fill.get((slide.index, shape.id))
                bg_basis = "shape_fill"
                if bg is None:
                    bg = slide_bg_rgb
                    bg_basis = "slide_bg" if bg is not None else None
                if bg is None:
                    continue  # fail open

                bad_runs: list[dict] = []
                for para in shape.paragraphs:
                    for run in para.runs:
                        if not run.color_rgb:
                            continue
                        ratio = contrast_ratio(run.color_rgb, bg)
                        if ratio is None:
                            continue
                        is_large = bool(run.font_size_pt is not None and run.font_size_pt >= large_pt)
                        threshold = large_min if is_large else normal_min
                        if ratio < threshold:
                            bad_runs.append(
                                {
                                    "ratio": round(ratio, 3),
                                    "threshold": threshold,
                                    "foreground": run.color_rgb,
                                    "font_size_pt": run.font_size_pt,
                                    "large_text": is_large,
                                }
                            )
                if not bad_runs:
                    continue
                worst = min(bad_runs, key=lambda r: r["ratio"])
                yield self._issue(
                    slide,
                    shape,
                    detail=(
                        f"contrast ratio {worst['ratio']:.2f}:1 below "
                        f"{worst['threshold']:.1f}:1 threshold ({bg_basis})"
                    ),
                    evidence={
                        "basis": bg_basis,
                        "background": bg,
                        "worst_ratio": worst["ratio"],
                        "worst_threshold": worst["threshold"],
                        "bad_runs": bad_runs,
                    },
                )
