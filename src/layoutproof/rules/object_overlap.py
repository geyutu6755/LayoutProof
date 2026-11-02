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
    return not any(hint in name for hint in decorative_hints)


def _absorbed_label_ids(candidates: list[ShapeModel]) -> set[str]:
    """Return ids of text labels that ride on a filled card/background shape.

    A text frame fully contained inside another *non-text* content shape is a
    label sitting on that shape (e.g. the caption on a card), not an
    independent colliding element.  It must not be paired on its own, or the
    same visual collision gets reported once per label attached to either
    card instead of once for the card-on-card collision itself.
    """
    attached: set[str] = set()
    for label in candidates:
        if not label.text.strip() or label.rect is None:
            continue
        for card in candidates:
            if card is label or card.rect is None:
                continue
            if card.text.strip():
                continue  # only absorb into a plain (non-text) filled shape
            if card.rect.contains(label.rect):
                attached.add(label.id)
                break
    return attached


@register_rule
class ObjectOverlapRule(Rule):
    rule_id = RuleId.OBJECT_OVERLAP
    confidence = 0.80

    # Image+text overlay is a deliberate design (caption/badge over a photo).
    # Only flag it when the text covers almost the whole picture, i.e. the
    # picture is genuinely obscured rather than partially labeled.
    PICTURE_TEXT_COVER_THRESHOLD = 0.9

    def check(self, model: PresentationModel) -> Iterable[Issue]:
        threshold = self.config.overlap_ratio_threshold
        hints = [h.lower() for h in self.config.decorative_name_hints]
        for slide in model.slides:
            candidates = [s for s in slide.shapes if _is_content_shape(s, hints)]
            absorbed = _absorbed_label_ids(candidates)
            shapes = [s for s in candidates if s.id not in absorbed]
            # Unordered pairs only: each colliding pair is reported once.
            for i in range(len(shapes)):
                for j in range(i + 1, len(shapes)):
                    a, b = shapes[i], shapes[j]
                    inter = a.rect.intersection(b.rect)
                    if inter is None:
                        continue
                    # Picture vs text: partial overlap is intentional overlay,
                    # not a collision. Flag only when the text nearly covers
                    # the entire picture.
                    pic = a if a.is_picture else (b if b.is_picture else None)
                    other = b if pic is a else a
                    if pic is not None and other.text.strip():
                        cover = inter.area / pic.rect.area
                        if cover < self.PICTURE_TEXT_COVER_THRESHOLD:
                            continue
                        ratio = cover
                    else:
                        ratio = a.rect.overlap_ratio(b.rect)
                    if ratio < threshold:
                        continue
                    yield self._issue(
                        slide,
                        a,
                        location=inter,
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
