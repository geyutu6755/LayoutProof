"""LibreOffice headless resave: turns authored .pptx files into a distinct
"LibreOffice-saved" corpus bucket.  No rendering report is produced here; the
converted files simply represent a second real authoring/round-trip path and
are scanned offline like every other file.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from schema import J  # noqa: E402

EVAL_ROOT = HERE.parent
CORPUS = EVAL_ROOT / "corpus"
LO_OUT = CORPUS / "libreoffice"

SOFFICE = Path(r"E:\ai测试\LayoutProof\.rendertools\lo\program\soffice.com")

# Authored clean/negative files selected for the resave bucket.  Geometry-driven
# positives (offslide/overlap/overflow) are excluded because LO may reflow them.
SELECTED_CONTENT_IDS = [
    "p01", "p02", "p03", "p04", "p05", "p06", "p07",
    "p11", "p12", "p13", "p14",
    "j01", "j02", "j11",
]


def convert_many(records: list[dict]) -> list[dict]:
    if not SOFFICE.exists():
        print(f"WARN: soffice not found at {SOFFICE}; LO bucket skipped", file=sys.stderr)
        return []

    by_id = {r["content_id"]: r for r in records}
    jobs = []
    for cid in SELECTED_CONTENT_IDS:
        parent = by_id.get(cid)
        if parent is None or parent.get("expected_status") != "ok":
            continue
        src = CORPUS / parent["file"]
        if not src.exists():
            continue
        jobs.append((parent, src, f"lo_{src.stem}.pptx"))

    if not jobs:
        return []

    LO_OUT.mkdir(parents=True, exist_ok=True)
    args = [str(SOFFICE), "--headless", "--norestore", "--convert-to",
            "pptx:Impress MS PowerPoint 2007 XML", "--outdir", str(LO_OUT)]
    args.extend(str(src) for _, src, _ in jobs)
    proc = subprocess.run(args, capture_output=True, text=True, timeout=300,
                         encoding="utf-8", errors="replace",
                         creationflags=0x08000000)
    if proc.returncode != 0:
        print("soffice stderr:", proc.stderr[-2000:], file=sys.stderr)

    derivative_records = []
    for parent, src, out_name in jobs:
        produced = LO_OUT / src.name
        target = LO_OUT / out_name
        if produced.exists():
            if target.exists():
                target.unlink()
            shutil.move(str(produced), str(target))
        if not target.exists():
            derivative_records.append({
                **parent,
                "content_id": parent["content_id"] + "_lo",
                "file": f"libreoffice/{out_name}",
                "source": "libreoffice_resave",
                "parent": parent["file"],
                "scenario": parent["scenario"] + "_lo",
                "description": "LibreOffice 26.2 headless resave of "
                                f"{parent['file']}; GT negatives inherited, "
                                "any positive expectation downgraded to unknown.",
                "build_note": "Conversion produced no file; excluded from manifest.",
                "judgements": [],
                "expected_status": "skipped",
            })
            continue

        new_judgements = []
        for j in parent.get("judgements", []):
            item = dict(j)
            if j["expect"] == "positive":
                item["expect"] = "unknown"
                item["basis"] = "LO may rewrite geometry/relationships; not asserted offline"
                item["note"] = "downgraded from positive during resave"
            new_judgements.append(item)
        # Geometry/background heuristics depend on renderer layout; mark them unknown
        # on every derivative so the confusion matrix only uses asserted samples.
        existing = {j["rule_id"] for j in new_judgements}
        for rule, scope in (
            ("offslide_object", "both"),
            ("text_overflow", "both"),
            ("object_overlap", "full"),
            ("low_contrast", "full"),
        ):
            if rule not in existing:
                new_judgements.append(J(
                    rule, "unknown",
                    "LO round-trip may rewrite coordinates, fonts and background; "
                    "geometry heuristic not asserted offline",
                    "renderer-dependent; excluded from confusion matrix",
                    profiles=scope))
        derivative_records.append({
            **parent,
            "content_id": parent["content_id"] + "_lo",
            "file": f"libreoffice/{out_name}",
            "source": "libreoffice_resave",
            "parent": parent["file"],
            "scenario": parent["scenario"] + "_lo",
            "description": "LibreOffice 26.2 headless resave of "
                            f"{parent['file']}.",
            "build_note": "Round-trip artifact; negative GT inherited from authored source.",
            "judgements": new_judgements,
        })
    return derivative_records
