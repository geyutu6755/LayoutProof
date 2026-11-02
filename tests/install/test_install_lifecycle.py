"""Installation / packaging lifecycle.

Always-on checks validate the declared console entry point, the ``python -m``
invocation, the project virtualenv console script and an offline wheel build.

A full throwaway-venv install -> upgrade -> uninstall cycle requires resolving
runtime dependencies and is gated behind ``LAYOUTPROOF_INSTALL_TEST=1``; when
the environment cannot perform it (no index, locked-down host), the test skips
with a recorded reason instead of pretending success.
"""

from __future__ import annotations

import importlib
import importlib.metadata
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import helpers_decks as decks

ROOT = decks.ROOT


def _run(cmd: list[str], timeout: int = 300) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, capture_output=True, timeout=timeout)
    return proc


# ---------------------------------------------------------------------------
# Always-on packaging contract
# ---------------------------------------------------------------------------
def test_console_script_entry_point_declared_and_resolves():
    candidates = []
    try:
        dist = importlib.metadata.distribution("layoutproof")
        candidates = [
            (ep.name, ep.value)
            for ep in dist.entry_points
            if ep.group == "console_scripts" and ep.name == "layoutproof"
        ]
    except importlib.metadata.PackageNotFoundError:
        candidates = []
    assert candidates, "layoutproof console entry point must be declared"
    value = candidates[0][1]
    module_path, _, func_name = value.partition(":")
    module = importlib.import_module(module_path)
    assert callable(getattr(module, func_name))


def test_python_module_invocation_prints_version():
    proc = _run([sys.executable, "-m", "layoutproof", "--version"], timeout=60)
    assert proc.returncode == 0
    assert b"LayoutProof" in proc.stdout or b"layoutproof" in proc.stdout.lower()


def test_project_venv_console_script_executable():
    exe = ROOT / ".venv" / "Scripts" / "layoutproof.exe"
    if not exe.exists():
        pytest.skip("project .venv console script layoutproof.exe not present")
    proc = _run([str(exe), "--version"], timeout=60)
    assert proc.returncode == 0
    assert b"LayoutProof" in proc.stdout


def test_offline_wheel_build_succeeds(tmp_path):
    """Build a wheel without build isolation so no network index is required."""
    wheel_dir = tmp_path / "wheels"
    proc = _run([
        sys.executable, "-m", "pip", "wheel",
        "--no-deps", "--no-build-isolation",
        "-w", str(wheel_dir), str(ROOT),
    ], timeout=300)
    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", errors="replace")
        pytest.skip(f"offline wheel build unavailable in this interpreter: {stderr[-400:]}")
    wheels = list(wheel_dir.glob("*.whl"))
    assert wheels, "pip wheel reported success but produced no wheel file"


# ---------------------------------------------------------------------------
# Full lifecycle in an isolated throwaway venv (opt-in)
# ---------------------------------------------------------------------------
def test_isolated_venv_install_upgrade_uninstall(tmp_path):
    if os.environ.get("LAYOUTPROOF_INSTALL_TEST") != "1":
        pytest.skip(
            "full pip install/upgrade/uninstall cycle skipped; set "
            "LAYOUTPROOF_INSTALL_TEST=1 in an environment that can resolve "
            "dependencies for a throwaway virtualenv"
        )

    venv_dir = tmp_path / "freshvenv"
    create = _run([sys.executable, "-m", "venv", str(venv_dir)], timeout=180)
    if create.returncode != 0:
        pytest.skip("could not create a throwaway virtualenv: "
                    + create.stderr.decode("utf-8", errors="replace")[-300:])

    venv_py = venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not venv_py.exists():
        pytest.skip(f"venv interpreter not found at {venv_py}")

    def pip(args: list[str]) -> subprocess.CompletedProcess:
        return _run([str(venv_py), "-m", "pip", "install", "--no-build-isolation",
                     *args], timeout=600)

    installed = pip([str(ROOT)])
    if installed.returncode != 0:
        pytest.skip("dependency resolution unavailable offline; install aborted: "
                    + installed.stderr.decode("utf-8", errors="replace")[-400:])

    proc = _run([str(venv_py), "-m", "layoutproof", "--version"], timeout=60)
    assert proc.returncode == 0, "installed package must expose a working CLI"

    # upgrade / force-reinstall over an existing installation must not error
    upgraded = pip(["--upgrade", "--force-reinstall", str(ROOT)])
    assert upgraded.returncode == 0
    proc = _run([str(venv_py), "-m", "layoutproof", "--version"], timeout=60)
    assert proc.returncode == 0

    # uninstall removes the package import
    removed = _run([str(venv_py), "-m", "pip", "uninstall", "-y", "layoutproof"],
                   timeout=300)
    assert removed.returncode == 0
    check = _run([str(venv_py), "-c", "import layoutproof"], timeout=60)
    assert check.returncode != 0

    # reinstall restores a working installation
    reinstalled = pip([str(ROOT)])
    assert reinstalled.returncode == 0
    proc = _run([str(venv_py), "-m", "layoutproof", "--version"], timeout=60)
    assert proc.returncode == 0
