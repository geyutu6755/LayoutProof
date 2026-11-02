"""Real rendering backend: LibreOffice/soffice discovery and invocation.

The renderer is optional. Detection, conversion and diagnostics are kept
isolated so a missing or failing renderer degrades to a clearly disclosed
static fallback instead of breaking the core offline checks.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

# Environment variable that explicitly pins a soffice executable.
ENV_SOFFICE = "LAYOUTPROOF_SOFFICE"

# Common Windows install locations checked before PATH.
_WINDOWS_CANDIDATES = [
    r"C:\Program Files\LibreOffice\program\soffice.com",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.com",
]


@dataclass
class RendererInfo:
    """Whether a real renderer is available and how it was resolved."""

    available: bool
    executable: str | None = None
    version: str | None = None
    reason: str = ""
    searched: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "available": self.available,
            "executable": self.executable,
            "version": self.version,
            "reason": self.reason,
            "searched": self.searched,
        }


def _candidate_paths() -> list[str]:
    """Ordered candidate executables, including the console wrapper."""
    candidates: list[str] = []
    pinned = os.environ.get(ENV_SOFFICE)
    if pinned:
        candidates.append(pinned)
    if os.name == "nt":
        candidates.extend(_WINDOWS_CANDIDATES)
        # If only the GUI .exe is found, prefer the sibling .com for stdout.
        for exe in (
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        ):
            com = exe[:-4] + ".com"
            if Path(com).exists() and com not in candidates:
                candidates.append(com)
    which = shutil.which("soffice")
    if which:
        candidates.append(which)
    return candidates


def detect_renderer() -> RendererInfo:
    """Locate a working soffice and read its version.

    Returns an unavailable :class:`RendererInfo` with the reason and the list
    of searched locations; callers must not treat that as a hard error.
    """
    searched: list[str] = []
    for candidate in _candidate_paths():
        searched.append(candidate)
        if not Path(candidate).exists():
            continue
        version = _read_version(candidate)
        if version is not None:
            return RendererInfo(
                available=True,
                executable=candidate,
                version=version,
                searched=searched,
            )
    return RendererInfo(
        available=False,
        reason=(
            "No LibreOffice/soffice executable found. Set the "
            f"{ENV_SOFFICE} environment variable or install LibreOffice to "
            "enable real rendering."
        ),
        searched=searched,
    )


def _decode(data: bytes | None) -> str:
    """Decode process output without assuming UTF-8.

    LibreOffice on a localized Windows can emit the system code page (e.g.
    GBK); decoding strictly as UTF-8 raises in the subprocess reader thread.
    Decode leniently so a non-ASCII console message never breaks a run.
    """
    if not data:
        return ""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        try:
            import locale

            encoding = locale.getpreferredencoding(False)
            return data.decode(encoding, errors="replace")
        except LookupError:
            return data.decode("utf-8", errors="replace")


def _run(cmd: list[str], timeout: int) -> subprocess.CompletedProcess:
    """Run a command capturing bytes (no text-mode decoding surprises)."""
    # The executable is a detected/validated renderer, never shell input;
    # argv is passed as a list with shell=False, so no command injection.
    return subprocess.run(  # noqa: S603
        cmd,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def _read_version(executable: str) -> str | None:
    """Return the renderer version string, or None on failure."""
    try:
        proc = _run([executable, "--version"], timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    text = _decode(proc.stdout) or _decode(proc.stderr)
    text = text.strip()
    if not text:
        return None
    # First line looks like "LibreOffice 26.2.7.3 <git-hash>".
    return text.splitlines()[0].strip()


def _user_installation_flag(profile_dir: Path) -> str:
    """Build an isolated -env:UserInstallation URL so the default profile and
    system configuration are never touched."""
    url = profile_dir.resolve().as_uri()
    return f"-env:UserInstallation={url}"


def convert_to_pdf(
    source: str | Path,
    out_dir: str | Path,
    executable: str,
    profile_dir: str | Path,
    timeout: int = 180,
) -> Path:
    """Convert a single PPTX to PDF using an isolated profile.

    Raises ``RuntimeError`` with the captured output when the PDF is not
    produced; the caller converts that into a static fallback.
    """
    source = Path(source)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    profile_dir = Path(profile_dir)
    profile_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        executable,
        "--headless",
        "--norestore",
        "--nofirststartwizard",
        _user_installation_flag(profile_dir),
        "--convert-to",
        "pdf",
        "--outdir",
        str(out_dir),
        str(source),
    ]
    proc = _run(cmd, timeout=timeout)
    pdf = out_dir / (source.stem + ".pdf")
    if not pdf.exists() or pdf.stat().st_size == 0:
        raise RuntimeError(
            "soffice did not produce a PDF. "
            f"exit={proc.returncode} stdout={_decode(proc.stdout)!r} "
            f"stderr={_decode(proc.stderr)!r}"
        )
    return pdf
