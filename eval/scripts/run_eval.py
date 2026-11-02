"""Repeatable evaluation runner for LayoutProof.

Runs ``layoutproof.scan_file`` for every physical .pptx in the eval corpus
under both ``core`` and ``full`` profiles, matches actual findings against the
structured ground truth, and writes:

* ``results/core_metrics.json`` / ``results/full_metrics.json``
* ``results/distribution.json``        dataset distribution and counts
* ``results/timing.json``              per-profile per-file detection timing
* ``results/eval_report.md``           human-readable summary
* ``findings/observed_mismatches.json`` FP/FN/severity deviations for review

Confusion matrix rules
----------------------
* Existence level drives P/R/F1: a positive judgement counts TP when the rule
  fires >=1 time, otherwise FN; a negative judgement counts FP when it fires,
  otherwise TN.
* A judgement with ``expect=unknown`` (and files with ``expected_status=error``)
  are excluded from the matrix and listed under "cannot judge".
* Scope "both" applies to core and full; "core" only to core; "full" only full.
* No support is invented for rules a file does not mention.
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

EVAL_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = EVAL_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from layoutproof import scan_file  # noqa: E402
from layoutproof.rules import PROFILES  # noqa: E402

CORPUS = EVAL_ROOT / "corpus"
MANIFEST = CORPUS / "ground_truth" / "manifest.json"
RESULTS = EVAL_ROOT / "results"
FINDINGS = EVAL_ROOT / "findings"

ACTIVE = {
    "core": set(PROFILES["core"]),
    "full": set(PROFILES["full"]),
}


def scope_active(scope: str, profile: str) -> bool:
    if scope == "both":
        return True
    return scope == profile


def _f1(tp: int, fp: int, fn: int) -> dict:
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall + 1e-12)
    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": 0,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def run_profile(records: list[dict], profile: str) -> dict:
    per_rule = {r: {"tp": 0, "fp": 0, "fn": 0, "tn": 0,
                    "support_positive": 0, "support_negative": 0}
                for r in ACTIVE[profile]}
    per_file = []
    unknown_rows = []
    severity_mismatches = []
    mismatches = []
    timings = []
    error_files = []
    missing_files = []

    for rec in records:
        path = CORPUS / rec["file"]
        if not path.exists():
            missing_files.append(rec["file"])
            continue

        t0 = time.perf_counter_ns()
        result = scan_file(path, profile=profile)
        dt_ms = (time.perf_counter_ns() - t0) / 1e6
        timings.append(dt_ms)

        by_rule: dict[str, int] = defaultdict(int)
        severity_by_rule: dict[str, set] = defaultdict(set)
        for issue in result.issues:
            by_rule[issue.rule_id] += 1
            severity_by_rule[issue.rule_id].add(issue.severity.value)

        row = {
            "file": rec["file"],
            "content_id": rec["content_id"],
            "source": rec["source"],
            "status": result.status,
            "slide_count": result.slide_count,
            "detected_counts": dict(by_rule),
            "expected_positive": [],
            "expected_negative": [],
            "flags": [],
            "elapsed_ms": round(dt_ms, 3),
        }

        if result.status == "error":
            error_files.append({"file": rec["file"], "error": result.error,
                                 "expected_status": rec["expected_status"]})

        if rec["expected_status"] == "error":
            if result.status != "error":
                row["flags"].append("expected_error_but_scanned_ok")
                mismatches.append({"kind": "expected_status", "file": rec["file"],
                                   "detail": "expected status=error but scan_file returned ok"})
            # No judgement confusion for an unopenable package.
            for j in rec["judgements"]:
                unknown_rows.append({"file": rec["file"], "rule": j["rule_id"],
                                     "reason": "package could not be opened (status error)"})
            per_file.append(row)
            continue

        for j in rec["judgements"]:
            rule = j["rule_id"]
            if not scope_active(j["profiles"], profile):
                continue
            if j["expect"] == "unknown":
                unknown_rows.append({"file": rec["file"], "rule": rule,
                                     "reason": j.get("basis", ""), "note": j.get("note", "")})
                continue
            fired = by_rule.get(rule, 0) > 0
            if j["expect"] == "positive":
                row["expected_positive"].append(rule)
                per_rule[rule]["support_positive"] += 1
                if fired:
                    per_rule[rule]["tp"] += 1
                else:
                    per_rule[rule]["fn"] += 1
                    row["flags"].append(f"FN:{rule}")
                    mismatches.append({"kind": "FN", "file": rec["file"], "rule": rule,
                                        "expected": j["expect"], "detail": j.get("basis", "")})
                if j.get("expected_count"):
                    if by_rule.get(rule, 0) != j["expected_count"]:
                        row["flags"].append(
                            f"COUNT:{rule}={by_rule.get(rule,0)} expected={j['expected_count']}")
                # severity check
                if rule in severity_by_rule and j.get("expected_severity"):
                    if j["expected_severity"] not in severity_by_rule[rule]:
                        severity_mismatches.append({"file": rec["file"], "rule": rule,
                                                     "expected": j["expected_severity"],
                                                     "actual": sorted(severity_by_rule[rule])})
            elif j["expect"] == "negative":
                row["expected_negative"].append(rule)
                per_rule[rule]["support_negative"] += 1
                if fired:
                    per_rule[rule]["fp"] += 1
                    row["flags"].append(f"FP:{rule}")
                    mismatches.append({"kind": "FP", "file": rec["file"], "rule": rule,
                                       "expected": j["expect"], "detail": j.get("basis", ""),
                                       "note": j.get("note", "")})
                else:
                    per_rule[rule]["tn"] += 1

        per_file.append(row)

    # finalize per-rule metrics
    rule_metrics = {}
    micro_tp = micro_fp = micro_fn = 0
    macro_p, macro_r, macro_f = [], [], []
    for rule, counts in per_rule.items():
        m = _f1(counts["tp"], counts["fp"], counts["fn"])
        m["tn"] = counts["tn"]
        m["support_positive"] = counts["support_positive"]
        m["support_negative"] = counts["support_negative"]
        m["evaluated"] = counts["support_positive"] + counts["support_negative"] > 0
        rule_metrics[rule] = m
        micro_tp += counts["tp"]
        micro_fp += counts["fp"]
        micro_fn += counts["fn"]
        if m["evaluated"]:
            macro_p.append(m["precision"])
            macro_r.append(m["recall"])
            macro_f.append(m["f1"])

    micro = _f1(micro_tp, micro_fp, micro_fn)
    summary = {
        "profile": profile,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "files_total": len(records),
        "files_scanned_ok": sum(1 for f in per_file if f["status"] == "ok"),
        "files_scanned_error": len(error_files),
        "missing_files": missing_files,
        "micro": {k: micro[k] for k in ("tp", "fp", "fn", "precision", "recall", "f1")},
        "macro_average": {
            "n_rules_evaluated": len(macro_f),
            "precision": round(statistics.mean(macro_p), 4) if macro_p else 0.0,
            "recall": round(statistics.mean(macro_r), 4) if macro_r else 0.0,
            "f1": round(statistics.mean(macro_f), 4) if macro_f else 0.0,
        },
        "timing_ms": {
            "files": len(timings),
            "total": round(sum(timings), 3),
            "mean": round(statistics.mean(timings), 3) if timings else 0.0,
            "median": round(statistics.median(timings), 3) if timings else 0.0,
            "p90": round(sorted(timings)[int(0.9 * len(timings)) - 1], 3) if timings else 0.0,
            "max": round(max(timings), 3) if timings else 0.0,
        },
        "unknown_judgements": unknown_rows,
        "error_files": error_files,
        "severity_mismatches": severity_mismatches,
    }
    return {"summary": summary, "rule_metrics": rule_metrics,
            "per_file": per_file, "mismatches": mismatches}


def distribution(records: list[dict]) -> dict:
    by_source: dict[str, int] = defaultdict(int)
    by_lang: dict[str, int] = defaultdict(int)
    by_aspect: dict[str, int] = defaultdict(int)
    by_scenario: dict[str, int] = defaultdict(int)
    deriv = 0
    authored = set()
    for r in records:
        by_source[r["source"]] += 1
        by_lang[r["language"]] += 1
        by_aspect[r["aspect"]] += 1
        by_scenario[r["scenario"]] += 1
        if r.get("parent"):
            deriv += 1
        else:
            authored.add(r["content_id"])
    judge_pos = judge_neg = judge_unk = 0
    for r in records:
        for j in r["judgements"]:
            if j["expect"] == "positive":
                judge_pos += 1
            elif j["expect"] == "negative":
                judge_neg += 1
            else:
                judge_unk += 1
    return {
        "physical_files": len(records),
        "unique_authored_content_ids": len(authored),
        "derivative_files": deriv,
        "by_source": dict(sorted(by_source.items())),
        "by_language": dict(sorted(by_lang.items())),
        "by_aspect": dict(sorted(by_aspect.items())),
        "by_scenario": dict(sorted(by_scenario.items())),
        "judgement_records": {"positive": judge_pos, "negative": judge_neg,
                              "unknown_explicit": judge_unk},
    }


def render_markdown(core: dict, full: dict, dist: dict) -> str:
    lines = []
    lines.append("# LayoutProof eval report\n")
    lines.append(f"- physical files: **{dist['physical_files']}**; "
                 f"unique authored content ids: **{dist['unique_authored_content_ids']}**; "
                 f"derivative (LibreOffice resave) files: **{dist['derivative_files']}**")
    lines.append(f"- judge records: positive={dist['judgement_records']['positive']}, "
                 f"negative={dist['judgement_records']['negative']}, "
                 f"unknown={dist['judgement_records']['unknown_explicit']}")
    lines.append("\n## Distribution\n")
    lines.append("### by source")
    for k, v in dist["by_source"].items():
        lines.append(f"- {k}: {v}")
    lines.append("\n### by language / aspect")
    for label, d in (("language", dist["by_language"]), ("aspect", dist["by_aspect"])):
        lines.append(f"- {label}: " + ", ".join(f"{k}={v}" for k, v in d.items()))

    def profile_table(data: dict, name: str):
        lines.append(f"\n## {name} profile\n")
        s = data["summary"]
        lines.append(f"- micro TP/FP/FN: {s['micro']['tp']}/{s['micro']['fp']}/{s['micro']['fn']}; "
                     f"Precision={s['micro']['precision']}, Recall={s['micro']['recall']}, "
                     f"F1={s['micro']['f1']}")
        lines.append(f"- macro avg over {s['macro_average']['n_rules_evaluated']} evaluated rules: "
                     f"P={s['macro_average']['precision']}, R={s['macro_average']['recall']}, "
                     f"F1={s['macro_average']['f1']}")
        t = s["timing_ms"]
        lines.append(f"- timing: total {t['total']} ms; mean {t['mean']} ms; "
                     f"median {t['median']} ms; p90 {t['p90']} ms; max {t['max']} ms "
                     f"({t['files']} scans)")
        lines.append("\n| rule | TP | FP | FN | support+ | support- | Precision | Recall | F1 |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
        for rule, m in data["rule_metrics"].items():
            lines.append(
                f"| {rule} | {m['tp']} | {m['fp']} | {m['fn']} | "
                f"{m['support_positive']} | {m['support_negative']} | "
                f"{m['precision']} | {m['recall']} | {m['f1']} |")
        if s["error_files"]:
            lines.append("\n### status=error files (excluded from matrix)")
            for e in s["error_files"]:
                lines.append(f"- {e['file']}: {e['error']}")
        if s["unknown_judgements"]:
            lines.append("\n### cannot-judge scenarios (excluded from matrix)")
            for u in s["unknown_judgements"]:
                lines.append(f"- {u['file']} :: {u['rule']} :: {u.get('reason','')}")
        return lines

    lines = profile_table(core, "core")
    lines = profile_table(full, "full")

    lines.append("\n## Observed mismatches (FP/FN/count/severity)\n")
    all_mis = [("core", m) for m in core["mismatches"]] + [("full", m) for m in full["mismatches"]]
    if not all_mis:
        lines.append("None under current ground truth.")
    for profile, m in all_mis:
        lines.append(f"- [{profile}] {m['kind']} {m['file']} :: {m.get('rule','')} :: {m.get('detail','')}")
    lines.append("\nDetailed machine-readable mismatch list: findings/observed_mismatches.json")
    return "\n".join(lines) + "\n"


def main() -> int:
    if not MANIFEST.exists():
        print(f"manifest missing: {MANIFEST}")
        return 2
    raw = json.loads(MANIFEST.read_text(encoding="utf-8"))
    records = raw["records"] if isinstance(raw, dict) else raw
    RESULTS.mkdir(parents=True, exist_ok=True)
    FINDINGS.mkdir(parents=True, exist_ok=True)

    core = run_profile(records, "core")
    full = run_profile(records, "full")
    dist = distribution(records)

    timing_by_file = {}
    for row in core["per_file"]:
        timing_by_file[row["file"]] = {"core_ms": row["elapsed_ms"]}
    for row in full["per_file"]:
        timing_by_file.setdefault(row["file"], {})["full_ms"] = row["elapsed_ms"]

    (RESULTS / "core_metrics.json").write_text(
        json.dumps(core, ensure_ascii=False, indent=2), encoding="utf-8")
    (RESULTS / "full_metrics.json").write_text(
        json.dumps(full, ensure_ascii=False, indent=2), encoding="utf-8")
    (RESULTS / "distribution.json").write_text(
        json.dumps(dist, ensure_ascii=False, indent=2), encoding="utf-8")
    (RESULTS / "timing.json").write_text(json.dumps(
        {"core": core["summary"]["timing_ms"], "full": full["summary"]["timing_ms"],
         "per_file": [{"file": k, **v} for k, v in sorted(timing_by_file.items())]},
        ensure_ascii=False, indent=2), encoding="utf-8")
    combined_mis = {"core": core["mismatches"], "full": full["mismatches"],
                   "severity_mismatches": {
                       "core": core["summary"]["severity_mismatches"],
                       "full": full["summary"]["severity_mismatches"]}}
    (FINDINGS / "observed_mismatches.json").write_text(
        json.dumps(combined_mis, ensure_ascii=False, indent=2), encoding="utf-8")
    (RESULTS / "eval_report.md").write_text(
        render_markdown(core, full, dist), encoding="utf-8")

    print("physical files:", dist["physical_files"])
    for name, data in (("core", core), ("full", full)):
        print(name, "micro:", data["summary"]["micro"],
              "macro:", data["summary"]["macro_average"],
              "mismatches:", len(data["mismatches"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
