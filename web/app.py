"""HTTP application logic for the LayoutProof offline web UI.

All detection, repair and rendering is delegated to the stable public package
API:

* :func:`layoutproof.scan_file`
* :func:`layoutproof.fix_file`
* :func:`layoutproof.render_presentation`
* :func:`layoutproof.report.render_html` / ``validate_output``

This layer only owns HTTP transport, session orchestration and safe file
servicing. No rule, threshold or heuristic is reimplemented here.
"""

from __future__ import annotations

import email
import json
import mimetypes
import platform
import urllib.parse
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from layoutproof import TOOL_VERSION, fix_file, scan_file
from layoutproof.models import RULES, Severity
from layoutproof.render import detect_renderer, render_presentation
from layoutproof.report import render_html, validate_output

from .store import EscapeError, SessionStore, UnknownSession
from .upload import (
    DEFAULT_MAX_UPLOAD_BYTES,
    UploadRejected,
    accepted_display_name,
    enforce_size,
    inspect_pptx_zip,
    sanitize_display_name,
)

ALLOWED_PROFILES = ("core", "full")
STATIC_DIR_DEFAULT = Path(__file__).resolve().parent / "static"
STATIC_FILES = {"index.html", "style.css", "app.js", "i18n.js", "logic.js"}
JSON_BODY_LIMIT = 1 * 1024 * 1024
PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


@dataclass
class Response:
    status: int
    body: bytes
    headers: dict[str, str] = field(default_factory=dict)


def _json(obj: Any, status: int = 200, extra: dict[str, str] | None = None) -> Response:
    payload = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Content-Length": str(len(payload)),
    }
    if extra:
        headers.update(extra)
    return Response(status, payload, headers)


def _error(reason: str, status: int, *, detail: str | None = None) -> Response:
    body: dict[str, Any] = {"error": reason}
    if detail:
        body["detail"] = detail
    return _json(body, status)


def build_overview(result: Any) -> dict[str, Any]:
    """Per-slide buckets plus document-level bucket for the UI overview."""
    per_slide = [
        {"number": i + 1, "error": 0, "warning": 0, "info": 0, "total": 0}
        for i in range(getattr(result, "slide_count", 0) or 0)
    ]
    document = {"error": 0, "warning": 0, "info": 0, "total": 0}
    for issue in result.issues:
        bucket = document if issue.slide_number <= 0 else per_slide[issue.slide_number - 1]
        bucket[issue.severity.value] += 1
        bucket["total"] += 1
    return {
        "summary": result.summarize().to_dict(),
        "per_slide": per_slide,
        "document": document,
    }


def render_manifest(result: Any) -> dict[str, Any]:
    return {
        "status": result.status,
        "rendered": result.rendered,
        "reason": result.reason,
        "renderer": result.renderer.to_dict(),
        "slide_count": len(result.slides),
        "slides": [
            {
                "number": slide.slide_number,
                "width_px": slide.width_px,
                "height_px": slide.height_px,
            }
            for slide in result.slides
        ],
    }


