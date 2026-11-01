"""Render a self-contained, bilingual HTML report for a LayoutProof scan."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..models import RULES, FixReport, ScanResult

_TEMPLATES_DIR = Path(__file__).with_name("templates")


def _build_issues_view(result: ScanResult) -> list[dict[str, Any]]:
    """Merge each Issue with its bilingual RuleSpec metadata."""
    view: list[dict[str, Any]] = []
    for issue in result.issues:
        spec = RULES[issue.rule_id]
        d = issue.to_dict(result.slide_width, result.slide_height)
        d["file_name"] = result.file_name
        d["title_en"] = spec.title_en
        d["title_zh"] = spec.title_zh
        d["explanation_en"] = spec.explanation_en
        d["explanation_zh"] = spec.explanation_zh
        d["recommendation_en"] = spec.recommendation_en
        d["recommendation_zh"] = spec.recommendation_zh
        view.append(d)
    return view


def _build_fix_view(fix_report: FixReport | None) -> dict[str, Any] | None:
    if fix_report is None:
        return None
    return {
        "before": fix_report.before_summary,
        "after": fix_report.after_summary,
        "issues_removed": max(
            0,
            fix_report.before_summary.get("total", 0)
            - fix_report.after_summary.get("total", 0),
        ),
        "applied": [a.to_dict() for a in fix_report.applied],
        "skipped": [a.to_dict() for a in fix_report.skipped],
    }


def render_html(
    result: ScanResult,
    output_path: str | Path,
    lang: str = "en",
    fix_report: FixReport | None = None,
) -> Path:
    """Render *result* to a self-contained HTML file at *output_path*.

    *lang* selects the initial UI language (``"en"`` or ``"zh"``); the report
    ships a client-side toggle so readers can switch without a reload.
    """
    if lang not in ("en", "zh"):
        raise ValueError('lang must be "en" or "zh"')

    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(enabled_extensions=("html",)),
    )
    template = env.get_template("report.html")

    style_css = (_TEMPLATES_DIR / "style.css").read_text(encoding="utf-8")
    report_js = (_TEMPLATES_DIR / "report.js").read_text(encoding="utf-8")

    issues_view = _build_issues_view(result)
    summary = result.summarize()

    context = {
        "lang": lang,
        "file_name": result.file_name,
        "timestamp": result.timestamp,
        "status": result.status,
        "error": result.error,
        "slide_count": result.slide_count,
        "summary": summary.to_dict(),
        "issues": issues_view,
        "issues_json": json.dumps(issues_view, ensure_ascii=False),
        "fix_report": _build_fix_view(fix_report),
        "style_css": style_css,
        "report_js": report_js,
    }

    html = template.render(**context)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path
