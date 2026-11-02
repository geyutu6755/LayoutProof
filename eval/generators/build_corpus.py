"""One-shot corpus builder: python-pptx files + PptxGenJS files + LibreOffice
resave bucket; emits the merged ground-truth manifest used by scripts/run_eval.py.

Repeatable: generated .pptx artifacts are refreshed from this script; the shared
project source tree (src/, tests/, ...) is never touched.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import gen_python  # noqa: E402
import convert_libreoffice  # noqa: E402

EVAL_ROOT = HERE.parent
CORPUS = EVAL_ROOT / "corpus"
MANIFEST = CORPUS / "ground_truth" / "manifest.json"
NODE = r"C:\Users\Lenovohqy\AppData\Local\Doubao\User Data\sandbox_runtime\bases\772984f6fd3a8ae0ae7d2422cd7c2bfa\node\node.exe"

BUCKET_DIRS = ["python_pptx", "pptxgenjs", "libreoffice"]


def purge_generated_pptx() -> None:
    for bucket in BUCKET_DIRS:
        d = CORPUS / bucket
        d.mkdir(parents=True, exist_ok=True)
        for old in d.glob("*.pptx"):
            old.unlink()


def strip_pptxgenjs_default_alt(path: Path) -> None:
    """pptxgenjs writes descr="preencoded.png" even when altText is omitted.
    Remove that default so the missing_alt_text positive sample is honest.
    """
    if not path.exists():
        return
    with zipfile.ZipFile(path, "r") as zin:
        names = zin.namelist()
        data = {n: zin.read(n) for n in names}
    slide_xml = "ppt/slides/slide1.xml"
    text = data[slide_xml].decode("utf-8")
    text = re.sub(r' descr="preencoded\.png"', "", text)
    data[slide_xml] = text.encode("utf-8")
    tmp = path.with_suffix(".tmp.pptx")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for n in names:
            zout.writestr(n, data[n])
    tmp.replace(path)


def run_node_generator() -> list[dict]:
    part = CORPUS / "pptxgenjs" / "manifest_part.json"
    node = NODE if Path(NODE).exists() else "node"
    proc = subprocess.run([node, str(HERE / "gen_pptxgenjs.js")],
                          capture_output=True, text=True, timeout=300,
                          encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(f"pptxgenjs generator failed:\n{proc.stderr}")
    strip_pptxgenjs_default_alt(CORPUS / "pptxgenjs" /
                                "j10_missing_alt_image_16x9.pptx")
    return json.loads(part.read_text(encoding="utf-8"))


def validate(records: list[dict]) -> list[str]:
    problems = []
    seen_files = set()
    for r in records:
        p = CORPUS / r["file"]
        if not p.exists():
            problems.append(f"missing file: {r['file']}")
        if r["file"] in seen_files:
            problems.append(f"duplicate output file: {r['file']}")
        seen_files.add(r["file"])
        for j in r.get("judgements", []):
            if j["expect"] not in ("positive", "negative", "unknown"):
                problems.append(f"{r['file']}: bad expect {j['expect']}")
    return problems


def main() -> int:
    purge_generated_pptx()
    python_records = gen_python.build_all(CORPUS)
    node_records = run_node_generator()
    authored = python_records + node_records
    lo_records = convert_libreoffice.convert_many(authored)
    records = authored + lo_records

    problems = validate(records)
    manifest = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "purpose": "LayoutProof offline quality-detection evaluation corpus",
        "judgement_legend": {
            "positive": "deliberate defect; rule expected to fire",
            "negative": "deliberately clean sample; rule expected to stay silent",
            "unknown": "cannot be judged offline; excluded from P/R/F1",
        },
        "profiles": {
            "core": ["offslide_object", "font_too_small", "text_overflow",
                     "unfinished_placeholder", "media_broken", "broken_reference",
                     "structure_anomaly"],
            "full": ["offslide_object", "font_too_small", "text_overflow",
                     "unfinished_placeholder", "media_broken", "broken_reference",
                     "structure_anomaly", "object_overlap", "low_contrast",
                     "blank_slide", "missing_alt_text", "cjk_typography"],
        },
        "records": records,
        "validation_problems": problems,
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                        encoding="utf-8")

    from collections import Counter
    src = Counter(r["source"] for r in records)
    print("total records:", len(records))
    print("by source:", dict(src))
    print("validation problems:", problems if problems else "none")
    print("manifest:", MANIFEST)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
