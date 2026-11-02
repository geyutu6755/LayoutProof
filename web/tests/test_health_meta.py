"""GET /api/health, /api/meta, the index page and static asset safety."""

from __future__ import annotations

import re

from conftest import http_request, request_json


def test_health_reports_offline_mode_and_renderer(web_server):
    base, _ = web_server
    status, _, payload = request_json(base, "GET", "/api/health")
    assert status == 200
    assert payload["ok"] is True
    assert payload["offline"] is True
    assert payload["tool"]["name"] == "layoutproof"
    assert payload["renderer"]["available"] in (True, False)
    assert "python" in payload


def test_meta_lists_bilingual_catalog_and_profiles(web_server):
    base, _ = web_server
    status, _, meta = request_json(base, "GET", "/api/meta")
    assert status == 200
    assert meta["languages"] == ["en", "zh"]
    assert set(meta["profiles"]) == {"core", "full"}
    assert len(meta["rules"]) >= 12
    severities = set(meta["severities"])
    assert severities == {"error", "warning", "info"}
    for rule in meta["rules"]:
        assert rule["severity"] in severities
        assert rule["title_en"]
        assert rule["title_zh"]
        assert rule["recommendation_en"]
        assert rule["recommendation_zh"]
        assert isinstance(rule["fixable"], bool)


def test_index_page_served_with_only_local_assets(web_server):
    base, _ = web_server
    status, headers, raw = http_request(base, "GET", "/")
    assert status == 200
    assert "text/html" in headers["Content-Type"]
    html = raw.decode("utf-8")
    assert "LayoutProof" in html
    assert 'src="http' not in html
    assert 'href="http' not in html
    referenced = re.findall(r'(?:src|href)="(/static/[^"]+)"', html)
    assert referenced, "index must reference its local script/style assets"
    for asset in referenced:
        s, _, body = http_request(base, "GET", asset)
        assert s == 200, asset
        assert b"https://" not in body


def test_static_assets_contain_no_external_network_urls(web_server):
    base, _ = web_server
    for asset in ("style.css", "app.js", "i18n.js", "logic.js"):
        status, _, body = http_request(base, "GET", f"/static/{asset}")
        assert status == 200, asset
        assert b"http://" not in body and b"https://" not in body, asset


def test_unknown_api_route_returns_json_404(web_server):
    base, _ = web_server
    status, _, payload = request_json(base, "GET", "/api/does-not-exist")
    assert status == 404
    assert payload["error"] == "not_found"


def test_non_get_request_to_index_is_rejected(web_server):
    base, _ = web_server
    status, _, payload = request_json(base, "POST", "/")
    assert status == 405
    assert payload["error"] == "method_not_allowed"
