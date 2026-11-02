"""JSON output contract: every serialised result must validate schema.json.

Covers real scanned decks (ok and error status), out-of-range normalised
coordinates that are legal for off-slide objects, and negative controls that
must be rejected.
"""

from __future__ import annotations

import jsonschema
import pytest

import helpers_decks as decks
from layoutproof.engine import scan_file
from layoutproof.report import validate_output, write_json


def test_real_clean_deck_validates_against_schema(tmp_path):
    path = decks.save_clean_deck(tmp_path / "clean.pptx")
    result = scan_file(path, profile="full")
    assert result.status == "ok"
    assert validate_output(result.to_dict()) == "ScanResult"


def test_error_status_payload_still_validates_schema(tmp_path):
    bad = tmp_path / "not_a_deck.pptx"
    bad.write_bytes(b"PK\x03\x04 corrupted archive without central directory")
    result = scan_file(bad)
    assert result.status == "error"
    assert validate_output(result.to_dict()) == "ScanResult"
    assert result.error


def test_real_offslide_coordinates_outside_unit_range_validate(tmp_path):
    """Negative x/y and width/height >1 are legal for off-slide objects."""
    path = decks.save_error_deck(tmp_path / "error.pptx")
    result = scan_file(path, profile="full")
    assert result.status == "ok"
    payload = result.to_dict()
    assert validate_output(payload) == "ScanResult"
    offslide = [i for i in payload["issues"] if i["rule_id"] == "offslide_object"]
    assert offslide, "error deck must contain a real off-slide finding"
    loc = offslide[0]["normalized_location"]
    assert loc["x"] > 1.0  # begins past the right edge
    assert loc["width"] >= 0 and loc["height"] >= 0


def test_write_json_on_real_deck_round_trips_schema(tmp_path):
    path = decks.save_clean_deck(tmp_path / "clean.pptx")
    result = scan_file(path)
    out = write_json(result, tmp_path / "report.json")
    import json

    data = json.loads(out.read_text(encoding="utf-8"))
    assert validate_output(data) == "ScanResult"


# ---------------------------------------------------------------------------
# Negative controls: invalid shapes must be rejected, not tolerated
# ---------------------------------------------------------------------------
def test_confidence_out_of_range_rejected(tmp_path):
    path = decks.save_clean_deck(tmp_path / "clean.pptx")
    result = scan_file(path)
    data = result.to_dict()
    data["issues"].append({
        "rule_id": "low_contrast",
        "severity": "warning",
        "slide_index": 0,
        "slide_number": 1,
        "location": None,
        "normalized_location": None,
        "detail": "tampered confidence",
        "confidence": 1.7,  # outside [0,1]
        "fixable": True,
        "fix_id": None,
        "evidence": {},
    })
    with pytest.raises(jsonschema.ValidationError):
        validate_output(data)


def test_unknown_severity_rejected(tmp_path):
    from layoutproof.models import Issue, ScanResult

    result = ScanResult(
        file_path="/x/clean.pptx", file_name="clean.pptx",
        slide_count=1, slide_width=9144000, slide_height=6858000,
        issues=[Issue(rule_id="low_contrast", slide_index=0, slide_number=1)],
    )
    data = result.to_dict()
    data["issues"][0]["severity"] = "critical"
    with pytest.raises(jsonschema.ValidationError):
        validate_output(data)


def test_unknown_extra_property_rejected(tmp_path):
    path = decks.save_clean_deck(tmp_path / "clean.pptx")
    data = scan_file(path).to_dict()
    data["injected_future_field"] = 123
    with pytest.raises(jsonschema.ValidationError):
        validate_output(data)


def test_missing_required_field_rejected():
    payload = {
        "schema_version": "1.0",
        "tool": {"name": "layoutproof", "version": "0.1.0a1"},
        "file": {"path": "x", "name": "x"},
        "status": "ok",
        "error": None,
        "timestamp": "t",
        "summary": {"error": 0, "warning": 0, "info": 0, "total": 0},
        "issues": [],
        "config": {},
    }
    payload.pop("slide_count", None)  # required by the ScanResult schema
    with pytest.raises(jsonschema.ValidationError):
        validate_output(payload)


def test_unrecognisable_payload_kind_rejected():
    with pytest.raises(Exception):
        validate_output({"hello": "world"})


def test_tool_version_matches_installed_metadata():
    """The reported version must track the installed distribution, not a constant."""
    from importlib import metadata

    from layoutproof import TOOL_VERSION, __version__
    from layoutproof.models import TOOL_NAME

    assert metadata.version(TOOL_NAME) == TOOL_VERSION
    assert __version__ == TOOL_VERSION
    assert TOOL_VERSION  # non-empty string
