"""Report export endpoints: JSON envelope and self-contained HTML download."""

from __future__ import annotations

import json

import _decks

from conftest import (
    fix_session,
    http_request,
    request_json,
    scan_session,
    upload_deck,
)


def _upload_scan(base, path):
    _, _, up = upload_deck(base, path)
    scan_session(base, up["session_id"])
    return up["session_id"]


def test_json_report_after_scan_validates_schema(web_server, tmp_path):
    base, _ = web_server
    sid = _upload_scan(base, _decks.save_clean_deck(tmp_path / "clean.pptx"))
    status, headers, raw = http_request(base, "GET", f"/api/report/json/{sid}")
    assert status == 200
    assert "application/json" in headers["Content-Type"]
    assert "attachment" in headers["Content-Disposition"]
    envelope = json.loads(raw.decode("utf-8"))
    assert envelope["validation"]["scan"] == "ScanResult"
    assert envelope["fix"] is None
    assert envelope["scan"]["summary"]["total"] == 0


def test_json_report_after_fix_includes_fix_and_after_scan(web_server, tmp_path):
    base, _ = web_server
    sid = _upload_scan(base, _decks.save_broken_deck(tmp_path / "broken.pptx"))
    fix_session(base, sid)
    status, _, raw = http_request(base, "GET", f"/api/report/json/{sid}")
    assert status == 200
    envelope = json.loads(raw.decode("utf-8"))
    assert envelope["validation"]["fix"] == "FixReport"
    assert envelope["fix"]["before"]["total"] > envelope["fix"]["after"]["total"]
    assert envelope["after_scan"] is not None


def test_html_report_is_downloadable_in_both_languages(web_server, tmp_path):
    base, _ = web_server
    sid = _upload_scan(base, _decks.save_clean_deck(tmp_path / "clean.pptx"))
    for lang in ("en", "zh"):
        status, headers, raw = http_request(base, "GET", f"/api/report/html/{sid}?lang={lang}")
        assert status == 200
        assert "text/html" in headers["Content-Type"]
        assert "attachment" in headers["Content-Disposition"]
        html = raw.decode("utf-8")
        assert "LayoutProof" in html
        assert 'src="http' not in html


def test_reports_unknown_session_404(web_server):
    base, _ = web_server
    for path in (
        "/api/report/json/" + "a" * 16,
        "/api/report/html/" + "a" * 16,
    ):
        status, _, payload = request_json(base, "GET", path)
        assert status == 404
        assert payload["error"] == "not_found"


def test_report_before_scan_is_404(web_server, tmp_path):
    base, _ = web_server
    _, _, up = upload_deck(base, _decks.save_clean_deck(tmp_path / "clean.pptx"))
    status, _, payload = request_json(base, "GET", f"/api/report/json/{up['session_id']}")
    assert status == 404
    assert payload["error"] == "scan_not_ready"