class WebApp:
    def __init__(
        self,
        store: SessionStore,
        *,
        max_upload_bytes: int | None = None,
        static_dir: Path | None = None,
    ) -> None:
        self.store = store
        self.max_upload_bytes = max_upload_bytes or DEFAULT_MAX_UPLOAD_BYTES
        self.static_dir = (static_dir or STATIC_DIR_DEFAULT).resolve()
        self.renderer_info = detect_renderer()

    # ---------------------------------------------------------------- HTTP
    def dispatch(
        self,
        method: str,
        raw_path: str,
        headers: dict[str, str],
        body: bytes,
    ) -> Response:
        parsed = urllib.parse.urlsplit(raw_path)
        path = urllib.parse.unquote(parsed.path)
        query = urllib.parse.parse_qs(parsed.query)
        segments = [seg for seg in path.split("/") if seg]

        try:
            return self._route(method, segments, query, headers, body)
        except UploadRejected as exc:
            return _error("upload_rejected", exc.status, detail=exc.reason)
        except (UnknownSession, EscapeError):
            return _error("not_found", 404, detail="session or resource does not exist")
        except json.JSONDecodeError:
            return _error("invalid_json_body", 400)
        except Exception as exc:  # defensive: localhost tool must never crash the thread
            return _error("internal_error", 500, detail=f"{type(exc).__name__}: {exc}")

    def _route(
        self,
        method: str,
        segments: list[str],
        query: dict[str, list[str]],
        headers: dict[str, str],
        body: bytes,
    ) -> Response:
        if method not in {"GET", "POST", "HEAD"}:
            return _error("method_not_allowed", 405)

        # Static surface
        non_get_static = not segments or (segments[0] == "static" and len(segments) == 2)
        if method not in ("GET", "HEAD") and non_get_static:
            return _error("method_not_allowed", 405)
        if not segments:
            return self._static_file("index.html")
        if segments[0] == "static" and len(segments) == 2:
            return self._static_file(segments[1])

        # API surface
        if segments and segments[0] == "api":
            return self._api_route(method, segments[1:], query, headers, body)

        return _error("not_found", 404, detail="unknown route")

    def _static_file(self, name: str) -> Response:
        if name not in STATIC_FILES:
            return _error("not_found", 404, detail="unknown static asset")
        file_path = (self.static_dir / name).resolve()
        if file_path != self.static_dir and self.static_dir not in file_path.parents:
            return _error("not_found", 404)
        if not file_path.is_file():
            return _error("not_found", 404, detail="static asset missing")
        data = file_path.read_bytes()
        ctype, _ = mimetypes.guess_type(name)
        if ctype is None:
            ctype = "application/octet-stream"
        if name.endswith((".html", ".css", ".js")):
            ctype += "; charset=utf-8"
        return Response(
            200,
            data,
            {"Content-Type": ctype, "Content-Length": str(len(data)), "Cache-Control": "no-store"},
        )

    # ----------------------------------------------------------------- API
    def _api_route(
        self,
        method: str,
        segments: list[str],
        query: dict[str, list[str]],
        headers: dict[str, str],
        body: bytes,
    ) -> Response:
        if segments == ["health"] and method == "GET":
            return self._health()
        if segments == ["meta"] and method == "GET":
            return self._meta()
        if segments == ["upload"] and method == "POST":
            return self._upload(headers, body)
        if segments == ["scan"] and method == "POST":
            return self._scan(body)
        if segments == ["fix"] and method == "POST":
            return self._fix(body)
        if len(segments) == 2 and segments[0] == "state" and method == "GET":
            return self._state(segments[1])
        if len(segments) == 3 and segments[0] == "render" and method == "GET":
            return self._render(segments[1], segments[2])
        if len(segments) == 4 and segments[0] == "image" and method == "GET":
            return self._image(segments[1], segments[2], segments[3])
        if len(segments) == 3 and segments[0] == "download" and segments[1] == "fixed":
            return self._download_fixed(segments[2], method)
        if len(segments) == 3 and segments[0] == "report" and segments[1] == "json":
            return self._report_json(segments[2], query, method)
        if len(segments) == 3 and segments[0] == "report" and segments[1] == "html":
            return self._report_html(segments[2], query, method)

        return _error("not_found", 404, detail="unknown api route")

    def _health(self) -> Response:
        return _json(
            {
                "ok": True,
                "offline": True,
                "tool": {"name": "layoutproof", "version": TOOL_VERSION},
                "python": platform.python_version(),
                "renderer": self.renderer_info.to_dict(),
            }
        )

    def _meta(self) -> Response:
        rules = []
        for rule_id, spec in RULES.items():
            rules.append(
                {
                    "id": rule_id,
                    "severity": spec.severity.value,
                    "fixable": spec.fixable,
                    "fix_id": spec.fix_id,
                    "title_en": spec.title_en,
                    "title_zh": spec.title_zh,
                    "explanation_en": spec.explanation_en,
                    "explanation_zh": spec.explanation_zh,
                    "recommendation_en": spec.recommendation_en,
                    "recommendation_zh": spec.recommendation_zh,
                }
            )
        return _json(
            {
                "languages": ["en", "zh"],
                "profiles": list(ALLOWED_PROFILES),
                "max_upload_mb": round(self.max_upload_bytes / (1024 * 1024), 2),
                "renderer": self.renderer_info.to_dict(),
                "rules": rules,
                "severities": [s.value for s in Severity],
            }
        )

    # ---------------------------------------------------------------- upload
    def _upload(self, headers: dict[str, str], body: bytes) -> Response:
        declared = headers.get("Content-Length")
        declared_int = int(declared) if declared and declared.isdigit() else None
        enforce_size(len(body), self.max_upload_bytes, declared=declared_int)

        content_type = headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type.lower():
            return _error(
                "unsupported_content_type",
                400,
                detail="multipart/form-data with a 'file' field required",
            )

        parts = self._parse_multipart(body, content_type)
        chosen = next((p for p in parts if p[0]), None)
        if chosen is None:
            return _error("no_file_part", 400, detail="expected a file field named 'file'")
        raw_name, data = chosen
        display_name = sanitize_display_name(raw_name)
        if not accepted_display_name(display_name):
            return _error("unsupported_file_type", 400, detail="only .pptx decks are accepted")
        if not data:
            return _error("empty_upload", 400, detail="uploaded file has zero bytes")

        session = self.store.create(display_name, len(data))
        session.source_path.write_bytes(data)
        try:
            stats = inspect_pptx_zip(session.source_path)
        except UploadRejected:
            self.store.discard(session)
            raise
        session.zip_stats = stats

        return _json(
            {
                "session_id": session.session_id,
                "file_name": session.display_name,
                "size_bytes": session.size_bytes,
                "archive": stats,
            },
            status=201,
        )

    @staticmethod
    def _parse_multipart(body: bytes, content_type: str) -> list[tuple[str | None, bytes]]:
        header = f"Content-Type: {content_type}\r\n\r\n".encode()
        message = email.message_from_bytes(header + body)
        parts: list[tuple[str | None, bytes]] = []
        for part in message.walk():
            if part.is_multipart():
                continue
            filename = part.get_filename()
            payload = part.get_payload(decode=True) or b""
            parts.append((filename, payload))
        return parts

    # ----------------------------------------------------------------- scan
    def _json_body(self, body: bytes) -> dict[str, Any]:
        if len(body) > JSON_BODY_LIMIT:
            raise UploadRejected("request body too large", status=413)
        if not body:
            return {}
        return json.loads(body.decode("utf-8"))

    def _scan(self, body: bytes) -> Response:
        data = self._json_body(body)
        session = self.store.get(data.get("session_id"))
        profile = data.get("profile", "core")
        if profile not in ALLOWED_PROFILES:
            allowed = ", ".join(ALLOWED_PROFILES)
            return _error("invalid_profile", 400, detail=f"profile must be one of {allowed}")

        result = scan_file(session.source_path, profile=profile)
        session.scan_result = result
        session.scanned = True
        return _json(
            {
                "session_id": session.session_id,
                "scan": result.to_dict(),
                "overview": build_overview(result),
            }
        )

    def _state(self, session_id: str) -> Response:
        session = self.store.get(session_id)
        return _json(
            {
                "session_id": session.session_id,
                "file_name": session.display_name,
                "size_bytes": session.size_bytes,
                "scanned": session.scanned,
                "fixed": session.fixed,
                "has_fixed_file": session.fixed_path.exists(),
                "scan_status": session.scan_result.status if session.scan_result else None,
                "fix_success": session.fix_report.success if session.fix_report else None,
            }
        )

    # ------------------------------------------------------------------ fix
    def _fix(self, body: bytes) -> Response:
        data = self._json_body(body)
        session = self.store.get(data.get("session_id"))
        profile = data.get("profile", "core")
        if profile not in ALLOWED_PROFILES:
            allowed = ", ".join(ALLOWED_PROFILES)
            return _error("invalid_profile", 400, detail=f"profile must be one of {allowed}")

        report = fix_file(
            session.source_path,
            output_path=session.fixed_path,
            profile=profile,
            make_backup=False,
        )
        session.fix_report = report
        after_scan = None
        if report.created and session.fixed_path.exists():
            after_scan = scan_file(session.fixed_path, profile=profile)
            session.after_scan = after_scan
            session.fixed = True

        payload: dict[str, Any] = {
            "session_id": session.session_id,
            "fix": report.to_dict(),
            "before_overview": build_overview(session.scan_result) if session.scan_result else None,
            "after_overview": build_overview(after_scan) if after_scan else None,
        }
        if after_scan is not None:
            payload["after_scan"] = after_scan.to_dict()
        return _json(payload)

    # ---------------------------------------------------------------- render
    def _render(self, session_id: str, which: str) -> Response:
        session = self.store.get(session_id)
        if which not in ("before", "after"):
            return _error("invalid_render_stage", 400, detail="stage must be 'before' or 'after'")
        if which == "after" and not session.fixed_path.exists():
            return _error("fixed_deck_not_ready", 404, detail="run fix before rendering 'after'")

        cached = session.before_render if which == "before" else session.after_render
        if cached is None:
            source = session.source_path if which == "before" else session.fixed_path
            result = render_presentation(source, session.render_dir(which), dpi=120)
            if which == "before":
                session.before_render = result
            else:
                session.after_render = result
            cached = result
        return _json(
            {"session_id": session.session_id, "stage": which, "render": render_manifest(cached)}
        )

    def _image(self, session_id: str, which: str, segment: str) -> Response:
        session = self.store.get(session_id)
        if which not in ("before", "after"):
            return _error("invalid_render_stage", 400)
        result = session.before_render if which == "before" else session.after_render
        raw = segment.rsplit(".", 1)[0]
        if not raw.isdigit():
            return _error("invalid_slide_number", 400)
        number = int(raw)
        if result is None or not result.rendered:
            return _error(
                "render_not_available",
                404,
                detail="static fallback: no rendered slide image exists",
            )
        slide = next((s for s in result.slides if s.slide_number == number), None)
        if slide is None:
            return _error("slide_not_found", 404)
        image_path = Path(slide.image_path)
        if not self.store.within_root(session, image_path) or not image_path.is_file():
            return _error("slide_not_found", 404)
        data = image_path.read_bytes()
        return Response(
            200,
            data,
            {
                "Content-Type": "image/png",
                "Content-Length": str(len(data)),
                "Cache-Control": "no-store",
            },
        )

    # ------------------------------------------------------------- downloads
    def _download_fixed(self, session_id: str, method: str) -> Response:
        if method != "GET":
            return _error("method_not_allowed", 405)
        session = self.store.get(session_id)
        if not session.fixed_path.exists():
            return _error("fixed_deck_not_ready", 404, detail="run fix first")
        data = session.fixed_path.read_bytes()
        filename = f"{Path(session.display_name).stem}.fixed.pptx"
        return Response(
            200,
            data,
            {
                "Content-Type": PPTX_MIME,
                "Content-Length": str(len(data)),
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )

    def _report_json(self, session_id: str, query: dict[str, list[str]], method: str) -> Response:
        if method != "GET":
            return _error("method_not_allowed", 405)
        session = self.store.get(session_id)
        if session.scan_result is None:
            return _error("scan_not_ready", 404, detail="run scan first")

        scan_dict = session.scan_result.to_dict()
        fix_dict = session.fix_report.to_dict() if session.fix_report else None
        after_dict = session.after_scan.to_dict() if session.after_scan else None

        validation: dict[str, str] = {}
        try:
            validation["scan"] = validate_output(scan_dict)
        except Exception as exc:
            validation["scan"] = f"invalid: {exc}"
        if fix_dict is not None:
            try:
                validation["fix"] = validate_output(fix_dict)
            except Exception as exc:
                validation["fix"] = f"invalid: {exc}"

        envelope = {
            "tool": {"name": "layoutproof", "version": TOOL_VERSION},
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "validation": validation,
            "scan": scan_dict,
            "fix": fix_dict,
            "after_scan": after_dict,
            "render": {
                "before": render_manifest(session.before_render) if session.before_render else None,
                "after": render_manifest(session.after_render) if session.after_render else None,
            },
        }
        payload = json.dumps(envelope, ensure_ascii=False, indent=2).encode("utf-8")
        return Response(
            200,
            payload,
            {
                "Content-Type": "application/json; charset=utf-8",
                "Content-Length": str(len(payload)),
                "Content-Disposition": 'attachment; filename="layoutproof-report.json"',
            },
        )

    def _report_html(self, session_id: str, query: dict[str, list[str]], method: str) -> Response:
        if method != "GET":
            return _error("method_not_allowed", 405)
        session = self.store.get(session_id)
        if session.scan_result is None:
            return _error("scan_not_ready", 404, detail="run scan first")
        lang = (query.get("lang", ["en"])[0] or "en").lower()
        if lang not in ("en", "zh"):
            lang = "en"

        out_path = session.root / "report.html"
        render_html(
            session.scan_result,
            out_path,
            lang=lang,
            fix_report=session.fix_report,
            render_result=session.before_render,
            fixed_render=session.after_render,
            fixed_result=session.after_scan,
        )
        data = out_path.read_bytes()
        return Response(
            200,
            data,
            {
                "Content-Type": "text/html; charset=utf-8",
                "Content-Length": str(len(data)),
                "Content-Disposition": 'attachment; filename="layoutproof-report.html"',
            },
        )
