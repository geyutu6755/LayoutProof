"""Rule: explicit font sizes below the readable threshold."""

from __future__ import annotations

from collections.abc import Iterable

from ..models import Issue, RuleId
from ..parsing import PresentationModel
from .base import Rule, register_rule


@register_rule
class FontSizeRule(Rule):
    rule_id = RuleId.FONT_TOO_SMALL
    confidence = 1.0

    def check(self, model: PresentationModel) -> Iterable[Issue]:
        minimum = self.config.min_font_size_pt
        for slide in model.slides:
            for shape in slide.visible_shapes:
                if shape.is_background or not shape.paragraphs:
                    continue
                sizes = shape.explicit_font_sizes
                if not sizes:
                    # Inherited sizes are not judged to avoid false positives.
                    continue
                min_size = min(sizes)
                if min_size < minimum:
                    yield self._issue(
                        slide,
                        shape,
                        detail=f"smallest font {min_size:g}pt (minimum {minimum:g}pt)",
                        evidence={
                            "min_font_size_pt": min_size,
                            "threshold_pt": minimum,
                            "all_sizes_pt": sorted(set(round(s, 2) for s in sizes)),
                        },
                    )
