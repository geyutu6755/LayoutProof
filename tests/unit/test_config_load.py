"""Coverage for QualityConfig.load / from_dict filtering."""

from __future__ import annotations

import json
from pathlib import Path

from layoutproof.config import QualityConfig


def test_load_json_config(tmp_path: Path):
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps({"min_font_size_pt": 14.0, "fail_on": "error"}),
                 encoding="utf-8")
    cfg = QualityConfig.load(p)
    assert cfg.min_font_size_pt == 14.0
    assert cfg.fail_on == "error"


def test_load_json_with_tool_layoutproof_nesting(tmp_path: Path):
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps({"tool": {"layoutproof": {"min_font_size_pt": 11.0}}}),
                 encoding="utf-8")
    cfg = QualityConfig.load(p)
    assert cfg.min_font_size_pt == 11.0


def test_load_toml_config(tmp_path: Path):
    p = tmp_path / "cfg.toml"
    p.write_text('min_font_size_pt = 13.0\nenabled_rules = ["offslide_object"]\n',
                 encoding="utf-8")
    cfg = QualityConfig.load(p)
    assert cfg.min_font_size_pt == 13.0
    assert cfg.enabled_rules == ["offslide_object"]


def test_from_dict_ignores_unknown_keys():
    cfg = QualityConfig.from_dict({"min_font_size_pt": 10.0, "bogus_key": 123})
    assert cfg.min_font_size_pt == 10.0
    assert not hasattr(cfg, "bogus_key")
