"""Frozen data contracts for LayoutProof.

This module is the single source of truth for the stable JSON schema, rule
identifiers, severity levels and the bilingual rule catalogue. Detection,
fix, report and CLI layers all depend on these structures and must not invent
parallel rule identifiers.
"""

from __future__ import annotations

import dataclasses
import enum
from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = "1.0"
TOOL_NAME = "layoutproof"
TOOL_VERSION = "0.1.0a1"


class Severity(str, enum.Enum):
    """Three-tier classification required by the product spec."""

    ERROR = "error"  # deterministic error / 确定性错误
    WARNING = "warning"  # heuristic warning / 启发式警告
    INFO = "info"  # informational hint / 信息提示


# ---------------------------------------------------------------------------
# Stable rule identifiers
# ---------------------------------------------------------------------------
class RuleId(str, enum.Enum):
    OFFSLIDE_OBJECT = "offslide_object"
    TEXT_OVERFLOW = "text_overflow"
    OBJECT_OVERLAP = "object_overlap"
    FONT_TOO_SMALL = "font_too_small"
    LOW_CONTRAST = "low_contrast"
    BLANK_SLIDE = "blank_slide"
    UNFINISHED_PLACEHOLDER = "unfinished_placeholder"
    MEDIA_BROKEN = "media_broken"
    BROKEN_REFERENCE = "broken_reference"
    STRUCTURE_ANOMALY = "structure_anomaly"
    MISSING_ALT_TEXT = "missing_alt_text"
    CJK_TYPOGRAPHY = "cjk_typography"


@dataclass(frozen=True)
class RuleSpec:
    rule_id: RuleId
    severity: Severity
    fix_id: str | None
    title_en: str
    title_zh: str
    explanation_en: str
    explanation_zh: str
    recommendation_en: str
    recommendation_zh: str

    @property
    def fixable(self) -> bool:
        return self.fix_id is not None


