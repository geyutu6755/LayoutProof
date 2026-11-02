"""POST /api/scan and GET /api/state: detection results delegated to scan_file."""

from __future__ import annotations

import _decks

from conftest import json_post, request_json, scan_session, upload_deck


def _upload(base, path):
    _, _, payload = upload_deck(base, path)
    return payload["session_id"]


def test_clean_deck_scans_with_zero_issues(web_server, tmp_path):
    base, _ = web_server
    sid = _upload(base, _decks.save_clean_deck(tmp_path / "clean.pptx", slides=2))
    status, _, payload = scan_session(base, sid)
    assert status == 200
    assert payload["scan"]["status"] == "ok"
    assert payload["overview"]["summary"]["total"] == 0
    assert len(payload["overview"]["per_slide"]) == 2
    assert payload["scan"]["slide_count"] == 2


def test_broken_deck_scan_reports_deterministic_errors(web_server, tmp_path):
    base, _ = web_server
    sid = _upload(base, _decks.save_broken_deck(tmp_path / "broken.pptx"))
    status, _, payload = scan_session(base, sid)
    assert status == 200
    summary = payload["overview"]["summary"]
    assert summary["error"] >= 1
    rules = {issue["rule_id"] for issue in payload["scan"]["issues"]}
    assert "font_too_small" in rules
    assert "offslide_object" in rules

    per_slide_total = sum(bucket["total"] for bucket in payload["overview"]["per_slide"])
    document_total = payload["overview"]["document"]["total"]
    assert per_slide_total + document_total == summary["total"]


def test_issues_carry_location_and_fixability_metadata(web_server, tmp_path):
    base, _ = web_server
    sid = _upload(base, _decks.save_broken_deck(tmp_path / "broken.pptx"))
    _, _, payload = scan_session(base, sid)
    located = [i for i in payload["scan"]["issues"] if i["normalized_location"]]
    assert located, "off-slide / small-font findings should carry geometry"
    for issue in located:
        assert issue["severity"] in {"error", "warning", "info"}
        assert "fixable" in issue


def test_scan_unknown_session_returns_404(web_server):
    base, _ = web_server
    status, _, payload = json_post(base, "/api/scan", {"session_id": "f" * 16})
    assert status == 404
    assert payload["error"] == "not_found"


def test_scan_rejects_unknown_profile(web_server, tmp_path):
    base, _ = web_server
    sid = _upload(base, _decks.save_clean_deck(tmp_path / "clean.pptx"))
    status, _, payload = json_post(base, "/api/scan", {"session_id": sid, "profile": "nope"})
    assert status == 400
    assert payload["error"] == "invalid_profile"


def test_state_endpoint_reflects_scan_then_fix_flags(web_server, tmp_path):
    base, _ = web_server
    sid = _upload(base, _decks.save_clean_deck(tmp_path / "clean.pptx"))
    scan_session(base, sid)
    status, _, state = request_json(base, "GET", f"/api/state/{sid}")
    assert status == 200
    assert state["scanned"] is True
    assert state["fixed"] is False
    assert state["has_fixed_file"] is False

    missing = request_json(base, "GET", "/api/state/" + "0" * 16)
    assert missing[0] == 404
