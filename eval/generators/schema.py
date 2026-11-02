"""Ground-truth schema constants and small builders for the eval corpus.

A judgement record answers one of three questions for one rule on one file:

* ``positive`` - the defect was deliberately constructed; the rule should fire
  at least once (judged under the listed profile scope).
* ``negative`` - a deliberately *clean* sample for that rule; the rule must
  stay silent on this file.
* ``unknown``  - behaviour depends on a renderer, font substitution or a
  heuristic we cannot derive offline; excluded from the confusion matrix and
  listed under "cannot be judged".

Only explicit positive/negative records feed Precision/Recall/F1; an omitted
rule on a file is implicitly unknown, so we never manufacture TN support.
"""

from __future__ import annotations

# Deterministic severity per rule id (mirrors layoutproof.models.RULES).
SEVERITY = {
    "offslide_object": "error",
    "font_too_small": "error",
    "text_overflow": "warning",
    "unfinished_placeholder": "warning",
    "media_broken": "error",
    "broken_reference": "error",
    "structure_anomaly": "error",
    "object_overlap": "warning",
    "low_contrast": "warning",
    "blank_slide": "warning",
    "missing_alt_text": "info",
    "cjk_typography": "warning",
}

CORE_RULES = [
    "offslide_object",
    "font_too_small",
    "text_overflow",
    "unfinished_placeholder",
    "media_broken",
    "broken_reference",
    "structure_anomaly",
]
FULL_RULES = [
    *CORE_RULES,
    "object_overlap",
    "low_contrast",
    "blank_slide",
    "missing_alt_text",
    "cjk_typography",
]


def scope_for(rule_id: str) -> str:
    return "both" if rule_id in CORE_RULES else "full"


def J(rule_id: str, expect: str, basis: str, note: str = "", *,
      profiles: str | None = None, expected_count: int | None = None) -> dict:
    if expect not in ("positive", "negative", "unknown"):
        raise ValueError(f"bad expect {expect}")
    return {
        "rule_id": rule_id,
        "expect": expect,
        "profiles": profiles or scope_for(rule_id),
        "expected_severity": SEVERITY.get(rule_id),
        "basis": basis,
        "note": note,
        "expected_count": expected_count,
    }


def record(
    content_id: str,
    file_rel: str,
    source: str,
    language: str,
    aspect: str,
    scenario: str,
    description: str,
    judgements: list[dict],
    *,
    parent: str | None = None,
    expected_status: str = "ok",
    build_note: str = "",
) -> dict:
    return {
        "content_id": content_id,
        "file": file_rel,
        "source": source,
        "language": language,
        "aspect": aspect,
        "scenario": scenario,
        "description": description,
        "parent": parent,
        "expected_status": expected_status,
        "build_note": build_note,
        "judgements": judgements,
    }
