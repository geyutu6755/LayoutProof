"""CLI tests: drive the installed ``layoutproof`` entry point via subprocess."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from pptx import Presentation
from pptx.util import Inches, Pt

REPO_ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable
MODULE = [PY, "-m", "layoutproof"]


def _run(*argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [*MODULE, *argv],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=120,
    )


def _make_broken(path: Path) -> None:
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    tiny = slide.shapes.add_textbox(Inches(0.6), Inches(0.5), Inches(4.0), Inches(0.8))
    tiny.text_frame.word_wrap = True
    r = tiny.text_frame.paragraphs[0].add_run()
    r.text = "小字号正文：这段文字故意用了 8pt。"
    r.font.size = Pt(8)

    ov = slide.shapes.add_textbox(Inches(0.6), Inches(1.7), Inches(4.5), Inches(0.5))
    ov.text_frame.word_wrap = True
    r = ov.text_frame.paragraphs[0].add_run()
    r.text = "LayoutProof 检测演示：这是一段故意写得很长的中文混排正文，用来触发文字溢出问题。"
    r.font.size = Pt(18)

    off = slide.shapes.add_textbox(Inches(11.5), Inches(0.5), Inches(2.5), Inches(0.8))
    r = off.text_frame.paragraphs[0].add_run()
    r.text = "越界备注。"
    r.font.size = Pt(18)

    ph = slide.shapes.add_textbox(Inches(0.6), Inches(4.2), Inches(4.0), Inches(0.8))
    r = ph.text_frame.paragraphs[0].add_run()
    r.text = "点击添加标题（TODO 待补充）"
    r.font.size = Pt(18)

    prs.save(str(path))


def test_cli_scan_reports_issues(tmp_path):
    src = tmp_path / "deck.pptx"
    _make_broken(src)
    p = _run("scan", str(src), "--json")
    # Errors present -> exit code 1 (EXIT_ISSUES).
    assert p.returncode == 1, p.stderr
    data = json.loads(p.stdout)
    assert data["summary"]["total"] > 0
    rule_ids = {i["rule_id"] for i in data["issues"]}
    assert "font_too_small" in rule_ids
    assert "offslide_object" in rule_ids


def test_cli_fix_produces_clean_output(tmp_path):
    src = tmp_path / "deck.pptx"
    _make_broken(src)
    out = tmp_path / "deck.fixed.pptx"

    p = _run("fix", str(src), "--output", str(out), "--json")
    assert p.returncode == 0, p.stderr + p.stdout
    report = json.loads(p.stdout)
    assert out.exists()
    assert report["success"] is True
    assert report["applied"], "expected applied fixes"
    assert report["after"]["total"] < report["before"]["total"]
    # Source untouched on disk.
    assert (tmp_path / "deck.bak.pptx").exists()


def test_cli_demo_generates_broken_and_fixed(tmp_path):
    demo_dir = tmp_path / "demo"
    p = _run("demo", "--dir", str(demo_dir))
    assert p.returncode == 0, p.stderr + p.stdout
    assert (demo_dir / "broken.pptx").exists()
    assert (demo_dir / "fixed.pptx").exists()


def test_cli_scan_json_idempotent(tmp_path):
    src = tmp_path / "idem.pptx"
    _make_broken(src)
    p1 = _run("scan", str(src), "--json")
    p2 = _run("scan", str(src), "--json")
    assert p1.returncode == p2.returncode
    d1 = json.loads(p1.stdout)
    d2 = json.loads(p2.stdout)
    d1.pop("timestamp")
    d2.pop("timestamp")
    assert d1 == d2
