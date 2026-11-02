"""Command-line interface for LayoutProof.

Subcommands
-----------
scan   inspect one or more .pptx files (default command)
fix    apply safe automatic fixes and re-verify
demo   generate a broken deck and a fixed deck to demonstrate value
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from .config import QualityConfig
from .engine import scan_file
from .models import (
    EXIT_CLEAN,
    EXIT_INTERNAL,
    EXIT_ISSUES,
    EXIT_USAGE,
    TOOL_VERSION,
    Severity,
    exit_code_for,
)


# ---------------------------------------------------------------------------
# Terminal rendering
# ---------------------------------------------------------------------------
def _color(text: str, code: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"\033[{code}m{text}\033[0m"


def _ensure_utf8_streams() -> None:
    """Force UTF-8 output so non-ASCII findings never crash on a cp1252 console.

    On Windows CI/runtime the default console code page may be ``cp1252``;
    writing CJK or other Unicode characters then raises ``UnicodeEncodeError``.
    Reconfiguring both standard streams to UTF-8 keeps the JSON and text
    contracts stable across platforms and pipes. ``errors='replace'`` is only a
    last-resort guard; UTF-8 represents every Unicode code point so it is not
    expected to trigger for valid input.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            # Some embedded hosts expose a stream that cannot be reconfigured;
            # leave it untouched rather than failing startup.
            continue


_SEVERITY_STYLE = {
    Severity.ERROR.value: ("ERROR", "31"),
    Severity.WARNING.value: ("WARN", "33"),
    Severity.INFO.value: ("INFO", "36"),
}


def render_text(result) -> str:
    lines = []
    header = f"LayoutProof {TOOL_VERSION} - {result.file_name}"
    lines.append(header)
    lines.append("=" * max(40, len(header)))
    if result.status == "error":
        lines.append(_color(f"Failed to scan: {result.error}", "31"))
        return "\n".join(lines)

    summary = result.summarize()
    lines.append(
        f"Slides: {result.slide_count} | "
        f"errors {summary.error}  warnings {summary.warning}  info {summary.info}"
    )
    lines.append("")
    if not result.issues:
        lines.append(_color("No issues found. Deck passed the selected profile.", "32"))
        return "\n".join(lines)

    for issue in result.issues:
        label, code = _SEVERITY_STYLE[issue.severity.value]
        where = f"slide {issue.slide_number}" if issue.slide_number else "document"
        if issue.shape_name:
            where += f" [{issue.shape_name}]"
        title = issue.spec.title_en
        left = _color(f"{label:<5}", code)
        lines.append(f"{left} {issue.rule_id:<22} {where}")
        lines.append(f"        {title}")
        if issue.detail:
            lines.append(f"        -> {issue.detail}")
        lines.append(f"        fix: {issue.spec.recommendation_en}")
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------
def _collect_paths(target: Path, recursive: bool) -> list[Path]:
    if target.is_file():
        return [target]
    if target.is_dir():
        pattern = "**/*.pptx" if recursive else "*.pptx"
        return sorted(p for p in target.glob(pattern) if p.is_file())
    return []


def _load_config(args: argparse.Namespace) -> QualityConfig:
    config = QualityConfig.load(args.config) if args.config else QualityConfig()
    if args.fail_on:
        config.fail_on = args.fail_on
    return config


def cmd_scan(args: argparse.Namespace) -> int:
    config = _load_config(args)
    paths = _collect_paths(Path(args.target), args.recursive)
    if not paths:
        print(f"No .pptx files found at: {args.target}", file=sys.stderr)
        return EXIT_USAGE

    results = [scan_file(p, config, profile=args.profile) for p in paths]
    if args.json:
        payload = [r.to_dict() for r in results]
        text = json.dumps(payload if len(payload) > 1 else payload[0], indent=2, ensure_ascii=False)
        if args.output:
            Path(args.output).write_text(text, encoding="utf-8")
        else:
            print(text)
    else:
        blocks = [render_text(r) for r in results]
        text = "\n\n".join(blocks)
        if args.output:
            Path(args.output).write_text(text, encoding="utf-8")
        else:
            print(text)

    # Exit code: worst result drives the process status.
    fail_severity = Severity(config.fail_on)
    code = EXIT_CLEAN
    for r in results:
        code = max(code, exit_code_for(r, fail_severity))
    return code


def cmd_fix(args: argparse.Namespace) -> int:
    try:
        from .fix.engine import fix_file
    except ImportError:
        print("Fix module is not available in this build.", file=sys.stderr)
        return EXIT_INTERNAL
    config = _load_config(args)
    report = fix_file(
        Path(args.target),
        Path(args.output) if args.output else None,
        config=config,
        profile=args.profile,
        make_backup=not args.no_backup,
    )
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(render_fix_text(report))
    return EXIT_CLEAN if report.success else EXIT_ISSUES


