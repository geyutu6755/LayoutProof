"""One-shot rebuild of the PPTX corpus.

Usage (from the project root or anywhere):

    .venv/Scripts/python.exe test_fixtures/generators/build_all.py

This wipes ``test_fixtures/corpus/`` (all ``.pptx`` and ``manifest.json``),
re-runs every category generator, and writes a fresh ``manifest.json``.
"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORPUS = HERE.parent / "corpus"

sys.path.insert(0, str(HERE))

import clean          # noqa: E402
import broken         # noqa: E402
import chinese        # noqa: E402
import complex as complex_   # noqa: E402
import cross_renderer # noqa: E402

GENERATORS = [clean, broken, chinese, complex_, cross_renderer]


def wipe_corpus() -> None:
    if CORPUS.exists():
        for child in CORPUS.iterdir():
            if child.is_file():
                child.unlink()
            else:
                shutil.rmtree(child)
    else:
        CORPUS.mkdir(parents=True)


def main() -> int:
    wipe_corpus()
    records: list[dict] = []
    for gen in GENERATORS:
        print(f"[build] {gen.__name__}")
        records.extend(gen.build(CORPUS))

    manifest = {
        "schema_version": "1.0",
        "tool": "layoutproof-test-fixtures",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "categories": ["clean", "broken", "chinese", "complex", "cross-renderer"],
        "records": records,
    }
    out = CORPUS / "manifest.json"
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[build] wrote {out} ({len(records)} records)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
