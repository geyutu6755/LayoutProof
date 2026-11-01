"""Rule: leftover placeholder prompts, TODO markers or lorem ipsum text."""

from __future__ import annotations

from collections.abc import Iterable

from ..models import Issue, RuleId
from ..parsing import PresentationModel
from .base import Rule, register_rule


@register_rule
class UnfinishedPlaceholderRule(Rule):
    rule_id = RuleId.UNFINISHED_PLACEHOLDER
    confidence = 0.90

    def check(self, model: PresentationModel) -> Iterable[Issue]:
        patterns = [p.lower() for p in self.config.placeholder_patterns]
        for slide in model.slides:
            for shape in slide.visible_shapes:
                if shape.is_background or shape.is_decorative:
                    continue
                text = shape.text.strip()
                if not text:
                    continue
                lowered = text.lower()
                matched = next((p for p in patterns if p in lowered), None)
                if matched is None:
                    continue
                yield self._issue(
                    slide,
                    shape,
                    detail=f"text matches placeholder pattern {matched!r}",
                    confidence=0.90,
                    evidence={
                        "matched_pattern": matched,
                        "text_preview": text[:60],
                    },
                )
