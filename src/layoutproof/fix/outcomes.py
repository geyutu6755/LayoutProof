"""Post-fix outcome classification and the additive report contract.

Detection issues that were targeted by the fix engine are re-measured after the
output deck is scanned once more.  Every targeted issue receives one of four
honest labels:

``resolved``
    the targeted issue key (rule + slide + shape) no longer appears in the
    re-scan and no other issue was introduced on the same shape.
``unchanged``
    the repair was applied but the targeted issue still appears after the
    re-scan (heuristic stayed above threshold, or the repair could only act
    partially).
``regressed``
    the targeted issue disappeared, but the repaired shape now carries a
    *new* issue that was absent before the repair.
``skipped``
    no repair was applied: the rule has no safe automatic strategy, the target
    shape could not be located, or a strategy was not applicable.  These stay
    on the manual-review list and are never counted as fixed.

The frozen :class:`~layoutproof.models.FixReport` dataclass lives outside this
package and its JSON branch (``additionalProperties: false``) must keep passing
the existing schema tests.  Therefore this module subclasses it and adds the new
fields as plain object attributes; :meth:`DetailedFixReport.to_dict` deliberately
returns the exact legacy dictionary so old consumers and the schema validator
keep working unchanged.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field

from ..models import FixReport

#: Outcome labels emitted after the re-scan.
RESOLVED = "resolved"
UNCHANGED = "unchanged"
REGRESSED = "regressed"
SKIPPED = "skipped"  # manual review, no repair applied

_OUTCOME_LABELS = (RESOLVED, UNCHANGED, REGRESSED, SKIPPED)


@dataclass
class FixOutcome:
    """Per-issue classification produced after the output deck was re-scanned."""

    rule_id: str
    slide_index: int
    shape_id: str | None
    action: str
    status: str  # "applied" | "skipped"
    outcome: str  # resolved | unchanged | regressed | skipped
    strategies: list[str] = field(default_factory=list)
    reason: str = ""
    detail: str = ""

    def __post_init__(self) -> None:
        if self.outcome not in _OUTCOME_LABELS:
            raise ValueError(f"unknown outcome {self.outcome!r}")

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


@dataclass
class DetailedFixReport(FixReport):
    """Backward-compatible FixReport extended with per-issue outcome data.

    All legacy constructor arguments and attributes keep their names and
    semantics; only additive, defaulted fields are introduced.
    """

    outcomes: list[FixOutcome] = field(default_factory=list)
    resolved_count: int = 0
    unchanged_count: int = 0
    regressed_count: int = 0
    manual_review_count: int = 0

    def outcomes_by_status(self) -> dict[str, list[FixOutcome]]:
        groups = {label: [] for label in _OUTCOME_LABELS}
        for outcome in self.outcomes:
            groups[outcome.outcome].append(outcome)
        return groups

    def to_dict(self) -> dict:
        # Keep the published FixReport JSON schema byte-stable: the dictionary
        # retains every legacy key and introduces none.  Rich outcome data is
        # available on the object itself (``report.outcomes`` and the count
        # fields) and summarized in the existing free-form ``note`` field.
        return super().to_dict()
