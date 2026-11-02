"""Path-traversal and resource-location negatives for the web surface.

The server never resolves client-supplied filenames or ids against the
filesystem; these tests probe encoded traversal strings and unknown ids.
"""

from __future__ import annotations

import _decks

from conftest import http_request, request_json, scan_session, upload_deck


def test_static_asset_traversal_never_leaves_static_dir(web_server):
    base, _ = web_server
    probes = [
        "/static/../app.js",
        "/static/%2e%2e%2fapp.js",
        "/static/%2e%2e%2f%2e%2e%2fetc%2fpasswd",
        "/static/missing.txt",
    ]
    for path in probes:
        status, _, _ = http_request(base, "GET", path)
        assert status in (400, 404), path


def test_download_route_rejects_traversal_session_ids(web_server, tmp_path):
    base, _ = web_server
    _, _, up = upload_deck(base, _decks.save_clean_deck(tmp_path / "clean.pptx"))
    scan_session(base, up["session_id"])
    probes = [
        "/api/download/fixed/..%2f..%2fetc",
        "/api/download/fixed/" + ".." * 4,
        "/api/download/fixed/" + "f" * 16,
    ]
    for path in probes:
        status, _, _ = http_request(base, "GET", path)
        assert status in (400, 404), path


def test_report_routes_reject_traversal_and_unknown_ids(web_server):
    base, _ = web_server
    probes = [
        "/api/report/json/..%2f..",
        "/api/report/html/..%2f..",
        "/api/render/..%2f..",
        "/api/state/..%2f..",
    ]
    for path in probes:
        status, _, payload = request_json(base, "GET", path)
        assert status in (400, 404), path
        if payload is not None:
            assert payload["error"] in {"not_found", "invalid_render_stage"}


def test_render_image_route_rejects_unknown_and_escaped_ids(web_server):
    base, _ = web_server
    probes = [
        "/api/image/..%2f..%2fbefore%2f1.png",
        "/api/image/" + "g" * 16 + "/before/1.png",
    ]
    for path in probes:
        status, _, _ = http_request(base, "GET", path)
        assert status in (400, 404), path


def test_only_server_created_files_are_served_under_session(web_server, tmp_path):
    base, httpd = web_server
    _, _, up = upload_deck(base, _decks.save_clean_deck(tmp_path / "clean.pptx"))
    session = httpd.app.store.get(up["session_id"])
    # Every managed artifact resolves strictly inside the session directory.
    source = session.source_path.resolve()
    root = session.root.resolve()
    assert root in source.parents
    # No sibling directory escapes into the user-provided temp path layout.
    assert session.render_dir("before").parent == root
