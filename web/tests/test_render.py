"""Render manifest and slide image routes; static fallback must be disclosed."""

from __future__ import annotations

import _decks

from conftest import http_request, request_json, scan_session, upload_deck


def _ready_clean_session(base, tmp_path):
    path = _decks.save_clean_deck(tmp_path / "clean.pptx")
    _, _, up = upload_deck(base, path)
    scan_session(base, up["session_id"])
    return up["session_id"]


def test_before_render_manifest_is_rendered_or_explicit_fallback(web_server, tmp_path):
    base, _ = web_server
    sid = _ready_clean_session(base, tmp_path)
    status, _, payload = request_json(base, "GET", f"/api/render/{sid}/before")
    assert status == 200
    manifest = payload["render"]
    assert manifest["status"] in {"rendered", "static_fallback"}
    assert "renderer" in manifest
    if manifest["rendered"]:
        assert manifest["slide_count"] >= 1
        assert manifest["slides"][0]["width_px"] > 0
    else:
        assert manifest["reason"]


def test_image_route_matches_manifest_state(web_server, tmp_path):
    base, _ = web_server
    sid = _ready_clean_session(base, tmp_path)
    _, _, payload = request_json(base, "GET", f"/api/render/{sid}/before")
    manifest = payload["render"]

    status, headers, raw = http_request(base, "GET", f"/api/image/{sid}/before/1.png")
    if manifest["rendered"]:
        assert status == 200
        assert headers["Content-Type"] == "image/png"
        assert raw[:8] == b"\x89PNG\r\n\x1a\n"
    else:
        assert status == 404


def test_after_render_before_fix_is_404(web_server, tmp_path):
    base, _ = web_server
    sid = _ready_clean_session(base, tmp_path)
    status, _, payload = request_json(base, "GET", f"/api/render/{sid}/after")
    assert status == 404
    assert payload["error"] == "fixed_deck_not_ready"


def test_invalid_render_stage_returns_400(web_server, tmp_path):
    base, _ = web_server
    sid = _ready_clean_session(base, tmp_path)
    status, _, payload = request_json(base, "GET", f"/api/render/{sid}/bogus")
    assert status == 400
    assert payload["error"] == "invalid_render_stage"


def test_render_unknown_session_404(web_server):
    base, _ = web_server
    status, _, _ = request_json(base, "GET", "/api/render/" + "e" * 16 + "/before")
    assert status == 404


def test_image_unknown_session_404(web_server):
    base, _ = web_server
    status, _, _ = http_request(base, "GET", "/api/image/" + "d" * 16 + "/before/1.png")
    assert status == 404


def test_image_non_numeric_slide_number_400(web_server, tmp_path):
    base, _ = web_server
    sid = _ready_clean_session(base, tmp_path)
    status, _, _ = http_request(base, "GET", f"/api/image/{sid}/before/abc.png")
    assert status == 400
