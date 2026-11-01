"""JSON serialisation and schema validation for LayoutProof reports."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import jsonschema

from ..models import FixReport, ScanResult

_SCHEMA_PATH = Path(__file__).with_name("schema.json")


def _load_schema() -> dict[str, Any]:
    with _SCHEMA_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _detect_kind(data: dict[str, Any]) -> str:
    """Pick the right schema branch for a serialised report dict."""
    if "issues" in data and "summary" in data:
        return "ScanResult"
    if "applied" in data and "source_path" in data:
        return "FixReport"
    raise ValueError(
        "Cannot detect report kind: expected a ScanResult (issues/summary) "
        "or FixReport (applied/source_path) dictionary."
    )


def _validator_for(schema: dict[str, Any], kind: str):
    """Return a validator whose root *is* the chosen branch but which still
    carries the shared ``definitions`` so ``$ref`` pointers resolve."""
    branch = schema["definitions"][kind]
    root = copy.deepcopy(schema)
    for key in ("type", "required", "properties", "additionalProperties"):
        if key in branch:
            root[key] = branch[key]
        else:
            root.pop(key, None)
    return jsonschema.Draft202012Validator(root)


def validate_output(data: dict[str, Any]) -> str:
    """Validate a serialised report dict against ``schema.json``.

    Returns the matched schema kind (``"ScanResult"`` or ``"FixReport"``) on
    success. Raises ``jsonschema.ValidationError`` on mismatch.
    """
    schema = _load_schema()
    kind = _detect_kind(data)
    _validator_for(schema, kind).validate(data)
    return kind


def write_json(result: ScanResult | FixReport, path: str | Path) -> Path:
    """Serialise a ScanResult or FixReport to pretty JSON and validate it."""
    path = Path(path)
    data = result.to_dict()
    validate_output(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    return path