def render_fix_text(report) -> str:
    lines = [f"LayoutProof fix - {report.source_path}"]
    if not report.created:
        lines.append(_color(f"Fix failed: {report.note}", "31"))
        return "\n".join(lines)
    lines.append(f"Output: {report.output_path}")
    lines.append(f"Applied {len(report.applied)} fix(es), skipped {len(report.skipped)}.")
    before = report.before_summary
    after = report.after_summary
    lines.append(
        f"Before: {before.get('total', 0)} issues -> After: {after.get('total', 0)} "
        f"(removed {report.to_dict()['issues_removed']})"
    )
    for fix in report.applied:
        lines.append(f"  + {fix.action} ({fix.rule_id})")
    return "\n".join(lines)


def cmd_demo(args: argparse.Namespace) -> int:
    try:
        from .demo import run_demo
    except ImportError:
        print("Demo module is not available in this build.", file=sys.stderr)
        return EXIT_INTERNAL
    return run_demo(Path(args.dir), json_out=args.json)


def cmd_render(args: argparse.Namespace) -> int:
    """Render a PPTX to PDF/images, with a disclosed static fallback.

    Optionally emit a self-contained HTML report that embeds the slides and
    overlays issue markers. Never claims real rendering when the renderer is
    missing or fails.
    """
    from .render import render_presentation

    config = _load_config(args)
    source = Path(args.target)
    if not source.is_file():
        print(f"Input not found: {source}", file=sys.stderr)
        return EXIT_USAGE

    work = Path(args.outdir) if args.outdir else source.parent / f"{source.stem}.render"
    result = render_presentation(source, work, dpi=args.dpi)

    if result.rendered:
        print(f"Real rendering: {len(result.slides)} slide(s) -> {work}")
        print(f"Renderer: {result.renderer.version}")
    else:
        print("Static fallback — real rendering did not run:", file=sys.stderr)
        print(f"  {result.reason}", file=sys.stderr)

    if args.html:
        scan = scan_file(source, config, profile=args.profile)
        from .report import render_html

        render_html(
            scan,
            args.html,
            lang=args.lang,
            render_result=result,
        )
        print(f"HTML report: {args.html}")

    # Rendering itself succeeded (even a fallback is a handled outcome).
    return EXIT_CLEAN


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="layoutproof",
        description="Local-first quality assurance for AI-generated PowerPoint files.",
    )
    parser.add_argument("--version", action="version", version=f"LayoutProof {TOOL_VERSION}")
    sub = parser.add_subparsers(dest="command")

    p_scan = sub.add_parser("scan", help="Inspect .pptx files")
    p_scan.add_argument("target", help="A .pptx file or directory")
    p_scan.add_argument(
        "--recursive", "-r", action="store_true", help="Recursively scan a directory"
    )
    p_scan.add_argument("--json", action="store_true", help="Emit JSON output")
    p_scan.add_argument("--profile", default="core", choices=["core", "full"])
    p_scan.add_argument("--config", help="Path to a TOML/JSON config file")
    p_scan.add_argument("--fail-on", choices=["error", "warning", "info"])
    p_scan.add_argument("--output", "-o", help="Write output to a file")
    p_scan.set_defaults(handler=cmd_scan)

    p_fix = sub.add_parser("fix", help="Auto-fix issues and re-verify")
    p_fix.add_argument("target", help="A .pptx file")
    p_fix.add_argument("--output", "-o", help="Output path (default: <name>.fixed.pptx)")
    p_fix.add_argument("--no-backup", action="store_true")
    p_fix.add_argument("--json", action="store_true")
    p_fix.add_argument("--profile", default="core", choices=["core", "full"])
    p_fix.add_argument("--config")
    p_fix.add_argument("--fail-on", choices=["error", "warning", "info"])
    p_fix.set_defaults(handler=cmd_fix)

    p_demo = sub.add_parser("demo", help="Generate a broken and a fixed deck")
    p_demo.add_argument("--dir", default=".", help="Directory for demo files")
    p_demo.add_argument("--json", action="store_true")
    p_demo.set_defaults(handler=cmd_demo)

    p_render = sub.add_parser("render", help="Render PPTX to PDF/images with fallback")
    p_render.add_argument("target", help="A .pptx file")
    p_render.add_argument("--outdir", help="Work directory (default: <name>.render)")
    p_render.add_argument("--dpi", type=int, default=150, help="Image DPI")
    p_render.add_argument("--html", help="Also write a self-contained HTML report")
    p_render.add_argument("--lang", default="en", choices=["en", "zh"])
    p_render.add_argument("--profile", default="core", choices=["core", "full"])
    p_render.add_argument("--config")
    p_render.add_argument("--fail-on", choices=["error", "warning", "info"])
    p_render.set_defaults(handler=cmd_render)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    _ensure_utf8_streams()
    parser = build_parser()
    # Default to scan when a bare path is supplied.
    raw = list(sys.argv[1:] if argv is None else argv)
    if raw and raw[0] not in {"scan", "fix", "demo", "render", "--help", "-h", "--version"}:
        raw = ["scan", *raw]
    args = parser.parse_args(raw)
    if not getattr(args, "handler", None):
        parser.print_help()
        return EXIT_USAGE
    try:
        return args.handler(args)
    except Exception as exc:  # pragma: no cover - defensive guard
        print(f"Internal error: {exc}", file=sys.stderr)
        return EXIT_INTERNAL
