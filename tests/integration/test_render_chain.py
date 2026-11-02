"""Integration tests for the real PPTX -> PDF -> images chain.

These require a LibreOffice/soffice binary. They are skipped automatically
when no renderer is detected, so the suite never fakes a render result.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from layoutproof.render import detect_renderer, render_presentation
from layoutproof.render.images import render_pdf, pdf_fonts

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "test_fixtures" / "corpus"


@pytest.fixture(scope="module")
def renderer():
    info = detect_renderer()
    if not info.available:
        pytest.skip("no LibreOffice/soffice renderer available")
    return info


def test_detect_and_render_real_deck(renderer, tmp_path):
    source = CORPUS / "clean_basic.pptx"
    result = render_presentation(source, tmp_path / "work", dpi=96)
    assert result.rendered is True
    assert result.status == "rendered"
    assert result.reason is None
    assert result.pdf_path and Path(result.pdf_path).exists()
    assert len(result.slides) >= 1
    for slide in result.slides:
        assert Path(slide.image_path).exists()
        assert slide.width_px > 0 and slide.height_px > 0
    # Diagnostics record the renderer version and DPI.
    assert result.diagnostics["dpi"] == 96
    assert result.renderer.version.startswith("LibreOffice")


def test_render_pdf_and_fonts(renderer, tmp_path):
    source = CORPUS / "clean_basic.pptx"
    full = render_presentation(source, tmp_path / "w", dpi=96)
    pdf = Path(full.pdf_path)
    images = render_pdf(pdf, tmp_path / "imgs", dpi=96)
    assert images and all(Path(i.image_path).exists() for i in images)
    fonts = pdf_fonts(pdf)
    assert isinstance(fonts, list)


def test_render_pdf_raises_without_pymupdf(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "layoutproof.render.images.pymupdf", None, raising=False
    )
    with pytest.raises(RuntimeError):
        render_pdf(CORPUS / "clean_basic.pptx", tmp_path)
