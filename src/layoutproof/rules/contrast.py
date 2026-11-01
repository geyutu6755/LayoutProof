"""Rule: insufficient WCAG contrast between text and its background.

Heuristic (confidence 0.8 for explicit colors, 0.7 for theme-derived colors):
we only judge a text run when BOTH colors are deterministically known:

* foreground  - explicit RGB color on the text run (already parsed), and
* background   - resolved in this priority order:
    1. solid fill on the text-bearing shape,
    2. explicit ``<p:bg>`` solid fill on the slide,
    3. the slide master's ``<p:bg>`` when the slide has none, with the
       classic theme colors ``bg1`` -> white and ``tx1`` -> black.

If either side is a theme accent, gradient, picture or otherwise
unresolvable we fail open and emit nothing rather than risk a false alarm.
Readable thresholds come from the config: normal text uses
``min_contrast_ratio`` while text at ``>= large_text_pt`` uses the more
lenient ``large_text_contrast_ratio``.
"""

from __future__ import annotations

import posixpath
from collections.abc import Iterable

from ..models import Issue, RuleId
from ..parsing import PresentationModel, SafePackage
from .base import Rule, register_rule

_P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"

# Classic Office theme constants we resolve without opening theme XML.
_SCHEME_COLOR_RGB = {"bg1": "FFFFFF", "tx1": "000000"}


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
# Background discovery
# ---------------------------------------------------------------------------
def _shape_solid_fill(shape) -> str | None:
    try:
        from pptx.enum.dml import MSO_FILL

        fill = shape.fill
        if fill.type == MSO_FILL.SOLID:
            return str(fill.fore_color.rgb)
    except Exception:
        pass
    return None


def _bg_from_xml(root) -> tuple[str, str] | None:
    """Resolve a (color, basis) tuple from a slide/master XML root, if known."""
    c_sld = root.find(f".//{_P}cSld")
    if c_sld is None:
        return None
    bg = c_sld.find(f"{_P}bg")
    if bg is None:
        return None
    # Explicit solid fill in <p:bg>
    for sf in bg.iter(f"{_A}solidFill"):
        srgb = sf.find(f"{_A}srgbClr")
        if srgb is not None and srgb.get("val"):
            return (srgb.get("val").upper(), "slide_bg")
        scheme = sf.find(f"{_A}schemeClr")
        if scheme is not None and scheme.get("val") in _SCHEME_COLOR_RGB:
            return (_SCHEME_COLOR_RGB[scheme.get("val")], "theme_bg1")
    # Background reference block: <p:bgRef ...><a:schemeClr val="bg1"/>
    for ref in bg.iter(f"{_P}bgRef"):
        scheme = ref.find(f"{_A}schemeClr")
        if scheme is not None and scheme.get("val") in _SCHEME_COLOR_RGB:
            return (_SCHEME_COLOR_RGB[scheme.get("val")], "theme_bg1")
    return None


def _background_maps(
    model: PresentationModel,
) -> tuple[dict[int, tuple[str, str]], dict[tuple[int, str], str]]:
    """Return (slide bg map, shape fill map).

    Slide bg map values are ``(rgb, basis)``; basis is ``slide_bg`` for an
    explicit solid/scheme background, ``theme_bg1`` for a master theme fallback.
    """
    slide_bg: dict[int, tuple[str, str]] = {}
    shape_fill: dict[tuple[int, str], str] = {}

    # Shape-level solid fills come from the live deck.
    try:
        from pptx import Presentation

        prs = Presentation(model.path)
        for idx, slide in enumerate(prs.slides):
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
    except Exception:
        pass

    # Slide/master background comes from raw XML via SafePackage.
    pkg = SafePackage(model.path)
    try:
        master_bg: tuple[str, str] | None = None
        masters = sorted(
            n
            for n in pkg.names
            if "ppt/slideMasters/slideMaster" in n and n.endswith(".xml")
        )
        if masters:
            try:
                master_bg = _bg_from_xml(pkg.parse_xml(masters[0]))
            except Exception:
                master_bg = None

        for idx, slide in enumerate(model.slides):
            part = slide.part_name.lstrip("/")
            info: tuple[str, str] | None = None
            if pkg.has_part(part):
                try:
                    info = _bg_from_xml(pkg.parse_xml(part))
                except Exception:
                    info = None
            if info is None:
                info = master_bg  # fall back to the slide master
            if info is not None:
                slide_bg[idx] = info
    finally:
        pkg.close()
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
            bg_info = slide_bg.get(slide.index)
            for shape in slide.visible_shapes:
                if not shape.paragraphs:
                    continue
                bg = shape_fill.get((slide.index, shape.id))
                bg_basis = "shape_fill"
                if bg is None and bg_info is not None:
                    bg, bg_basis = bg_info
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
                    confidence=0.7 if bg_basis == "theme_bg1" else 0.8,
                    evidence={
                        "basis": bg_basis,
                        "background": bg,
                        "worst_ratio": worst["ratio"],
                        "worst_threshold": worst["threshold"],
                        "bad_runs": bad_runs,
                    },
                )
