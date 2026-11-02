"""Stdlib-only HTTP server for the offline LayoutProof web UI.

Run with either::

    python -m web.server            # from the project root
    python -m web                   # equivalent

The server binds to 127.0.0.1 by default and uses an ephemeral port (0)
unless ``--port`` is given. It performs no outbound network calls; all
detection uses the local offline LayoutProof engine.
"""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .app import WebApp
from .store import SessionStore

DEFAULT_HOST = "127.0.0.1"
DEFAULT_MAX_MB = 50.0
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


class _Handler(BaseHTTPRequestHandler):
    server_version = "LayoutProofWeb/0.1"

    # Every HTTP method funnels through dispatch; the app returns JSON errors
    # for unsupported methods and never starts a shell or spawns processes.
    def _dispatch(self) -> None:
        declared = self.headers.get("Content-Length")
        length = int(declared) if declared and declared.isdigit() else 0
        body = self.rfile.read(length) if length > 0 else b""
        headers = dict(self.headers.items())
        response = self.server.app.dispatch(self.command, self.path, headers, body)
        self.send_response(response.status)
        for key, value in response.headers.items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(response.body)

    do_GET = _dispatch
    do_POST = _dispatch
    do_HEAD = _dispatch
    do_PUT = _dispatch
    do_DELETE = _dispatch
    do_PATCH = _dispatch

    def log_message(self, message: str, *args: Any) -> None:
        if getattr(self.server, "verbose", False):
            super().log_message(message, *args)


def make_server(
    host: str = DEFAULT_HOST,
    port: int = 0,
    *,
    workdir: str | None = None,
    max_upload_bytes: int | None = None,
) -> ThreadingHTTPServer:
    """Build a ready-to-serve server; call ``serve_forever`` on the result."""
    store = SessionStore(workdir)
    app = WebApp(store, max_upload_bytes=max_upload_bytes)
    httpd = ThreadingHTTPServer((host, port), _Handler)
    httpd.app = app  # type: ignore[attr-defined]
    httpd.daemon_threads = True
    return httpd


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="layoutproof-web",
        description="Offline localhost quality-assurance UI for AI-generated PPTX decks.",
    )
    parser.add_argument(
        "--host", default=DEFAULT_HOST, help="bind address (loopback only; default 127.0.0.1)"
    )
    parser.add_argument(
        "--port", type=int, default=0, help="TCP port; 0 picks an ephemeral free port (default 0)"
    )
    parser.add_argument(
        "--workdir",
        default=None,
        help="server-managed workspace root (default: a private temp dir)",
    )
    parser.add_argument(
        "--max-mb",
        type=float,
        default=DEFAULT_MAX_MB,
        help="upload size ceiling in MiB (default 50)",
    )
    parser.add_argument("--verbose", action="store_true", help="log HTTP requests")
    args = parser.parse_args(argv)

    if args.host not in LOOPBACK_HOSTS:
        parser.error("this offline tool refuses non-loopback binds; use 127.0.0.1")

    max_bytes = int(args.max_mb * 1024 * 1024)
    httpd = make_server(args.host, args.port, workdir=args.workdir, max_upload_bytes=max_bytes)
    httpd.verbose = args.verbose  # type: ignore[attr-defined]

    host, port = httpd.server_address[:2]
    print("LayoutProof offline web UI")
    print(f"  URL:  http://{host}:{port}/")
    print("  Uploads stay on this machine; no CDN or outbound network calls.")
    print("  Stop with Ctrl+C.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
