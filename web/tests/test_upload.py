"""POST /api/upload: happy path plus every negative safety branch."""

from __future__ import annotations

import warnings
import zipfile

import _decks

from conftest import build_multipart, request_json, upload_deck


def _post_multipart(base: str, filename: str, content: bytes, **kwargs):
    body, headers = build_multipart(filename, content, **kwargs)
    return request_json(base, "POST", "/api/upload", body=body, headers=headers)


def test_clean_deck_uploaded_to_server_managed_session(web_server, tmp_path):
    base, httpd = web_server
    path = _decks.save_clean_deck(tmp_path / "clean.pptx")
    status, _, payload = upload_deck(base, path)
    assert status == 201
    sid = payload["session_id"]
    assert len(sid) == 16
    assert all(ch in "0123456789abcdef" for ch in sid)
    assert payload["file_name"].endswith(".pptx")
    assert payload["size_bytes"] > 0
    assert payload["archive"]["entries"] > 0

    session = httpd.app.store.get(sid)
    # On-disk name is fixed; the client filename never reaches a path.
    assert session.source_path.name == "source.pptx"
    assert session.source_path.is_file()


def test_non_multipart_body_rejected(web_server):
    base, _ = web_server
    status, _, payload = request_json(
        base,
        "POST",
        "/api/upload",
        body=b"not multipart",
        headers={"Content-Type": "text/plain"},
    )
    assert status == 400
    assert payload["error"] == "unsupported_content_type"


def test_missing_file_field_rejected(web_server):
    base, _ = web_server
    status, _, payload = _post_multipart(
        base,
        "",
        b"hello",
        field_name="note",
        extra_fields={"note": "text only"},
    )
    assert status == 400
    assert payload["error"] == "no_file_part"


def test_wrong_extension_rejected(web_server):
    base, _ = web_server
    status, _, payload = _post_multipart(base, "notes.txt", b"PK\x03\x04 data")
    assert status == 400
    assert payload["error"] == "unsupported_file_type"


def test_non_zip_bytes_with_pptx_name_rejected(web_server):
    base, _ = web_server
    status, _, payload = _post_multipart(
        base, "deck.pptx", b"plain text that is definitely not a zip archive"
    )
    assert status == 400
    assert payload["error"] == "upload_rejected"
    assert "zip" in payload["detail"].lower()


def test_empty_upload_rejected(web_server):
    base, _ = web_server
    status, _, payload = _post_multipart(base, "empty.pptx", b"")
    assert status == 400
    assert payload["error"] == "empty_upload"


def test_zip_slip_member_rejected_and_never_extracted(web_server, tmp_path):
    base, _ = web_server
    entries = dict(_decks.MINIMAL_OFFICE_PARTS)
    entries["../evil.txt"] = b"injected"
    path = _decks.write_raw_zip(tmp_path / "slip.pptx", entries)
    status, _, payload = upload_deck(base, path)
    assert status == 400
    assert "unsafe archive member" in payload["detail"]
    assert not (tmp_path / "evil.txt").exists()


def test_duplicate_member_rejected(web_server, tmp_path):
    base, _ = web_server
    path = tmp_path / "dup.pptx"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, data in _decks.MINIMAL_OFFICE_PARTS.items():
                zf.writestr(name, data)
            zf.writestr("ppt/slides/slide1.xml", b"<second copy/>")
    status, _, payload = upload_deck(base, path)
    assert status == 400
    assert "duplicate archive member" in payload["detail"].lower()


def test_missing_required_parts_rejected(web_server, tmp_path):
    base, _ = web_server
    path = _decks.write_raw_zip(tmp_path / "naked.pptx", {"ppt/random.xml": b"<x/>"})
    status, _, payload = upload_deck(base, path)
    assert status == 400
    detail = payload["detail"].lower()
    assert "missing required part" in detail or "main part" in detail


def test_oversize_upload_returns_413(web_server, tmp_path):
    base, httpd = web_server
    path = _decks.save_clean_deck(tmp_path / "clean.pptx")
    original = httpd.app.max_upload_bytes
    httpd.app.max_upload_bytes = 64  # tiny ceiling; the clean deck exceeds it
    try:
        status, _, payload = upload_deck(base, path)
        assert status == 413
        assert payload["error"] == "upload_rejected"
    finally:
        httpd.app.max_upload_bytes = original


def test_client_filename_traversal_is_display_only(web_server, tmp_path):
    base, httpd = web_server
    path = _decks.save_clean_deck(tmp_path / "clean.pptx")
    body, headers = build_multipart("../../data/evil.pptx", path.read_bytes())
    status, _, payload = request_json(base, "POST", "/api/upload", body=body, headers=headers)
    assert status == 201
    assert payload["file_name"] == "evil.pptx"
    session = httpd.app.store.get(payload["session_id"])
    assert session.source_path.parent.name == payload["session_id"]
    assert not (tmp_path / "data").exists()
