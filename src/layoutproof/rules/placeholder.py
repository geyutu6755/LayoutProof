"""Rule: leftover placeholder prompts, TODO markers or lorem ipsum text."""

from __future__ import annotations

import re
from collections.abc import Iterable

from ..models import Issue, RuleId
from ..parsing import PresentationModel
from .base import Rule, register_rule

# Generic single-word markers that can also appear in ordinary prose. They are
# only treated as leftover markers when the whole text is short (a real marker
# box is terse), not when the word is mentioned inside a full sentence.
_GENERIC_MARKERS = frozenset({"todo", "tbd", "fixme", "placeholder"})
_MAX_GENERIC_MARKER_WORDS = 6
_CJK_RE = re.compile(r"[㐀-䶿一-鿿]")


def _word_boundary_pattern(pattern: str) -> re.Pattern[str]:
    """Regex that matches *pattern* as whole words, not inside other words."""
    return re.compile(rf"(?<![a-z0-9]){re.escape(pattern)}(?![a-z0-9])")


@register_rule
class UnfinishedPlaceholderRule(Rule):
    rule_id = RuleId.UNFINISHED_PLACEHOLDER
    confidence = 0.90

    def _match(self, lowered: str, patterns: list[str]) -> str | None:
        word_count = len(lowered.split())
        for pattern in patterns:
            if _CJK_RE.search(pattern):
                # CJK markers are specific; substring matching is reliable.
                if pattern in lowered:
                    return pattern
                continue
            if pattern in _GENERIC_MARKERS:
                # Ambiguous word: require a whole-word hit in short text so a
                # normal sentence that merely mentions it is not flagged.
                if (
                    word_count <= _MAX_GENERIC_MARKER_WORDS
                    and _word_boundary_pattern(pattern).search(lowered)
                ):
                    return pattern
                continue
            if _word_boundary_pattern(pattern).search(lowered):
                return pattern
        return None

    def check(self, model: PresentationModel) -> Iterable[Issue]:
        patterns = [p.lower() for p in self.config.placeholder_patterns]
        for slide in model.slides:
            for shape in slide.visible_shapes:
                if shape.is_background or shape.is_decorative:
                    continue
                text = shape.text.strip()
                if not text:
                    continue
                matched = self._match(text.lower(), patterns)
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
