"""High-level render orchestration with an explicit static fallback.

``render_presentation`` never raises for a missing renderer. It returns a
:class:`RenderResult` whose ``status`` is either ``"rendered"`` (real
PPTX -> PDF -> images chain) or ``"static_fallback"`` with the reason. The
core static detection remains fully offline and independent of this module.
"""

from __future__ import annotations

import json
import platform
from dataclasses import dataclass, field
from pathlib import Path

from . import images as images_mod
from .backend import RendererInfo, convert_to_pdf, detect_renderer

RENDER_STATUS_RENDERED = "rendered"
RENDER_STATUS_STATIC = "static_fallback"


@dataclass
class RenderResult:
    status: str
    renderer: RendererInfo
    work_dir: str
    pdf_path: str | None = None
    slides: list[images_mod.SlideImage] = field(default_factory=list)
    diagnostics: dict = field(default_factory=dict)
    reason: str | None = None

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "renderer": self.renderer.to_dict(),
            "work_dir": self.work_dir,
            "pdf_path": self.pdf_path,
            "slides": [s.to_dict() for s in self.slides],
            "diagnostics": self.diagnostics,
            "reason": self.reason,
        }

    @property
    def rendered(self) -> bool:
        return self.status == RENDER_STATUS_RENDERED

    def slide_image(self, slide_number: int) -> str | None:
        for slide in self.slides:
            if slide.slide_number == slide_number:
                return slide.image_path
        return None


def _system_diagnostics() -> dict:
    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "architecture": platform.machine(),
        "pymupdf_available": images_mod.is_available(),
    }


def render_presentation(
    source: str | Path,
    work_dir: str | Path,
    dpi: int = 150,
    timeout: int = 180,
) -> RenderResult:
    """Render a PPTX to real per-slide images, or fall back to static.

    The work directory holds the PDF, images, isolated profile and a
    ``render-manifest.json``. Nothing outside it and the isolated profile is
    written.
    """
    source = Path(source)
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    profile_dir = work_dir / "profile"

    renderer = detect_renderer()
    diagnostics = _system_diagnostics()

    if not renderer.available:
        return _fallback(work_dir, renderer, diagnostics, renderer.reason)

    if not images_mod.is_available():
        reason = (
            "LibreOffice was found but PyMuPDF is not installed, so PDF pages "
            "could not be rasterized. Install the 'render' extra."
        )
        return _fallback(work_dir, renderer, diagnostics, reason)

    try:
        pdf = convert_to_pdf(
            source,
            work_dir / "pdf",
            renderer.executable,
            profile_dir,
            timeout=timeout,
        )
        slides = images_mod.render_pdf(pdf, work_dir / "images", dpi=dpi)
    except Exception as exc:  # renderer/rasterizer failure -> static fallback
        reason = f"Real rendering failed: {exc}"
        return _fallback(work_dir, renderer, diagnostics, reason)

    diagnostics["fonts"] = images_mod.pdf_fonts(pdf)
    diagnostics["dpi"] = dpi
    result = RenderResult(
        status=RENDER_STATUS_RENDERED,
        renderer=renderer,
        work_dir=str(work_dir),
        pdf_path=str(pdf),
        slides=slides,
        diagnostics=diagnostics,
    )
    _write_manifest(work_dir, result)
    return result


def _fallback(
    work_dir: Path,
    renderer: RendererInfo,
    diagnostics: dict,
    reason: str,
) -> RenderResult:
    result = RenderResult(
        status=RENDER_STATUS_STATIC,
        renderer=renderer,
        work_dir=str(work_dir),
        diagnostics=diagnostics,
        reason=reason,
    )
    _write_manifest(work_dir, result)
    return result


def _write_manifest(work_dir: Path, result: RenderResult) -> Path:
    manifest = work_dir / "render-manifest.json"
    manifest.write_text(
        json.dumps(result.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return manifest
