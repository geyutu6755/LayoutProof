"""Server-managed, isolated on-disk workspace for sessions.

Each upload lives in its own directory owned by the server. The client never
supplies a filesystem path or a filename used for storage; on-disk names are
fixed (``source.pptx`` / ``fixed.pptx``) and every read-back resolves inside
the session directory before bytes are returned.
"""

from __future__ import annotations

import re
import secrets
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SESSION_ID_RE = re.compile(r"^[0-9a-f]{16}$")
RENDER_WHICH = ("before", "after")


class UnknownSession(KeyError):
    """Raised when a session id is missing or malformed."""


class EscapeError(ValueError):
    """Raised when a resolved path would leave a session directory."""


@dataclass
class Session:
    session_id: str
    display_name: str
    size_bytes: int
    root: Path
    # Detector / fixer / render results; objects are kept so report builders
    # (e.g. layoutproof.report.render_html) can use them directly.
    scan_result: Any = None
    fix_report: Any = None
    after_scan: Any = None
    before_render: Any = None
    after_render: Any = None
    scanned: bool = False
    fixed: bool = False
    zip_stats: dict[str, int] | None = None

    @property
    def source_path(self) -> Path:
        return self.root / "source.pptx"

    @property
    def fixed_path(self) -> Path:
        return self.root / "fixed.pptx"

    def render_dir(self, which: str) -> Path:
        if which not in RENDER_WHICH:
            raise EscapeError(f"unknown render stage: {which!r}")
        return self.root / f"render_{which}"


class SessionStore:
    def __init__(self, root: str | Path | None = None) -> None:
        if root is None:
            root = Path(tempfile.mkdtemp(prefix="lpweb-"))
        else:
            root = Path(root)
            root.mkdir(parents=True, exist_ok=True)
        self.root = root.resolve()
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ CRUD
    def create(self, display_name: str, size_bytes: int) -> Session:
        session_id = secrets.token_hex(8)
        root = self.root / session_id
        root.mkdir(parents=True, exist_ok=True)
        session = Session(
            session_id=session_id,
            display_name=display_name,
            size_bytes=size_bytes,
            root=root,
        )
        with self._lock:
            self._sessions[session_id] = session
        return session

    def get(self, session_id: str | None) -> Session:
        if not isinstance(session_id, str) or not SESSION_ID_RE.fullmatch(session_id):
            raise UnknownSession(session_id or "")
        with self._lock:
            session = self._sessions.get(session_id)
        if session is None:
            raise UnknownSession(session_id)
        return session

    def discard(self, session: Session) -> None:
        """Remove an invalidated session (used after upload validation fails)."""
        with self._lock:
            self._sessions.pop(session.session_id, None)
        if session.root.exists():
            for child in sorted(session.root.rglob("*"), reverse=True):
                child.unlink(missing_ok=True)
            session.root.rmdir()

    # ----------------------------------------------------------------- paths
    def safe_member(self, session: Session, relative: str) -> Path:
        """Resolve *relative* inside the session root; refuse escapes."""
        if not relative or relative.startswith(("/", "\\")) or "\x00" in relative:
            raise EscapeError("invalid relative path")
        candidate = (session.root / relative).resolve()
        root = session.root.resolve()
        if candidate != root and root not in candidate.parents:
            raise EscapeError("path escapes the session directory")
        return candidate

    def within_root(self, session: Session, candidate: Path) -> bool:
        resolved = candidate.resolve()
        root = session.root.resolve()
        return resolved == root or root in resolved.parents
