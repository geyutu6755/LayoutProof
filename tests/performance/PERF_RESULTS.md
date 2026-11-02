# Performance measurement record (Windows, local offline run)

Recorded on 2026-11-02 with the project virtualenv interpreter
`.venv\Scripts\python.exe`, full rule profile, no network access.

- Time: `time.perf_counter()` around `scan_file(path, profile="full")`.
- Memory: `tracemalloc` peak Python allocation inside the same scan call.
  Native/decoder heap (e.g. libjpeg) is not fully captured by tracemalloc, so
  the number should be read as an upper-style Python-allocator bound, not a
  complete RSS figure.
- Every scan also reloads the model with `build_model` and asserts the parsed
  shape/picture count equals the generated count, so measurements cannot cheat
  by skipping rules or parts of the deck.

## Shape-count trend (default suite, `@pytest.mark.slow`)

| shapes on one slide | elapsed (s) | tracemalloc peak (MB) |
|---:|---:|---:|
| 40  | 0.3671 | 0.64 |
| 160 | 0.6865 | 0.76 |
| 640 | 4.2171 | 1.87 |

Assertions: larger decks do not collapse in throughput; 640 shapes finish in
under 120 s and under 700 MB traced allocation.

## Real media decks (opt-in: `set LAYOUTPROOF_PERF=1`)

Run command:

```powershell
$env:LAYOUTPROOF_PERF="1"
.venv\Scripts\python.exe -m pytest tests/performance/test_large_files.py -s
```

| target | on-disk size | embedded pictures | slides | elapsed (s) | tracemalloc peak (MB) |
|---|---:|---:|---:|---:|---:|
| ~10 MB | 9.94 MB | 90  | 8  | 0.88 | 21.4 |
| ~50 MB | 49.50 MB | 449 | 38 | 3.21 | 102.9 |

Assertions enforced by the tests: scanned slide/picture counts match the build
plan, payload validates `report/schema.json`, on-disk size reaches its order of
magnitude, elapsed stays under 180 s (10 MB) / 360 s (50 MB), and traced peak
stays under 1200 MB / 2200 MB.

## Platform note

These measurements were taken on Windows. The detection code is pure Python
and offline, but the absolute timings/memory were **not** measured on
Linux/macOS; do not copy the numeric caps as cross-platform guarantees.
