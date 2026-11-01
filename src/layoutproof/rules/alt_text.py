"""Rule: meaningful, visible images without alternative text (accessibility).

Decorative images, background (full-bleed) pictures and hidden pictures are
exempt: they either carry no information for a screen reader or do not render.
"""

from __future__ import annotations

from collections.abc import Iterable

from ..models import Issue, RuleId
from ..parsing import PresentationModel
from .base import Rule, register_rule


@register_rule
class MissingAltTextRule(Rule):
    rule_id = RuleId.MISSING_ALT_TEXT
    confidence = 1.0

    def check(self, model: PresentationModel) -> Iterable[Issue]:
        for slide in model.slides:
            for shape in slide.shapes:
                if not shape.is_picture:
                    continue
                if not shape.is_visible:
                    continue
                if shape.is_decorative or shape.is_background:
                    continue
                if shape.has_alt_text:
                    continue
                yield self._issue(
                    slide,
                    shape,
                    detail="picture has no alternative text",
                    evidence={"kind": "missing_alt_text"},
                )
