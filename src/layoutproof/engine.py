"""High-level scanning engine tying parsing and rules together."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .config import QualityConfig
from .models import Issue, RuleId, ScanResult
from .parsing import PackageError, build_model
from .rules import run_rules


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def scan_file(
    path: str | Path,
    config: QualityConfig | None = None,
    profile: str = "core",
) -> ScanResult:
    config = config or QualityConfig()
    p = Path(path)
    try:
        model = build_model(p, config)
    except PackageError as exc:
        return ScanResult(
            file_path=str(p.resolve()),
            file_name=p.name,
            status="error",
            error=str(exc),
            timestamp=_utc_now(),
            config=config.to_dict(),
        )
    except Exception as exc:  # defensive: never crash the CLI on a bad deck
        return ScanResult(
            file_path=str(p.resolve()),
            file_name=p.name,
            status="error",
            error=f"Unexpected parsing failure: {exc}",
            timestamp=_utc_now(),
            config=config.to_dict(),
        )

    issues = list(run_rules(model, config, profile))

    # Surface package-level structural anomalies as deterministic issues.
    if config.is_rule_enabled(RuleId.STRUCTURE_ANOMALY.value):
        for anomaly in model.anomalies:
            issues.append(
                Issue(
                    rule_id=RuleId.STRUCTURE_ANOMALY.value,
                    slide_index=-1,
                    slide_number=0,
                    detail=anomaly,
                    confidence=1.0,
                    evidence={"source": "package"},
                )
            )

    issues.sort(key=lambda i: (i.slide_index, i.shape_id or "", i.rule_id))
    result = ScanResult(
        file_path=str(p.resolve()),
        file_name=p.name,
        slide_count=len(model.slides),
        slide_width=model.width,
        slide_height=model.height,
        issues=issues,
        status="ok",
        timestamp=_utc_now(),
        config=config.to_dict(),
    )
    return result
