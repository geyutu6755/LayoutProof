"""Detection rule engine: discovery, profiles and execution."""

from __future__ import annotations

from ..config import QualityConfig
from ..models import RuleId
from ..parsing import PresentationModel
from .base import Rule, get_rule_classes, load_all_rules, register_rule

# High-confidence, low-false-positive defaults for the first-minute experience.
CORE_PROFILE = [
    RuleId.OFFSLIDE_OBJECT.value,
    RuleId.FONT_TOO_SMALL.value,
    RuleId.TEXT_OVERFLOW.value,
    RuleId.UNFINISHED_PLACEHOLDER.value,
    RuleId.MEDIA_BROKEN.value,
    RuleId.BROKEN_REFERENCE.value,
    RuleId.STRUCTURE_ANOMALY.value,
]

FULL_PROFILE = [r.value for r in RuleId]

PROFILES = {
    "core": CORE_PROFILE,
    "full": FULL_PROFILE,
}

__all__ = [
    "CORE_PROFILE",
    "FULL_PROFILE",
    "PROFILES",
    "Rule",
    "get_rule_classes",
    "load_all_rules",
    "register_rule",
    "resolve_profile",
    "run_rules",
]


def resolve_profile(profile: str) -> list[str]:
    if profile not in PROFILES:
        raise ValueError(f"Unknown profile {profile!r}; choose from {sorted(PROFILES)}")
    return list(PROFILES[profile])


def run_rules(
    model: PresentationModel,
    config: QualityConfig,
    profile: str = "core",
) -> list:
    load_all_rules()
    # Explicit enabled/disabled config wins over the profile.
    explicit = bool(config.enabled_rules or config.disabled_rules)
    profile_rules = set(resolve_profile(profile))
    issues = []
    for rule_id, rule_cls in get_rule_classes().items():
        if not explicit and rule_id not in profile_rules:
            continue
        if not config.is_rule_enabled(rule_id):
            continue
        rule = rule_cls(config)
        issues.extend(rule.check(model))
    # Deterministic ordering: slide, then shape, then rule id.
    issues.sort(
        key=lambda i: (
            i.slide_index,
            i.shape_id or "",
            i.rule_id,
        )
    )
    return issues
