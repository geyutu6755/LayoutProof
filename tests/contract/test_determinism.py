"""Reproducibility: scans of the same file must be byte-stable once the
wall-clock timestamp (the only inherently changing field) is removed."""

from __future__ import annotations

import json
import re

import helpers_decks as decks
from layoutproof.engine import scan_file
from layoutproof.report import write_json

_TS_RE = re.compile(rb'"timestamp":\s*"[^"]*"')
_TS_STR_RE = re.compile(r'"timestamp":\s*"[^"]*"')


def _without_timestamp(payload: dict) -> dict:
    payload = dict(payload)
    payload.pop("timestamp", None)
    return payload


def _normalise_json_bytes(raw: bytes) -> bytes:
    return _TS_RE.sub(b'"timestamp": ""', raw) if isinstance(raw, bytes) else raw


def test_two_scans_produce_identical_payload_without_timestamp(tmp_path):
    path = decks.save_error_deck(tmp_path / "error.pptx")
    first = _without_timestamp(scan_file(path, profile="full").to_dict())
    second = _without_timestamp(scan_file(path, profile="full").to_dict())
    assert json.dumps(first, sort_keys=True, ensure_ascii=False) == \
           json.dumps(second, sort_keys=True, ensure_ascii=False)


def test_issue_sequence_is_deterministic(tmp_path):
    path = decks.save_error_deck(tmp_path / "error.pptx")
    a = scan_file(path, profile="full")
    b = scan_file(path, profile="full")
    assert [(i.rule_id, i.slide_number, i.shape_id) for i in a.issues] == \
           [(i.rule_id, i.slide_number, i.shape_id) for i in b.issues]
    assert a.summarize().to_dict() == b.summarize().to_dict()


def test_written_json_files_are_byte_stable_after_timestamp_normalisation(tmp_path):
    path = decks.save_clean_deck(tmp_path / "clean.pptx")
    r1 = scan_file(path)
    f1 = write_json(r1, tmp_path / "a.json")
    r2 = scan_file(path)
    f2 = write_json(r2, tmp_path / "b.json")
    assert _normalise_json_bytes(f1.read_bytes()) == _normalise_json_bytes(f2.read_bytes())


def test_timestamp_field_present_but_otherwise_constant(tmp_path):
    path = decks.save_clean_deck(tmp_path / "clean.pptx")
    a = scan_file(path).to_dict()
    b = scan_file(path).to_dict()
    assert a["timestamp"] and b["timestamp"]
    body_a = _TS_STR_RE.sub("", json.dumps(a, sort_keys=True))
    body_b = _TS_STR_RE.sub("", json.dumps(b, sort_keys=True))
    assert body_a == body_b
