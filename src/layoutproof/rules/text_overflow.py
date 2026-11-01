"""Rule: heuristic text overflow estimation without a renderer.

Based purely on geometry and text: combine the explicit font size, ``word_wrap``
setting, autofit mode and text length to estimate the required number of lines
and box height, then compare against the actual shape height.  When PowerPoint's
``normAutofit`` (auto-shrink on overflow) is enabled the text is shrunk by the
application itself, so we skip it to avoid false positives.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

from ..models import Issue, RuleId
from ..parsing import PresentationModel, ShapeModel
from ..parsing.geometry import emu_to_pt
from .base import Rule, register_rule

# Rough vertical padding inside a text frame (top + bottom insets, in points).
# PowerPoint default bodyPr insets are ~0.05" top/bottom = ~7pt total.
_FRAME_PADDING_PT = 8.0
# Typical single-spaced line leading multiplier relative to the font size.
_LINE_LEADING = 1.2
# Average advance width of a Latin glyph as a fraction of the font size
# (mixed case with spaces and narrow glyphs averages below 0.5em).
_GLYPH_WIDTH_FRACTION = 0.45
# Horizontal inset allowance (left + right insets, in points).
_HORIZONTAL_PADDING_PT = 16.0


@register_rule
class TextOverflowRule(Rule):
    rule_id = RuleId.TEXT_OVERFLOW
    confidence = 0.80

    def check(self, model: PresentationModel) -> Iterable[Issue]:
        threshold = self.config.overflow_ratio_threshold
        for slide in model.slides:
            for shape in slide.visible_shapes:
                if shape.is_background or shape.is_decorative:
                    continue
                if shape.rect is None:
                    continue
                text = shape.text
                if not text:
                    continue
                # PowerPoint shrinks text itself when normAutofit is on.
                if shape.autofit == "normAutofit":
                    continue
                # Inherited (unset) font sizes are not judged.
                sizes = shape.explicit_font_sizes
                if not sizes:
                    continue
                font_pt = max(sizes)
                lines, needed_pt = self._estimate_lines_height(shape, font_pt)
                if lines <= 0:
                    continue
                box_h_pt = emu_to_pt(shape.rect.height)
                if box_h_pt <= 0:
                    continue
                overflow_ratio = (needed_pt - box_h_pt) / box_h_pt
                if overflow_ratio <= threshold:
                    continue
                yield self._issue(
                    slide,
                    shape,
                    detail=(
                        f"estimated {lines} line(s) need ~{needed_pt:.0f}pt "
                        f"but box is only {box_h_pt:.0f}pt tall"
                    ),
                    confidence=0.78,
                    evidence={
                        "estimated_lines": lines,
                        "estimated_height_pt": round(needed_pt, 1),
                        "box_height_pt": round(box_h_pt, 1),
                        "overflow_ratio": round(overflow_ratio, 3),
                        "autofit": shape.autofit,
                        "font_size_pt": font_pt,
                    },
                )

    def _estimate_lines_height(self, shape: ShapeModel, font_pt: float) -> tuple[int, float]:
        box_w_pt = emu_to_pt(shape.rect.width)
        usable_w_pt = max(1.0, box_w_pt - _HORIZONTAL_PADDING_PT)
        glyph_w_pt = font_pt * _GLYPH_WIDTH_FRACTION
        chars_per_line = max(1.0, usable_w_pt / glyph_w_pt)
        total_lines = 0
        for para in shape.paragraphs:
            para_text = para.text.strip()
            if not para_text:
                continue
            if shape.wrap == "none":
                total_lines += 1
            else:
                total_lines += math.ceil(len(para_text) / chars_per_line)
        if total_lines == 0:
            return 0, 0.0
        needed_pt = total_lines * font_pt * _LINE_LEADING + _FRAME_PADDING_PT
        return total_lines, needed_pt
