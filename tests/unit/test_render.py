"""Unit tests for the render module: deterministic helpers and fallback."""

from __future__ import annotations

import base64

from layoutproof.models import Issue, Location, RuleId, ScanResult
from layoutproof.render import backend, engine
from layoutproof.render.backend import (
    RendererInfo,
    _decode,
)


def test_decode_utf8_and_non_utf8():
    assert _decode(b"hello") == "hello"
    assert _decode(b"") == ""
    # Invalid UTF-8 must be replaced, never raise (the GBK/console bug).
    decoded = _decode(b"prefix\xb2suffix")
    assert "prefix" in decoded and "suffix" in decoded


def test_decode_uses_system_codepath_for_valid_gbk():
    # 0xb2 0xe2 is a valid GBK sequence (簿). Strict UTF-8 would fail.
    out = _decode(b"\xb2\xe2")
    assert isinstance(out, str)


def test_console_wrapper_preferred_for_windows_exe(tmp_path, monkeypatch):
    # The GUI soffice.exe hangs on --version; the sibling .com must win.
    program = tmp_path / "program"
    program.mkdir()
    exe = program / "soffice.exe"
    com = program / "soffice.com"
    exe.write_text("gui", encoding="utf-8")
    com.write_text("console", encoding="utf-8")
    monkeypatch.setattr(backend.os, "name", "nt")

    ordered = backend._prefer_console_wrapper([str(exe)])
    assert ordered[0] == str(com)
    assert str(exe) in ordered


def test_console_wrapper_keeps_exe_when_com_absent(tmp_path, monkeypatch):
    program = tmp_path / "program"
    program.mkdir()
    exe = program / "soffice.exe"
    exe.write_text("gui", encoding="utf-8")
    monkeypatch.setattr(backend.os, "name", "nt")

    ordered = backend._prefer_console_wrapper([str(exe)])
    assert ordered == [str(exe)]


def test_console_wrapper_noop_on_non_windows(tmp_path, monkeypatch):
    monkeypatch.setattr(backend.os, "name", "posix")
    candidates = [str(tmp_path / "soffice.exe")]
    assert backend._prefer_console_wrapper(candidates) == candidates


def test_pinned_exe_resolves_to_sibling_com(tmp_path, monkeypatch):
    program = tmp_path / "rendertools" / "lo" / "program"
    program.mkdir(parents=True)
    exe = program / "soffice.exe"
    com = program / "soffice.com"
    exe.write_text("gui", encoding="utf-8")
    com.write_text("console", encoding="utf-8")
    monkeypatch.setattr(backend.os, "name", "nt")
    monkeypatch.setenv("LAYOUTPROOF_SOFFICE", str(exe))
    monkeypatch.setattr(backend.shutil, "which", lambda _name: None)

    candidates = backend._candidate_paths()
    assert candidates[0] == str(com)


def test_image_data_uri_embeds_png(tmp_path):
    png = tmp_path / "x.png"
    payload = b"\x89PNG\r\n\x1a\nfake"
    png.write_bytes(payload)
    from layoutproof.report.html import _image_data_uri

    uri = _image_data_uri(png)
    assert uri.startswith("data:image/png;base64,")
    assert base64.b64decode(uri.split(",", 1)[1]) == payload


def _make_scan(tmp_path):
    result = ScanResult(
        file_path=str(tmp_path / "d.pptx"),
        file_name="d.pptx",
        slide_count=1,
        slide_width=9144000,
        slide_height=6858000,
    )
    issue = Issue(
        rule_id=RuleId.OFFSLIDE_OBJECT,
        slide_index=0,
        slide_number=1,
        shape_id="4",
        shape_name="Box",
        location=Location(9525000, 1000000, 1000000, 800000),
    )
    result.issues.append(issue)
    return result


def test_markers_for_slide_normalized(tmp_path):
    from layoutproof.report.html import _markers_for_slide

    result = _make_scan(tmp_path)
    markers = _markers_for_slide(result, 1)
    assert len(markers) == 1
    loc = markers[0]["location"]
    assert loc["x"] > 1.0  # off-slide, normalized beyond canvas
    assert markers[0]["rule_id"] == "offslide_object"
    assert _markers_for_slide(result, 2) == []


def test_fallback_when_no_renderer(tmp_path, monkeypatch):
    monkeypatch.delenv("LAYOUTPROOF_SOFFICE", raising=False)
    monkeypatch.setattr(
        engine,
        "detect_renderer",
        lambda: RendererInfo(available=False, reason="blocked", searched=[]),
    )
    source = tmp_path / "s.pptx"
    source.write_bytes(b"x")
    work = tmp_path / "work"
    result = engine.render_presentation(source, work)
    assert result.status == engine.RENDER_STATUS_STATIC
    assert result.reason == "blocked"
    assert result.rendered is False
    manifest = work / "render-manifest.json"
    assert manifest.exists()


def test_fallback_when_pymupdf_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(
        engine,
        "detect_renderer",
        lambda: RendererInfo(available=True, executable="soffice", version="x"),
    )
    monkeypatch.setattr(engine.images_mod, "is_available", lambda: False)
    source = tmp_path / "s.pptx"
    source.write_bytes(b"x")
    result = engine.render_presentation(source, tmp_path / "work")
    assert result.status == engine.RENDER_STATUS_STATIC
    assert "PyMuPDF" in result.reason


def test_fallback_when_conversion_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(
        engine,
        "detect_renderer",
        lambda: RendererInfo(available=True, executable="soffice", version="x"),
    )
    monkeypatch.setattr(engine.images_mod, "is_available", lambda: True)

    def boom(*a, **k):
        raise RuntimeError("soffice crashed")

    monkeypatch.setattr(engine, "convert_to_pdf", boom)
    source = tmp_path / "s.pptx"
    source.write_bytes(b"x")
    result = engine.render_presentation(source, tmp_path / "work")
    assert result.status == engine.RENDER_STATUS_STATIC
    assert "soffice crashed" in result.reason
