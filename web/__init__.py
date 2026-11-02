"""Local offline web UI package for LayoutProof.

This package wraps the stable public Python API (``scan_file``, ``fix_file``,
``render_presentation``) behind a small stdlib-only HTTP server bound to the
loopback interface. It adds no detection logic of its own.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
