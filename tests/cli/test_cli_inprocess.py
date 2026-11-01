"""In-process CLI tests: call ``layoutproof.cli.main(argv)`` directly so the
coverage tool actually sees cli.py (subprocess runs are invisible to the
parent process' coverage)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pptx import Presentation
from pptx.util import Inches, Pt

from layoutproof.cli import main


def _clean_deck(path: Path) -> None:
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(1))
    box.text_frame.text = "A perfectly clean, readable deck."
    box.text_frame.paragraphs[0].runs[0].font.size = Pt(18)
    prs.save(str(path))


def _broken_deck(path: Path) -> None:
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    tiny = slide.shapes.add_textbox(Inches(0.6), Inches(0.5), Inches(4.0), Inches(0.8))
    tiny.text_frame.text = "小字号正文故意用8pt字体难以阅读。"
    tiny.text_frame.paragraphs[0].runs[0].font.size = Pt(8)
    off = slide.shapes.add_textbox(Inches(11.5), Inches(0.5), Inches(2.5), Inches(0.8))
    off.text_frame.text = "完全滑出画布的越界内容。"
    off.text_frame.paragraphs[0].runs[0].font.size = Pt(18)
    prs.save(str(path))


# ---------------------------------------------------------------------------
# scan
# ---------------------------------------------------------------------------
def test_scan_clean_deck_returns_zero(tmp_path, capsys):
    src = tmp_path / "clean.pptx"
    _clean_deck(src)
    code = main(["scan", str(src)])
    assert code == 0
    assert "No issues" in capsys.readouterr().out


def test_scan_broken_deck_returns_one(tmp_path, capsys):
    src = tmp_path / "broken.pptx"
    _broken_deck(src)
    code = main(["scan", str(src)])
    assert code == 1


def test_scan_json_to_stdout(tmp_path, capsys):
    src = tmp_path / "broken.pptx"
    _broken_deck(src)
    code = main(["scan", str(src), "--json"])
    assert code == 1
    data = json.loads(capsys.readouterr().out)
    assert data["summary"]["total"] >= 1
    assert "font_too_small" in {i["rule_id"] for i in data["issues"]}


def test_scan_json_to_output_file(tmp_path, capsys):
    src = tmp_path / "broken.pptx"
    _broken_deck(src)
    out_file = tmp_path / "report.json"
    code = main(["scan", str(src), "--json", "--output", str(out_file)])
    assert code == 1
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["summary"]["total"] >= 1


def test_scan_text_mode_to_output_file(tmp_path, capsys):
    src = tmp_path / "broken.pptx"
    _broken_deck(src)
    out_file = tmp_path / "report.txt"
    code = main(["scan", str(src), "-o", str(out_file)])
    assert code == 1
    assert "font_too_small" in out_file.read_text(encoding="utf-8")


def test_scan_directory_non_recursive(tmp_path, capsys):
    _broken_deck(tmp_path / "top.pptx")
    sub = tmp_path / "sub"
    sub.mkdir()
    _broken_deck(sub / "inner.pptx")
    code = main(["scan", str(tmp_path)])
    assert code == 1
    out = capsys.readouterr().out
    assert "top.pptx" in out
    assert "inner.pptx" not in out  # non-recursive misses the subdir


def test_scan_directory_recursive(tmp_path, capsys):
    _broken_deck(tmp_path / "top.pptx")
    sub = tmp_path / "sub"
    sub.mkdir()
    _broken_deck(sub / "inner.pptx")
    code = main(["scan", str(tmp_path), "--recursive"])
    assert code == 1
    out = capsys.readouterr().out
    assert "inner.pptx" in out


def test_scan_missing_target_returns_usage(tmp_path, capsys):
    code = main(["scan", str(tmp_path / "does-not-exist.pptx")])
    assert code == 2
    assert "No .pptx" in capsys.readouterr().err


def test_bare_path_defaults_to_scan(tmp_path, capsys):
    src = tmp_path / "clean.pptx"
    _clean_deck(src)
    code = main([str(src)])
    assert code == 0


def test_no_args_prints_help_and_returns_usage(tmp_path, capsys):
    code = main([])
    assert code == 2


def test_scan_profile_full(tmp_path, capsys):
    src = tmp_path / "clean.pptx"
    _clean_deck(src)
    code = main(["scan", str(src), "--profile", "full"])
    assert code == 0


def test_scan_fail_on_error_still_flags_errors(tmp_path, capsys):
    src = tmp_path / "broken.pptx"
    _broken_deck(src)
    code = main(["scan", str(src), "--fail-on", "error"])
    assert code == 1


# ---------------------------------------------------------------------------
# version / help (argparse raises SystemExit)
# ---------------------------------------------------------------------------
def test_version_exits_zero():
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0


def test_help_exits_zero():
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0


# ---------------------------------------------------------------------------
# fix / demo subcommands in-process
# ---------------------------------------------------------------------------
def test_fix_subcommand_inprocess(tmp_path, capsys):
    src = tmp_path / "broken.pptx"
    _broken_deck(src)
    code = main(["fix", str(src), "--json"])
    assert code == 0
    data = json.loads(capsys.readouterr().out)
    assert data["success"] is True
    assert data["after"]["total"] < data["before"]["total"]
    assert (tmp_path / "broken.fixed.pptx").exists()


def test_fix_subcommand_text_mode(tmp_path, capsys):
    src = tmp_path / "broken.pptx"
    _broken_deck(src)
    code = main(["fix", str(src)])
    assert code == 0
    out = capsys.readouterr().out
    assert "Output:" in out


def test_demo_subcommand_inprocess(tmp_path, capsys):
    demo_dir = tmp_path / "demo"
    code = main(["demo", "--dir", str(demo_dir)])
    assert code == 0
    assert (demo_dir / "broken.pptx").exists()
    assert (demo_dir / "fixed.pptx").exists()


def test_demo_subcommand_json(tmp_path, capsys):
    demo_dir = tmp_path / "demoj"
    code = main(["demo", "--dir", str(demo_dir), "--json"])
    assert code == 0
    data = json.loads(capsys.readouterr().out)
    assert data["fix_report"]["success"] is True


def test_scan_corrupt_file_reports_error_usage(tmp_path, capsys):
    bad = tmp_path / "broken_zip.pptx"
    bad.write_bytes(b"this is not a real pptx package")
    code = main(["scan", str(bad)])
    # scan_file returns status="error" -> exit_code_for -> EXIT_USAGE (2)
    assert code == 2
    assert "Failed to scan" in capsys.readouterr().out
