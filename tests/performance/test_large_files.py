"""Heavy-media performance tests (opt-in: set LAYOUTPROOF_PERF=1).

Generates REAL on-disk decks dominated by distinct noisy JPEG parts, scans the
complete file with the full rule profile, and records wall-clock time plus
tracemalloc peak memory. They are skipped in the default run because building
and decoding tens of MB of media is expensive; numbers captured during a gate
run are printed and asserted against generous but finite resource caps.
"""

from __future__ import annotations

import io
import os
import random
import time
import tracemalloc

import pytest
from PIL import Image
from pptx import Presentation
from pptx.util import Inches

from layoutproof.engine import scan_file
from layoutproof.parsing import build_model
from layoutproof.report import validate_output

pytestmark = pytest.mark.slow
GATE = "LAYOUTPROOF_PERF"


def _require_gate():
    if os.environ.get(GATE) != "1":
        pytest.skip(
            f"heavy media performance test skipped; set {GATE}=1 to generate "
            "~10MB/~50MB decks and record real timings"
        )


def _noisy_jpeg(rng: random.Random, width: int = 800, height: int = 600,
                quality: int = 25) -> bytes:
    raw = rng.randbytes(width * height * 3)
    image = Image.frombytes("RGB", (width, height), raw)
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def _build_media_deck(path, target_mb: float, per_slide: int = 12,
                       max_images: int = 700) -> dict:
    rng = random.Random(20261102)
    prs = Presentation()
    bytes_total = 0
    images = 0
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slot = 0
    while bytes_total < target_mb * 1024 * 1024 and images < max_images:
        data = _noisy_jpeg(rng)
        bytes_total += len(data)
        if slot >= per_slide:
            slide = prs.slides.add_slide(prs.slide_layouts[6])
            slot = 0
        col, row = divmod(slot, 4)
        slide.shapes.add_picture(
            io.BytesIO(data),
            Inches(0.25 + col * 1.15), Inches(0.2 + row * 1.7),
            width=Inches(1.0), height=Inches(0.8),
        )
        images += 1
        slot += 1
    prs.save(str(path))
    return {"images": images, "embedded_bytes": bytes_total,
            "slides": len(prs.slides)}


def _measure(path):
    tracemalloc.start()
    start = time.perf_counter()
    result = scan_file(path, profile="full")
    elapsed = time.perf_counter() - start
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    tracemalloc.clear_traces()
    return result, elapsed, peak


def test_ten_megabyte_media_deck(tmp_path):
    _require_gate()
    path = tmp_path / "media_10mb.pptx"
    plan = _build_media_deck(path, target_mb=10.0)

    model = build_model(path)
    picture_count = sum(1 for s in model.slides for sh in s.shapes if sh.is_picture)
    assert picture_count == plan["images"]  # nothing silently skipped

    result, elapsed, peak = _measure(path)
    on_disk_mb = path.stat().st_size / 1024 / 1024
    print(f"[perf-10MB] on_disk={on_disk_mb:.2f}MB images={plan['images']} "
          f"slides={result.slide_count} elapsed={elapsed:.2f}s "
          f"tracemalloc_peak={peak / 1024 / 1024:.1f}MB")

    assert result.status == "ok"
    validate_output(result.to_dict())
    assert on_disk_mb >= 8.5  # within "10MB order of magnitude"
    assert result.slide_count == plan["slides"]
    assert elapsed < 180.0
    assert peak / 1024 / 1024 < 1200.0


def test_fifty_megabyte_media_deck(tmp_path):
    _require_gate()
    path = tmp_path / "media_50mb.pptx"
    plan = _build_media_deck(path, target_mb=50.0, max_images=700)

    model = build_model(path)
    picture_count = sum(1 for s in model.slides for sh in s.shapes if sh.is_picture)
    assert picture_count == plan["images"]

    result, elapsed, peak = _measure(path)
    on_disk_mb = path.stat().st_size / 1024 / 1024
    print(f"[perf-50MB] on_disk={on_disk_mb:.2f}MB images={plan['images']} "
          f"slides={result.slide_count} elapsed={elapsed:.2f}s "
          f"tracemalloc_peak={peak / 1024 / 1024:.1f}MB")

    assert result.status == "ok"
    validate_output(result.to_dict())
    # ~50MB order of magnitude; capped at 700 generated images for runtime safety
    assert on_disk_mb >= 25.0
    assert result.slide_count == plan["slides"]
    assert elapsed < 360.0
    assert peak / 1024 / 1024 < 2200.0
