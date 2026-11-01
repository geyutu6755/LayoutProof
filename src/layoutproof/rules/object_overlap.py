"""Rule: unexpected overlap between two content shapes."""

from __future__ import annotations

from collections.abc import Iterable

from ..models import Issue, RuleId
from ..parsing import PresentationModel, ShapeModel
from .base import Rule, register_rule


def _is_content_shape(shape: ShapeModel, decorative_hints: list[str]) -> bool:
    """Visible, non-background, non-decorative, top-level shape."""
    if not shape.is_visible or shape.is_background or shape.is_decorative:
        return False
    if shape.rect is None:
        return False
    # Only compare top-level shapes; grouped children share a deliberate
    # arrangement (and their parent links via parent_id) so skip them.
    if shape.parent_id is not None:
        return False
    name = (shape.name or "").lower()
    if any(hint in name for hint in decorative_hints):
        return False
    return True


@register_rule
class ObjectOverlapRule(Rule):
    rule_id = RuleId.OBJECT_OVERLAP
    confidence = 0.80

    def check(self, model: PresentationModel) -> Iterable[Issue]:
        threshold = self.config.overlap_ratio_threshold
        hints = [h.lower() for h in self.config.decorative_name_hints]
        for slide in model.slides:
            shapes = [
                s for s in slide.shapes if _is_content_shape(s, hints)
            ]
            for i in range(len(shapes)):
                for j in range(i + 1, len(shapes)):
                    a, b = shapes[i], shapes[j]
                    ratio = a.rect.overlap_ratio(b.rect)
                    if ratio < threshold:
                        continue
                    yield self._issue(
                        slide,
                        a,
                        location=a.rect.intersection(b.rect),
                        detail=(
                            f"{b.name!r} overlaps {a.name!r}: "
                            f"{ratio * 100:.0f}% of the smaller shape"
                        ),
                        confidence=0.80,
                        evidence={
                            "overlap_ratio": round(ratio, 3),
                            "threshold": threshold,
                            "shape_a": a.name,
                            "shape_b": b.name,
                        },
                    )
