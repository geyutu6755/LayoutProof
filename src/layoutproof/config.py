"""Configurable quality rules and safe loading defaults."""

from __future__ import annotations

import json
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Default placeholder prompt text shipped by PowerPoint plus common AI leftovers.
DEFAULT_PLACEHOLDER_PATTERNS = [
    "click to add title",
    "click to add subtitle",
    "click to add text",
    "click to add content",
    "click to add notes",
    "click to add header",
    "click to add footer",
    "click to add picture",
    "click to add media",
    "click icon to add",
    "title placeholder",
    "subtitle placeholder",
    "lorem ipsum",
    "todo",
    "tbd",
    "fixme",
    "placeholder",
    "待补充",
    "待完善",
    "占位",
    "此处输入",
    "点击添加标题",
    "点击添加副标题",
    "点击添加文本",
    "点击添加内容",
]

# Shape names / keywords that strongly indicate a deliberately decorative element.
DECORATIVE_NAME_HINTS = [
    "background",
    "decor",
    "decoration",
    "ornament",
    "accent",
    "divider",
    "bg",
    "背景",
    "装饰",
    "底纹",
]


@dataclass
class QualityConfig:
    # Readability
    min_font_size_pt: float = 12.0
    min_contrast_ratio: float = 4.5
    large_text_pt: float = 18.0
    large_text_contrast_ratio: float = 3.0

    # Geometry / layout
    overlap_ratio_threshold: float = 0.30
    offslide_fraction_threshold: float = 0.05
    overflow_ratio_threshold: float = 0.15

    # Security
    max_file_size_mb: int = 100

    # Quality gate
    fail_on: str = "warning"  # "error" | "warning" | "info"

    # Enabled rule ids (empty list means all enabled)
    enabled_rules: list[str] = field(default_factory=list)
    disabled_rules: list[str] = field(default_factory=list)

    placeholder_patterns: list[str] = field(
        default_factory=lambda: list(DEFAULT_PLACEHOLDER_PATTERNS)
    )
    decorative_name_hints: list[str] = field(default_factory=lambda: list(DECORATIVE_NAME_HINTS))

    def is_rule_enabled(self, rule_id: str) -> bool:
        if rule_id in self.disabled_rules:
            return False
        if self.enabled_rules:
            return rule_id in self.enabled_rules
        return True

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> QualityConfig:
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)

    @classmethod
    def load(cls, path: str | Path) -> QualityConfig:
        p = Path(path)
        raw = p.read_bytes()
        if p.suffix.lower() == ".toml":
            data = tomllib.loads(raw.decode("utf-8"))
        else:
            data = json.loads(raw.decode("utf-8"))
        # Allow a top-level [tool.layoutproof] style table.
        if "tool" in data and "layoutproof" in data.get("tool", {}):
            data = data["tool"]["layoutproof"]
        return cls.from_dict(data)
