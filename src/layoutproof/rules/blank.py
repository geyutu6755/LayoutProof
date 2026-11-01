"""Rule: slides that contain no visible content."""

from __future__ import annotations

from collections.abc import Iterable

from ..models import Issue, RuleId
from ..parsing import PresentationModel
from .base import Rule, register_rule


@register_rule
class BlankSlideRule(Rule):
    rule_id = RuleId.BLANK_SLIDE
    confidence = 0.90

    def check(self, model: PresentationModel) -> Iterable[Issue]:
        for slide in model.slides:
            content_shapes = []
            for shape in slide.visible_shapes:
                if shape.is_background or shape.is_decorative:
                    continue
                has_text = bool(shape.text.strip())
                has_media = shape.is_picture or shape.has_table or shape.has_chart
                if has_text or has_media:
                    content_shapes.append(shape)
            if content_shapes:
                continue
            yield self._issue(
                slide,
                None,
                location=model.bounds,
                detail="slide has no visible content shapes, placeholder text or media",
                confidence=0.90,
                evidence={
                    "visible_shape_count": len(slide.visible_shapes),
                    "content_shape_count": 0,
                    "background_picture": slide.background_picture,
                },
            )
