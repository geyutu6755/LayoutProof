"""PDF to per-slide image rendering and font diagnostics (PyMuPDF)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

try:
    import pymupdf
except ImportError:  # pragma: no cover - exercised only when the extra is missing
    pymupdf = None


@dataclass
class SlideImage:
    slide_number: int
    image_path: str
    width_px: int
    height_px: int

    def to_dict(self) -> dict:
        return {
            "slide_number": self.slide_number,
            "image_path": self.image_path,
            "width_px": self.width_px,
            "height_px": self.height_px,
        }


def is_available() -> bool:
    return pymupdf is not None


def render_pdf(
    pdf_path: str | Path,
    out_dir: str | Path,
    dpi: int = 150,
) -> list[SlideImage]:
    """Render every PDF page to a PNG.

    Raises ``RuntimeError`` if PyMuPDF is not installed or the PDF cannot be
    opened; the caller maps that to a static fallback.
    """
    if not is_available():
        raise RuntimeError(
            "PyMuPDF is not installed. Install the 'render' extra "
            "(pip install layoutproof[render]) to rasterize PDF pages."
        )
    pdf_path = Path(pdf_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        doc = pymupdf.open(pdf_path)
    except Exception as exc:  # pymupdf raises a range of mupdf errors
        raise RuntimeError(f"cannot open PDF {pdf_path}: {exc}") from exc

    scale = dpi / 72.0
    matrix = pymupdf.Matrix(scale, scale)
    images: list[SlideImage] = []
    try:
        for index, page in enumerate(doc):
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            image_path = out_dir / f"slide_{index + 1:02d}.png"
            pix.save(image_path)
            images.append(
                SlideImage(
                    slide_number=index + 1,
                    image_path=str(image_path),
                    width_px=pix.width,
                    height_px=pix.height,
                )
            )
    finally:
        doc.close()
    return images


def pdf_fonts(pdf_path: str | Path) -> list[dict]:
    """List the fonts referenced by each PDF page for diagnostics."""
    if not is_available():
        return []
    pdf_path = Path(pdf_path)
    try:
        doc = pymupdf.open(pdf_path)
    except Exception:
        return []
    seen: dict[tuple, dict] = {}
    try:
        for page_index, page in enumerate(doc):
            for font in page.get_fonts(full=True):
                # get_fonts tuple: xref, ext, type, basefont, name, encoding, ...
                key = (font[3], font[2])
                if key not in seen:
                    seen[key] = {
                        "base_font": font[3],
                        "font_type": font[2],
                        "first_seen_slide": page_index + 1,
                    }
    finally:
        doc.close()
    return list(seen.values())
