"""Base classes and registry for detection rules.

Each rule is a small, focused class that receives the parsed
:class:`~layoutproof.parsing.PresentationModel` and yields
:class:`~layoutproof.models.Issue` objects. Rules register themselves through
the ``@register_rule`` decorator so the engine can discover them without a
hand-maintained import list.
"""

from __future__ import annotations

import abc
from collections.abc import Iterable

from ..config import QualityConfig
from ..models import Issue, Location, RuleId
from ..parsing import PresentationModel, ShapeModel, SlideModel
from ..parsing.geometry import Rect


class Rule(abc.ABC):
    """Abstract detection rule."""

    rule_id: RuleId
    confidence: float = 1.0

    def __init__(self, config: QualityConfig) -> None:
        self.config = config

    @property
    def rule_id_value(self) -> str:
        return self.rule_id.value if isinstance(self.rule_id, RuleId) else str(self.rule_id)

    def enabled(self) -> bool:
        return self.config.is_rule_enabled(self.rule_id_value)

    @abc.abstractmethod
    def check(self, model: PresentationModel) -> Iterable[Issue]:
        """Yield zero or more issues for the whole presentation."""

    # Convenience helpers shared by concrete rules -------------------------
    def _issue(
        self,
        slide: SlideModel,
        shape: ShapeModel | None,
        location=None,
        detail: str = "",
        confidence: float | None = None,
        evidence: dict | None = None,
    ) -> Issue:
        loc = location if location is not None else (shape.rect if shape else None)
        if isinstance(loc, Rect):
            loc = Location(loc.x, loc.y, loc.width, loc.height)
        return Issue(
            rule_id=self.rule_id_value,
            slide_index=slide.index,
            slide_number=slide.number,
            shape_id=shape.id if shape else None,
            shape_name=shape.name if shape else None,
            location=loc,
            detail=detail,
            confidence=self.confidence if confidence is None else confidence,
            evidence=evidence or {},
        )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
_REGISTRY: dict[str, type[Rule]] = {}


def register_rule(cls: type[Rule]) -> type[Rule]:
    rid = _rule_id_value(cls)
    if rid not in _REGISTRY:
        _REGISTRY[rid] = cls
    return cls


def _rule_id_value(cls: type[Rule]) -> str:
    rid = cls.rule_id
    return rid.value if isinstance(rid, RuleId) else str(rid)


def get_rule_classes() -> dict[str, type[Rule]]:
    return dict(_REGISTRY)


def load_all_rules() -> None:
    """Import every rule module so decorators run and populate the registry."""

    import importlib
    import pathlib
    import pkgutil

    package_dir = pathlib.Path(__file__).parent
    for module_info in pkgutil.iter_modules([str(package_dir)]):
        name = module_info.name
        if name.startswith("_") or name in ("base",):
            continue
        importlib.import_module(f"{__package__}.{name}")