RULES: dict[str, RuleSpec] = {
    RuleId.OFFSLIDE_OBJECT.value: RuleSpec(
        RuleId.OFFSLIDE_OBJECT,
        Severity.ERROR,
        "move_into_slide",
        "Object outside slide bounds",
        "对象位于页面边界之外",
        "A shape or media element is placed fully or partially outside the slide "
        "canvas and will not render in the exported deck.",
        "形状或媒体元素完全或部分位于幻灯片画布之外，导出后不会显示。",
        "Move the object fully inside the slide bounds, or delete it if it is unused.",
        "将对象移动到幻灯片边界内；若不再使用则删除。",
    ),
    RuleId.TEXT_OVERFLOW.value: RuleSpec(
        RuleId.TEXT_OVERFLOW,
        Severity.WARNING,
        "autofit_text",
        "Suspected text overflow or clipping",
        "疑似文字溢出或内容裁切",
        "The text content likely exceeds the shape or placeholder box, so "
        "PowerPoint may clip or auto-shrink it.",
        "文本内容可能超出形状或占位符框，PowerPoint 可能裁切或自动缩小文字。",
        "Enlarge the text box, reduce the text, or enable auto-fit/shrink text on overflow.",
        "放大文本框、精简文字，或启用溢出时自动缩排/缩小字体。",
    ),
    RuleId.OBJECT_OVERLAP.value: RuleSpec(
        RuleId.OBJECT_OVERLAP,
        Severity.WARNING,
        None,
        "Unexpected object overlap or collision",
        "非预期对象遮挡或碰撞",
        "Two non-decorative objects overlap enough to obscure content, which "
        "often indicates a layout collision.",
        "两个非装饰对象重叠到足以遮挡内容，通常意味着布局碰撞。",
        "Reposition or resize the objects so content is not obscured; group "
        "them deliberately if overlap is intended.",
        "重新摆放或调整对象大小，避免遮挡；若确需叠放请显式组合。",
    ),
    RuleId.FONT_TOO_SMALL.value: RuleSpec(
        RuleId.FONT_TOO_SMALL,
        Severity.ERROR,
        "increase_font_size",
        "Font too small to read",
        "字体过小，难以阅读",
        "The effective font size is below the readable threshold, especially on projected screens.",
        "实际字号低于可读阈值，在投影屏幕上尤其难以辨认。",
        "Increase the font size to at least the configured minimum, or split "
        "the content across slides.",
        "将字号提升到配置的最小值以上，或拆分内容到多张幻灯片。",
    ),
    RuleId.LOW_CONTRAST.value: RuleSpec(
        RuleId.LOW_CONTRAST,
        Severity.WARNING,
        "adjust_contrast",
        "Insufficient color contrast",
        "颜色对比度不足",
        "The text/background color combination has a contrast ratio below the "
        "readability threshold.",
        "文字与背景的颜色对比度低于可读阈值。",
        "Choose a darker or lighter foreground/background pair that meets the contrast threshold.",
        "调整前景或背景颜色，使对比度达到阈值要求。",
    ),
    RuleId.BLANK_SLIDE.value: RuleSpec(
        RuleId.BLANK_SLIDE,
        Severity.WARNING,
        None,
        "Blank or empty slide",
        "空白幻灯片",
        "The slide contains no visible content, placeholder text, or usable media.",
        "该幻灯片不包含任何可见内容、占位文本或可用媒体。",
        "Add content or remove the empty slide if it is unintentional.",
        "补充内容；若非有意保留则删除该空白页。",
    ),
    RuleId.UNFINISHED_PLACEHOLDER.value: RuleSpec(
        RuleId.UNFINISHED_PLACEHOLDER,
        Severity.WARNING,
        "clear_placeholder",
        "Unfinished placeholder or leftover content",
        "未完成的占位内容或残留文本",
        "Default placeholder prompts, TODO markers or Lorem ipsum text indicate "
        "the deck was left unfinished.",
        "默认占位提示、TODO 标记或 Lorem ipsum 等文本表明文档尚未完成。",
        "Replace the placeholder with real content or remove it.",
        "用真实内容替换占位符，或直接删除。",
    ),
    RuleId.MEDIA_BROKEN.value: RuleSpec(
        RuleId.MEDIA_BROKEN,
        Severity.ERROR,
        None,
        "Broken or missing media",
        "媒体资源损坏或缺失",
        "An image or media relationship points to a part that is missing, unreadable or corrupted.",
        "图片或媒体关系指向缺失、不可读或已损坏的部件。",
        "Re-embed the media or remove the broken reference.",
        "重新嵌入媒体，或删除损坏的引用。",
    ),
    RuleId.BROKEN_REFERENCE.value: RuleSpec(
        RuleId.BROKEN_REFERENCE,
        Severity.ERROR,
        None,
        "Broken internal reference",
        "失效的内部引用",
        "A hyperlink, slide jump or relationship target does not resolve to an "
        "existing part or slide.",
        "超链接、幻灯片跳转或关系目标无法解析到现有部件或幻灯片。",
        "Repair the link target or remove the invalid reference.",
        "修复链接目标，或删除无效引用。",
    ),
    RuleId.STRUCTURE_ANOMALY.value: RuleSpec(
        RuleId.STRUCTURE_ANOMALY,
        Severity.ERROR,
        None,
        "Package or structural anomaly",
        "压缩包或结构异常",
        "The OOXML package is malformed, contains unsafe entries, or is missing required parts.",
        "OOXML 压缩包格式错误、包含不安全条目或缺失必要部件。",
        "Re-save the file in PowerPoint or regenerate it from a healthy template.",
        "在 PowerPoint 中重新保存，或用健康模板重新生成。",
    ),
    RuleId.MISSING_ALT_TEXT.value: RuleSpec(
        RuleId.MISSING_ALT_TEXT,
        Severity.INFO,
        None,
        "Image missing alternative text",
        "图片缺少替代文字",
        "A meaningful image has no alternative text, which hurts screen-reader accessibility.",
        "有意义的图片缺少替代文字，影响屏幕阅读器的可访问性。",
        "Add concise descriptive alt text; mark purely decorative images as decorative.",
        "添加简洁的描述性替代文字；纯装饰图片标记为装饰性。",
    ),
    RuleId.CJK_TYPOGRAPHY.value: RuleSpec(
        RuleId.CJK_TYPOGRAPHY,
        Severity.WARNING,
        "normalize_cjk_text",
        "Simplified Chinese typography issue",
        "简体中文排版问题",
        "Common Chinese typesetting problems such as kinsoku (line starting or "
        "ending with a forbidden punctuation mark), improper spacing between "
        "Chinese and Latin/digit text, or mixed full-width/half-width punctuation.",
        "常见中文排版问题，例如避头尾（行首/行尾出现禁用标点）、中西文或中文字与数字之间间距不当、全角/半角标点混用。",
        "Normalize punctuation width, fix CJK-Latin spacing, and reflow so "
        "forbidden punctuation does not sit at a line break.",
        "规范标点宽度、修正中西文间距并重新排版，使禁用标点不落在换行处。",
    ),
}


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Location:
    """Bounding box in EMU. Coordinates follow the OOXML slide coordinate system."""

    x: int | None = None
    y: int | None = None
    width: int | None = None
    height: int | None = None

    def to_dict(self) -> dict[str, int]:
        return {
            "x": int(self.x or 0),
            "y": int(self.y or 0),
            "width": int(self.width or 0),
            "height": int(self.height or 0),
        }

    def normalized(self, slide_w: int, slide_h: int) -> dict[str, float]:
        def pct(value: int | None, base: int) -> float:
            if value is None or base == 0:
                return 0.0
            return round(value / base, 6)

        return {
            "x": pct(self.x, slide_w),
            "y": pct(self.y, slide_h),
            "width": pct(self.width, slide_w),
            "height": pct(self.height, slide_h),
        }


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------
@dataclass
class Issue:
    rule_id: str
    slide_index: int = -1  # 0-based; -1 for document-level
    slide_number: int = 0  # 1-based; 0 for document-level
    shape_id: str | None = None
    shape_name: str | None = None
    location: Location | None = None
    detail: str = ""  # short, language-neutral technical detail
    confidence: float = 1.0  # 1.0 for deterministic rules
    evidence: dict[str, Any] = field(default_factory=dict)

    @property
    def spec(self) -> RuleSpec:
        return RULES[self.rule_id]

    @property
    def severity(self) -> Severity:
        return self.spec.severity

    @property
    def fix_id(self) -> str | None:
        return self.spec.fix_id

    @property
    def fixable(self) -> bool:
        return self.spec.fixable

    def to_dict(self, slide_w: int = 0, slide_h: int = 0) -> dict[str, Any]:
        data: dict[str, Any] = {
            "rule_id": self.rule_id,
            "severity": self.severity.value,
            "slide_index": self.slide_index,
            "slide_number": self.slide_number,
            "shape_id": self.shape_id,
            "shape_name": self.shape_name,
            "location": self.location.to_dict() if self.location else None,
            "normalized_location": (
                self.location.normalized(slide_w, slide_h)
                if self.location and slide_w and slide_h
                else None
            ),
            "detail": self.detail,
            "confidence": round(self.confidence, 4),
            "fixable": self.fixable,
            "fix_id": self.fix_id,
            "evidence": self.evidence,
        }
        return data


