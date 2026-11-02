"""POST /api/fix, GET /api/download/fixed/<sid>: delegated safe repair loop."""

from __future__ import annotations

import hashlib

import _decks

from conftest import (
    fix_session,
    http_request,
    request_json,
    scan_session,
    upload_deck,
)


def _upload_scan_broken(base, tmp_path):
    path = _decks.save_broken_deck(tmp_path / "broken.pptx")
    _, _, up = upload_deck(base, path)
    scan_session(base, up["session_id"])
    return up["session_id"]


def test_fix_creates_output_and_lowers_issue_count(web_server, tmp_path):
    base, httpd = web_server
    sid = _upload_scan_broken(base, tmp_path)
    status, _, payload = fix_session(base, sid)
    assert status == 200

    fix = payload["fix"]
    assert fix["created"] is True
    assert fix["before"]["total"] > fix["after"]["total"]
    assert len(fix["applied"]) >= 1
    assert (
        payload["after_overview"]["summary"]["total"]
        < payload["before_overview"]["summary"]["total"]
    )
    assert "after_scan" in payload

    session = httpd.app.store.get(sid)
    assert session.fixed_path.is_file()
    assert session.fixed_path.name == "fixed.pptx"


def test_source_deck_bytes_are_never_modified(web_server, tmp_path):
    base, httpd = web_server
    sid = _upload_scan_broken(base, tmp_path)
    session = httpd.app.store.get(sid)
    before = hashlib.sha256(session.source_path.read_bytes()).hexdigest()

    fix_session(base, sid)
    after = hashlib.sha256(session.source_path.read_bytes()).hexdigest()
    assert before == after


def test_fixed_download_is_an_attachment_pptx(web_server, tmp_path):
    base, _ = web_server
    sid = _upload_scan_broken(base, tmp_path)
    fix_session(base, sid)

    status, headers, raw = http_request(base, "GET", f"/api/download/fixed/{sid}")
    assert status == 200
    assert "presentationml" in headers["Content-Type"]
    assert "attachment" in headers["Content-Disposition"]
    assert raw[:2] == b"PK"

    _, _, source_up = upload_deck(base, _decks.save_clean_deck(tmp_path / "other.pptx"))
    scan_session(base, source_up["session_id"])
    status2, _, _ = http_request(base, "GET", f"/api/download/fixed/{source_up['session_id']}")
    assert status2 == 404


def test_fix_unknown_session_returns_404(web_server):
    base, _ = web_server
    status, _, payload = fix_session(base, "0" * 16)
    assert status == 404
    assert payload["error"] == "not_found"


def test_state_reports_fixed_after_repair(web_server, tmp_path):
    base, _ = web_server
    sid = _upload_scan_broken(base, tmp_path)
    fix_session(base, sid)
    status, _, state = request_json(base, "GET", f"/api/state/{sid}")
    assert status == 200
    assert state["fixed"] is True
    assert state["has_fixed_file"] is True
    assert state["fix_success"] in (True, False)
