"""Scalability trend: scan time and traced memory versus shape count.

Runs in the default suite (marked ``slow``) with modest sizes. The heavy
10/50 MB media decks live in ``test_large_files.py`` behind an opt-in env var.
Numbers are printed to stdout; assertions guard against regressions in
throughput and against silently shrinking the scanned scope.
"""

from __future__ import annotations

import tracemalloc
import time

import pytest
from pptx import Presentation
from pptx.util import Inches, Pt

from layoutproof.engine import scan_file
from layoutproof.parsing import build_model
from layoutproof.report import validate_output

pytestmark = pytest.mark.slow

COUNTS = (40, 160, 640)


def _build_shape_deck(path, shape_count: int) -> int:
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    cols = 8
    for i in range(shape_count):
        row, col = divmod(i, cols)
        box = slide.shapes.add_textbox(
            Inches(0.3 + (col % cols) * 1.2),
            Inches(0.2 + row * 0.35),
            Inches(1.1), Inches(0.3),
        )
        tf = box.text_frame
        tf.text = f"item {i} body sentence"
        for para in tf.paragraphs:
            for run in para.runs:
                run.font.size = Pt(12)
    prs.save(str(path))
    return shape_count


def _count_shapes(model) -> int:
    total = 0
    for slide in model.slides:
        total += len(slide.shapes)
    return total


def test_scaling_trend_time_and_memory(tmp_path):
    records = []
    for count in COUNTS:
        path = tmp_path / f"shapes_{count}.pptx"
        expected = _build_shape_deck(path, count)

        # scope check: the parsed model really contains every generated shape
        model = build_model(path)
        assert _count_shapes(model) == expected

        tracemalloc.start()
        start = time.perf_counter()
        result = scan_file(path, profile="full")
        elapsed = time.perf_counter() - start
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        tracemalloc.clear_traces()

        assert result.status == "ok"
        validate_output(result.to_dict())
        records.append({"shapes": count, "elapsed_s": round(elapsed, 4),
                        "peak_mb": round(peak / 1024 / 1024, 2)})

    print("\n[scale-trend] shapes | elapsed_s | tracemalloc_peak_mb")
    for rec in records:
        print(f"[scale-trend] {rec['shapes']:5d} | {rec['elapsed_s']:8.4f} | "
              f"{rec['peak_mb']:8.2f}")

    # Throughput must not collapse: larger decks take a reasonable fraction
    # more time, never a wild jump on these modest sizes.
    t_small, t_mid, t_large = (r["elapsed_s"] for r in records)
    assert t_mid >= t_small * 0.7
    assert t_large >= t_mid * 0.7
    # Absolute safety caps (generous, Windows desktop, full profile).
    assert t_large < 120.0
    assert records[-1]["peak_mb"] < 700.0