# ---------------------------------------------------------------------------
# Scan result
# ---------------------------------------------------------------------------
@dataclass
class Summary:
    error: int = 0
    warning: int = 0
    info: int = 0

    @property
    def total(self) -> int:
        return self.error + self.warning + self.info

    def to_dict(self) -> dict[str, int]:
        return {
            "error": self.error,
            "warning": self.warning,
            "info": self.info,
            "total": self.total,
        }


@dataclass
class ScanResult:
    file_path: str
    file_name: str
    slide_count: int = 0
    slide_width: int = 0
    slide_height: int = 0
    issues: list[Issue] = field(default_factory=list)
    status: str = "ok"  # "ok" | "error"
    error: str | None = None
    timestamp: str = ""
    config: dict[str, Any] = field(default_factory=dict)

    def summarize(self) -> Summary:
        s = Summary()
        for issue in self.issues:
            if issue.severity == Severity.ERROR:
                s.error += 1
            elif issue.severity == Severity.WARNING:
                s.warning += 1
            else:
                s.info += 1
        return s

    def to_dict(self, slide_w: int | None = None, slide_h: int | None = None) -> dict[str, Any]:
        if slide_w is None:
            slide_w = self.slide_width
        if slide_h is None:
            slide_h = self.slide_height
        summary = self.summarize()
        return {
            "schema_version": SCHEMA_VERSION,
            "tool": {
                "name": TOOL_NAME,
                "version": TOOL_VERSION,
            },
            "file": {
                "path": self.file_path,
                "name": self.file_name,
            },
            "status": self.status,
            "error": self.error,
            "timestamp": self.timestamp,
            "slide_count": self.slide_count,
            "summary": summary.to_dict(),
            "issues": [i.to_dict(slide_w, slide_h) for i in self.issues],
            "config": self.config,
        }


# ---------------------------------------------------------------------------
# Fix result
# ---------------------------------------------------------------------------
@dataclass
class AppliedFix:
    rule_id: str
    shape_id: str | None
    action: str
    status: str = "applied"  # "applied" | "skipped"
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass
class FixReport:
    source_path: str
    output_path: str
    backup_path: str | None = None
    created: bool = False
    applied: list[AppliedFix] = field(default_factory=list)
    skipped: list[AppliedFix] = field(default_factory=list)
    before_summary: dict[str, int] = field(default_factory=dict)
    after_summary: dict[str, int] = field(default_factory=dict)
    success: bool = False
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "source_path": self.source_path,
            "output_path": self.output_path,
            "backup_path": self.backup_path,
            "created": self.created,
            "success": self.success,
            "applied": [a.to_dict() for a in self.applied],
            "skipped": [a.to_dict() for a in self.skipped],
            "before": self.before_summary,
            "after": self.after_summary,
            "issues_removed": max(
                0,
                self.before_summary.get("total", 0) - self.after_summary.get("total", 0),
            ),
            "note": self.note,
        }


# ---------------------------------------------------------------------------
# Exit codes
# ------------------------------------------------- Exit-code contract for AI agents / CI.
EXIT_CLEAN = 0  # no issues at or above the fail threshold
EXIT_ISSUES = 1  # quality gate failed
EXIT_USAGE = 2  # bad arguments / missing or invalid input
EXIT_INTERNAL = 3  # unexpected internal error


def exit_code_for(result: ScanResult, fail_on: Severity = Severity.WARNING) -> int:
    """Return the deterministic process exit code for a scan."""
    if result.status == "error":
        return EXIT_USAGE
    for issue in result.issues:
        if issue.severity == Severity.ERROR:
            return EXIT_ISSUES
        if issue.severity == Severity.WARNING and fail_on == Severity.WARNING:
            return EXIT_ISSUES
        if fail_on == Severity.INFO:
            return EXIT_ISSUES
    return EXIT_CLEAN
