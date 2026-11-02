"""Safe validation for browser-uploaded .pptx payloads (stdlib only).

The web layer never trusts a client-supplied filename for disk paths: display
names are sanitized, bytes are size-capped and the central directory of the
archive is inspected without extracting anything. Mirrors the threat classes
handled by ``layoutproof.parsing.package`` (zip-slip names, duplicates,
bombs, missing required parts) so a hostile upload cannot reach the engine
through a disguised file.
"""

from __future__ import annotations

import posixpath
import zipfile
from pathlib import Path

DEFAULT_MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MiB default ceiling
MAX_ZIP_ENTRIES = 5000
MAX_ZIP_UNCOMPRESSED = 2 * 1024 * 1024 * 1024  # 2 GB, matches core loader
DISPLAY_NAME_MAX_LEN = 255


class UploadRejected(Exception):
    """A rejected upload. ``status`` is the HTTP status the handler should use."""

    def __init__(self, reason: str, *, status: int = 400) -> None:
        super().__init__(reason)
        self.reason = reason
        self.status = status


def sanitize_display_name(raw: str | None) -> str:
    """Reduce a client filename to a bare basename used for display only."""
    if not raw:
        return "deck.pptx"
    # Strip every directory component a browser or hostile client may send.
    name = Path(raw.replace("\x00", "")).name.strip()
    return name or "deck.pptx"


def accepted_display_name(name: str) -> bool:
    """Extension whitelist; the bytes themselves are validated afterwards."""
    return (
        name.lower().endswith(".pptx") and len(name) <= DISPLAY_NAME_MAX_LEN and "\x00" not in name
    )


def is_unsafe_member_name(name: str) -> bool:
    """True for absolute, drive-letter, backslash or parent-traversal members."""
    if not name:
        return True
    if name.startswith(("/", "\\")) or (len(name) > 1 and name[1] == ":"):
        return True
    if "\\" in name:
        return True
    parts = posixpath.normpath(name).split("/")
    return any(part == ".." for part in parts)


def enforce_size(byte_count: int, max_bytes: int, *, declared: int | None = None) -> None:
    if declared is not None and declared > max_bytes:
        raise UploadRejected("upload exceeds the configured size limit", status=413)
    if byte_count > max_bytes:
        raise UploadRejected("upload exceeds the configured size limit", status=413)


def inspect_pptx_zip(path: Path) -> dict[str, int]:
    """Read the archive central directory only; never extract to disk.

    Raises :class:`UploadRejected` on malformed, hostile or incomplete packages.
    Returns light statistics for diagnostics on success.
    """
    try:
        zf = zipfile.ZipFile(path, "r")
    except zipfile.BadZipFile as exc:
        raise UploadRejected(f"uploaded file is not a valid zip/pptx package: {exc}") from exc

    with zf:
        infos = zf.infolist()
        if len(infos) > MAX_ZIP_ENTRIES:
            raise UploadRejected(f"archive has {len(infos)} entries (limit {MAX_ZIP_ENTRIES})")
        seen: set[str] = set()
        total_uncompressed = 0
        for info in infos:
            name = info.filename
            if is_unsafe_member_name(name):
                raise UploadRejected(f"unsafe archive member name: {name!r}")
            if name in seen:
                raise UploadRejected(f"duplicate archive member: {name!r}")
            seen.add(name)
            total_uncompressed += info.file_size
            if total_uncompressed > MAX_ZIP_UNCOMPRESSED:
                raise UploadRejected("archive exceeds the uncompressed-size quota")

        if "[Content_Types].xml" not in seen:
            raise UploadRejected("missing required part [Content_Types].xml")
        if not any(n.startswith("ppt/presentation") for n in seen):
            raise UploadRejected("missing ppt/presentation main part")

    return {"entries": len(seen), "uncompressed_bytes": total_uncompressed}
