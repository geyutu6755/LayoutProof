"""HTML report output-safety contract.

Deck-supplied text (file name, shape name, issue detail, scan error message)
is attacker-influenced free text. The visible markup must be HTML-escaped and
the embedded ``<script type="application/json">`` data block must not allow a
``</script>`` breakout. A regression that returns raw script/handler markup
fails this file.
"""

from __future__ import annotations

import json
import re

import pytest
from pptx.util import Inches

import helpers_decks as decks
from layoutproof.engine import scan_file
from layoutproof.models import Issue, Location, ScanResult
from layoutproof.report import render_html

SCRIPT_BREAKOUT = "</script><script>alert('xss')</script>"
IMG_HANDLER = '"><img src=x onerror=alert(2)><"'


def _direct_result() -> ScanResult:
    return ScanResult(
        file_path="/deck/" + SCRIPT_BREAKOUT,
        file_name=SCRIPT_BREAKOUT,
        slide_count=1, slide_width=9144000, slide_height=6858000,
        timestamp="2026-01-01T00:00:00Z", status="error",
        error="<script>alert(1)</script>",
        issues=[Issue(
            rule_id="offslide_object", slide_index=0, slide_number=1,
            shape_id="1", shape_name=SCRIPT_BREAKOUT,
            location=Location(-100000, -50000, 2_000_000, 1_000_000),
            detail=IMG_HANDLER + SCRIPT_BREAKOUT,
            evidence={},
        )],
    )


def _extract_issues_json(html: str) -> dict:
    match = re.search(
        r'<script id="issues-data" type="application/json">(.*?)</script>',
        html, re.S | re.I,
    )
    assert match, "issues data block missing from report"
    block = match.group(1)
    assert "</script" not in block.lower(), "data block contains a script breakout"
    return json.loads(block)


def test_visible_markup_is_escaped_and_json_block_cannot_break_out(tmp_path):
    out = tmp_path / "hostile.html"
    render_html(_direct_result(), out, lang="en")
    html = out.read_text(encoding="utf-8")

    # 1) No executable payload reaches the markup: no live script tag carrying
    #    the payload, no injected event handler on an actual tag.
    assert not re.search(r"<script\b[^>]*alert", html, re.I)
    assert not re.search(r"<img\b[^>]*onerror", html, re.I)

    # 2) Visible/decorative contexts use escaped markup rather than raw tags.
    assert "&lt;script" in html
    assert "&lt;img" in html
    assert "&#34;" in html  # quote characters neutralised by Jinja autoescape

    # 3) The data block still parses as JSON and preserves the original data
    #    (unicode escapes used for the data block decode back to the text).
    issues = _extract_issues_json(html)
    assert len(issues) == 1
    assert "alert('xss')" in issues[0]["shape_name"]
    assert "onerror=alert(2)" in issues[0]["detail"]

    # 4) Scan error message is escaped in the alert banner.
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)" in html


def test_real_scanned_deck_with_hostile_shape_name_renders_safely(tmp_path):
    path = tmp_path / "hostile.pptx"
    prs = decks.blank_prs()
    slide = decks.add_blank_slide(prs)
    decks.add_textbox(slide, Inches(1), Inches(1), Inches(6), Inches(1),
                      "normal body", font_pt=18, name=SCRIPT_BREAKOUT)
    prs.save(str(path))

    result = scan_file(path, profile="full")
    out = tmp_path / "pipeline.html"
    render_html(result, out, lang="zh")
    html = out.read_text(encoding="utf-8")
    assert not re.search(r"<script\b[^>]*alert", html, re.I)
    _extract_issues_json(html)


def test_unsupported_language_rejected(tmp_path):
    with pytest.raises(ValueError, match="lang"):
        render_html(_direct_result(), tmp_path / "bad.html", lang="fr")


def test_static_assets_are_the_only_safe_marked_blocks(tmp_path):
    """Sanity: exactly two legitimate script elements (data + app logic);
    user content never adds a third executable element."""
    out = tmp_path / "clean.html"
    result = _direct_result()
    result.status = "ok"
    result.error = None
    render_html(result, out, lang="en")
    html = out.read_text(encoding="utf-8")
    opens = len(re.findall(r"<script\b", html, re.I))
    closes = len(re.findall(r"</script\s*>", html, re.I))
    assert opens == 2 and closes == 2
