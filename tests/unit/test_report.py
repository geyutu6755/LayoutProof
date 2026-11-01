"""Tests for the HTML/JSON report layer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from layoutproof.models import (
    AppliedFix,
    FixReport,
    Issue,
    Location,
    ScanResult,
)
from layoutproof.report import render_html, validate_output, write_json


def _make_result() -> ScanResult:
    return ScanResult(
        file_path="/deck/demo.pptx",
        file_name="demo.pptx",
        slide_count=3,
        slide_width=9144000,
        slide_height=6858000,
        timestamp="2026-11-02T10:00:00Z",
        config={"min_font_pt": 12.0},
        issues=[
            Issue(
                rule_id="offslide_object",
                slide_index=0,
                slide_number=1,
                shape_id="2",
                shape_name="TextBox 3",
                location=Location(x=9000000, y=100000, width=500000, height=400000),
                detail="shape extends 356 EMU past right edge",
                confidence=1.0,
                evidence={"overflow_emu": 356},
            ),
            Issue(
                rule_id="text_overflow",
                slide_index=1,
                slide_number=2,
                shape_id="5",
                shape_name="Title 1",
                location=Location(x=500000, y=500000, width=4000000, height=800000),
                detail="text box 4000000 EMU wide, content needs 4380000",
                confidence=0.8,
                evidence={"needed": 4380000},
            ),
            Issue(
                rule_id="missing_alt_text",
                slide_index=0,
                slide_number=1,
                shape_id="7",
                shape_name="Picture 2",
                location=None,
                detail="picture has no descr",
                confidence=1.0,
                evidence={},
            ),
            Issue(
                rule_id="object_overlap",
                slide_index=-1,
                slide_number=0,
                shape_id=None,
                shape_name=None,
                location=None,
                detail="document-level heuristic",
                confidence=0.6,
                evidence={},
            ),
        ],
    )


def _make_fix(result: ScanResult) -> FixReport:
    before = result.summarize().to_dict()
    after = {"error": 0, "warning": 1, "info": 1, "total": 2}
    return FixReport(
        source_path="/deck/demo.pptx",
        output_path="/deck/demo.fixed.pptx",
        backup_path="/deck/demo.pptx.bak",
        created=True,
        success=True,
        applied=[
            AppliedFix(
                rule_id="offslide_object",
                shape_id="2",
                action="moved into slide bounds",
                status="applied",
                note="clamped to right edge",
            ),
        ],
        skipped=[
            AppliedFix(
                rule_id="object_overlap",
                shape_id=None,
                action="needs manual review",
                status="skipped",
                note="no safe auto-fix",
            ),
        ],
        before_summary=before,
        after_summary=after,
        note="demo fix run",
    )


# --------------------------------------------------------------------------- #
# HTML rendering
# --------------------------------------------------------------------------- #
def test_render_en_contains_rule_titles_and_filters(tmp_path: Path) -> None:
    result = _make_result()
    out = tmp_path / "report_en.html"
    render_html(result, out, lang="en")

    html = out.read_text(encoding="utf-8")
    # file exists and is non-trivial
    assert out.stat().st_size > 1000

    # bilingual rule titles present
    assert "Object outside slide bounds" in html
    assert "Suspected text overflow or clipping" in html
    # Chinese title present (hidden via CSS but shipped for toggle)
    assert "对象位于页面边界之外" in html

    # filter controls
    assert 'id="filter-file"' in html
    assert 'id="filter-slide"' in html
    assert 'data-sev="error"' in html
    assert 'data-sev="warning"' in html
    assert 'data-sev="info"' in html

    # location preview + locate button
    assert 'id="stage"' in html
    assert 'data-locate="0"' in html

    # no un-rendered Jinja residue
    assert "{{" not in html
    assert "}}" not in html
    assert "{%" not in html
    assert "{%" not in html

    # embedded issues JSON carries normalized_location
    assert '"normalized_location"' in html


def test_render_zh_initial_language(tmp_path: Path) -> None:
    result = _make_result()
    out = tmp_path / "report_zh.html"
    render_html(result, out, lang="zh")
    html = out.read_text(encoding="utf-8")

    # body starts in zh mode; both language strings shipped for the toggle
    assert '<body class="lang-zh">' in html
    assert "对象位于页面边界之外" in html
    assert "Object outside slide bounds" in html
    # no template residue
    assert "{{" not in html and "{%" not in html


def test_render_with_fix_report(tmp_path: Path) -> None:
    result = _make_result()
    fix = _make_fix(result)
    out = tmp_path / "report_fix.html"
    render_html(result, out, lang="en", fix_report=fix)
    html = out.read_text(encoding="utf-8")

    assert "Auto-fix result" in html
    assert "Before" in html and "After" in html
    assert "moved into slide bounds" in html
    assert "needs manual review" in html


# --------------------------------------------------------------------------- #
# JSON schema
# --------------------------------------------------------------------------- #
def test_scan_result_dict_passes_schema() -> None:
    result = _make_result()
    data = result.to_dict()
    assert validate_output(data) == "ScanResult"
    # normalized_location populated because slide dims are set
    offslide = data["issues"][0]
    assert offslide["normalized_location"] is not None
    assert 0.0 <= offslide["normalized_location"]["x"] <= 1.0


def test_fix_report_dict_passes_schema() -> None:
    result = _make_result()
    fix = _make_fix(result)
    data = fix.to_dict()
    assert validate_output(data) == "FixReport"
    assert data["issues_removed"] >= 0


def test_write_json_roundtrip(tmp_path: Path) -> None:
    result = _make_result()
    path = write_json(result, tmp_path / "out.json")
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk["file"]["name"] == "demo.pptx"
    assert on_disk["summary"]["error"] >= 1
    assert validate_output(on_disk) == "ScanResult"


def test_invalid_dict_rejected() -> None:
    with pytest.raises(Exception):
        validate_output({"not": "a report"})
