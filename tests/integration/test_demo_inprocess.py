"""In-process coverage for layoutproof.demo.run_demo."""

from __future__ import annotations

import json
from pathlib import Path

from layoutproof.demo import run_demo


def test_run_demo_text_mode(tmp_path, capsys):
    d = tmp_path / "demo"
    code = run_demo(d)
    assert code == 0
    assert (d / "broken.pptx").exists()
    assert (d / "fixed.pptx").exists()
    out = capsys.readouterr().out
    assert "LayoutProof" in out
    assert "Before:" in out


def test_run_demo_json_mode(tmp_path, capsys):
    d = tmp_path / "demoj"
    code = run_demo(d, json_out=True)
    assert code == 0
    data = json.loads(capsys.readouterr().out)
    assert data["broken"].endswith("broken.pptx")
    assert data["fixed"].endswith("fixed.pptx")
    assert data["fix_report"]["success"] is True
    assert data["fix_report"]["after"]["total"] < data["fix_report"]["before"]["total"]


def test_run_demo_build_failure(tmp_path, monkeypatch, capsys):
    from layoutproof import demo

    def _boom(path: Path) -> None:
        raise RuntimeError("synthetic build failure")

    monkeypatch.setattr(demo, "_build_broken", _boom)
    code = run_demo(tmp_path / "will-fail")
    assert code == 3  # EXIT_INTERNAL
    assert "failed to build" in capsys.readouterr().err
