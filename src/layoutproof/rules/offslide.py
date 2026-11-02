"""Rule: objects placed outside the slide canvas."""

from __future__ import annotations

from collections.abc import Iterable

from ..models import Issue, RuleId
from ..parsing import PresentationModel
from .base import Rule, register_rule


@register_rule
class OffslideRule(Rule):
    rule_id = RuleId.OFFSLIDE_OBJECT
    confidence = 1.0

    def check(self, model: PresentationModel) -> Iterable[Issue]:
        bounds = model.bounds
        threshold = self.config.offslide_fraction_threshold
        for slide in model.slides:
            for shape in slide.visible_shapes:
                if shape.rect is None or shape.is_background:
                    continue
                # Decorative elements (flagged or named) are intentionally
                # placed accents, sometimes bleeding past the edge; exempt
                # them so a deliberate ornament does not become a false alarm.
                if shape.is_decorative:
                    continue
                fraction = shape.rect.fraction_outside(bounds)
                if fraction <= threshold:
                    continue
                fully_out = shape.rect.is_fully_outside(bounds)
                yield self._issue(
                    slide,
                    shape,
                    detail=(
                        "100% outside slide"
                        if fully_out
                        else f"{fraction * 100:.0f}% of area outside slide"
                    ),
                    evidence={
                        "fraction_outside": round(fraction, 4),
                        "fully_outside": fully_out,
                    },
                )
