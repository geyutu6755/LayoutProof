"""Shared fixtures and tiny stdlib HTTP helpers for the web endpoint suite."""

from __future__ import annotations

import json
import sys
import threading
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import pytest

# Ensure the project root (which holds the importable ``web`` and editable
# ``layoutproof`` packages) is on sys.path no matter where pytest was launched.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from web.server import make_server  # noqa: E402


@pytest.fixture()
def web_server(tmp_path):
    httpd = make_server(
        "127.0.0.1",
        0,
        workdir=str(tmp_path / "workspace"),
        max_upload_bytes=8 * 1024 * 1024,
    )
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    host, port = httpd.server_address[:2]
    base = f"http://{host}:{port}"
    try:
        yield base, httpd
    finally:
        httpd.shutdown()
        httpd.server_close()


def http_request(
    base: str,
    method: str,
    path: str,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], bytes]:
    req = urllib.request.Request(base + path, data=body, method=method)
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read()


def request_json(*args, **kwargs):
    status, headers, raw = http_request(*args, **kwargs)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        payload = None
    return status, headers, payload


def build_multipart(
    filename: str,
    content: bytes,
    *,
    field_name: str = "file",
    extra_fields: dict[str, str] | None = None,
) -> tuple[bytes, dict[str, str]]:
    boundary = "----lpwebboundary" + uuid.uuid4().hex
    chunks: list[bytes] = []
    for name, value in (extra_fields or {}).items():
        chunks.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n".encode()
        )
    disposition = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="{field_name}"; '
        f'filename="{filename}"\r\n'
        f"Content-Type: application/x-vnd.openxml.pptx\r\n\r\n"
    )
    chunks.append(disposition.encode())
    chunks.append(content)
    chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode())
    body = b"".join(chunks)
    headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Content-Length": str(len(body)),
    }
    return body, headers


def upload_deck(base: str, path: Path, *, filename: str | None = None):
    data = path.read_bytes()
    body, headers = build_multipart(filename or path.name, data)
    return request_json(base, "POST", "/api/upload", body=body, headers=headers)


def json_post(base: str, path: str, obj: dict):
    body = json.dumps(obj).encode()
    headers = {"Content-Type": "application/json", "Content-Length": str(len(body))}
    return request_json(base, "POST", path, body=body, headers=headers)


def scan_session(base: str, session_id: str, profile: str = "core"):
    return json_post(base, "/api/scan", {"session_id": session_id, "profile": profile})


def fix_session(base: str, session_id: str, profile: str = "core"):
    return json_post(base, "/api/fix", {"session_id": session_id, "profile": profile})
