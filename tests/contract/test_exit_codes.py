"""Process exit-code contract: 0 clean, 1 quality gate failed, 2 usage/unusable
input, 3 unexpected internal error. Matrix covers both the pure mapping
helper and the real CLI wiring plus the fail-on severity combinations."""

from __future__ import annotations

import pytest

import helpers_decks as decks
from layoutproof.cli import main
from layoutproof.models import (
    EXIT_CLEAN,
    EXIT_INTERNAL,
    EXIT_ISSUES,
    EXIT_USAGE,
    Issue,
    ScanResult,
    Severity,
    exit_code_for,
)


def _result(*rule_ids: str, status: str = "ok") -> ScanResult:
    return ScanResult(
        file_path="/x/y.pptx", file_name="y.pptx", status=status,
        error="broken" if status == "error" else None,
        issues=[Issue(rule_id=r, slide_index=0, slide_number=1) for r in rule_ids],
    )


# ---------------------------------------------------------------------------
# Pure helper matrix
# ---------------------------------------------------------------------------
def test_exit_code_mapping_matrix():
    clean = _result()
    warn = _result("low_contrast")
    info = _result("missing_alt_text")
    err = _result("offslide_object")
    err_and_warn = _result("offslide_object", "low_contrast")
    broken = _result(status="error")

    assert exit_code_for(clean, Severity.WARNING) == EXIT_CLEAN
    assert exit_code_for(warn, Severity.WARNING) == EXIT_ISSUES
    assert exit_code_for(warn, Severity.ERROR) == EXIT_CLEAN
    assert exit_code_for(err, Severity.WARNING) == EXIT_ISSUES
    assert exit_code_for(err, Severity.ERROR) == EXIT_ISSUES
    assert exit_code_for(info, Severity.WARNING) == EXIT_CLEAN
    assert exit_code_for(info, Severity.INFO) == EXIT_ISSUES
    assert exit_code_for(info, Severity.ERROR) == EXIT_CLEAN
    assert exit_code_for(err_and_warn, Severity.ERROR) == EXIT_ISSUES
    # an unreadable/aborted scan maps to usage code 2, never to "issues found"
    assert exit_code_for(broken, Severity.WARNING) == EXIT_USAGE


# ---------------------------------------------------------------------------
# Real CLI wiring
# ---------------------------------------------------------------------------
def test_clean_deck_exits_zero(tmp_path):
    p = decks.save_clean_deck(tmp_path / "clean.pptx")
    assert main(["scan", str(p)]) == EXIT_CLEAN


def test_warning_deck_exits_one_by_default_and_zero_with_fail_on_error(tmp_path):
    p = decks.save_warning_deck(tmp_path / "warn.pptx")
    assert main(["scan", str(p)]) == EXIT_ISSUES
    assert main(["scan", str(p), "--fail-on", "error"]) == EXIT_CLEAN


def test_error_deck_exits_one_even_with_fail_on_error(tmp_path):
    p = decks.save_error_deck(tmp_path / "err.pptx")
    assert main(["scan", str(p), "--fail-on", "error"]) == EXIT_ISSUES
    assert main(["scan", str(p)]) == EXIT_ISSUES


def test_info_only_deck_ignored_by_warning_but_flagged_by_fail_on_info(tmp_path):
    p = decks.save_info_deck(tmp_path / "info.pptx")
    assert main(["scan", str(p), "--profile", "full"]) == EXIT_CLEAN
    assert main(["scan", str(p), "--profile", "full",
                "--fail-on", "info"]) == EXIT_ISSUES


def test_missing_target_exits_usage(tmp_path):
    assert main(["scan", str(tmp_path / "missing.pptx")]) == EXIT_USAGE
    assert main([]) == EXIT_USAGE


def test_corrupt_archive_exits_usage_not_internal(tmp_path, capsys):
    bad = tmp_path / "corrupt.pptx"
    bad.write_bytes(b"PK\x03\x04 not a real central directory" * 4)
    assert main(["scan", str(bad)]) == EXIT_USAGE


def test_internal_exception_is_caught_and_maps_to_three(tmp_path, monkeypatch, capsys):
    import layoutproof.cli as cli_mod

    p = decks.save_clean_deck(tmp_path / "clean.pptx")

    def _boom(_args):
        raise RuntimeError("simulated internal failure")

    monkeypatch.setattr(cli_mod, "cmd_scan", _boom)
    code = main(["scan", str(p)])
    assert code == EXIT_INTERNAL
    assert "Internal error" in capsys.readouterr().err
