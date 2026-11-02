"""Render a self-contained, bilingual HTML report for a LayoutProof scan."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..models import RULES, FixReport, ScanResult

_TEMPLATES_DIR = Path(__file__).with_name("templates")


def _image_data_uri(path: str | Path) -> str:
    """Embed a PNG as a base64 data URI so the report stays self-contained."""
    raw = Path(path).read_bytes()
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _json_script_payload(value: Any) -> str:
    """Serialise JSON for a ``<script type="application/json">`` data block.

    The payload is user-influenced: shape names, details and file names come
    from the scanned deck. A literal ``</script>`` inside the JSON would still
    terminate the element in the HTML parser (non-executing MIME type does not
    change CDATA-like script parsing), allowing a malicious deck to break out
    and inject markup. Escape HTML metacharacters as JSON unicode escapes;
    ``JSON.parse`` / ``textContent`` decode them back unchanged, so no report
    data is lost.
    """
    text = json.dumps(value, ensure_ascii=False)
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _markers_for_slide(result: ScanResult, slide_number: int) -> list[dict]:
    """Normalized issue markers for one slide, positioned over the image."""
    markers: list[dict] = []
    for issue in result.issues:
        if issue.slide_number != slide_number:
            continue
        d = issue.to_dict(result.slide_width, result.slide_height)
        loc = d.get("normalized_location")
        markers.append(
            {
                "rule_id": d["rule_id"],
                "severity": d["severity"],
                "location": loc,
                "detail": d["detail"],
            }
        )
    return markers


def _build_render_view(
    render_result: Any,
    result: ScanResult,
    fixed_render: Any = None,
    fixed_result: ScanResult | None = None,
) -> dict[str, Any] | None:
    """Build the rendered-slides view, including before/after when fixed."""
    if render_result is None:
        return None

    before_slides = []
    for slide in render_result.slides:
        num = slide.slide_number
        before_slides.append(
            {
                "number": num,
                "image": _image_data_uri(slide.image_path),
                "width_px": slide.width_px,
                "height_px": slide.height_px,
                "markers": _markers_for_slide(result, num),
            }
        )

    after_slides: list[dict] = []
    if fixed_render is not None and fixed_result is not None:
        for slide in fixed_render.slides:
            num = slide.slide_number
            after_slides.append(
                {
                    "number": num,
                    "image": _image_data_uri(slide.image_path),
                    "markers": _markers_for_slide(fixed_result, num),
                }
            )

    return {
        "rendered": render_result.rendered,
        "status": render_result.status,
        "reason": render_result.reason,
        "renderer": render_result.renderer.to_dict(),
        "diagnostics": render_result.diagnostics,
        "before_slides": before_slides,
        "after_slides": after_slides,
        "has_after": bool(after_slides),
    }


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
            fix_report.before_summary.get("total", 0) - fix_report.after_summary.get("total", 0),
        ),
        "applied": [a.to_dict() for a in fix_report.applied],
        "skipped": [a.to_dict() for a in fix_report.skipped],
    }


def render_html(
    result: ScanResult,
    output_path: str | Path,
    lang: str = "en",
    fix_report: FixReport | None = None,
    render_result: Any = None,
    fixed_render: Any = None,
    fixed_result: ScanResult | None = None,
) -> Path:
    """Render *result* to a self-contained HTML file at *output_path*.

    *lang* selects the initial UI language (``"en"`` or ``"zh"``); the report
    ships a client-side toggle so readers can switch without a reload. When
    *render_result* is supplied the report embeds real rendered slides with
    issue markers; *fixed_render*/*fixed_result* add a before/after comparison.
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
        "issues_json": _json_script_payload(issues_view),
        "fix_report": _build_fix_view(fix_report),
        "render_view": _build_render_view(render_result, result, fixed_render, fixed_result),
        "style_css": style_css,
        "report_js": report_js,
    }

    html = template.render(**context)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path
