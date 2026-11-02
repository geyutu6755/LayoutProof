"""Byte-level fuzzing of real .pptx files.

Every mutation derives from a real shipped corpus deck or a real generated
deck; the contract under test is robustness, *not* a particular finding:

* ``scan_file`` must never raise out of the engine,
* the returned :class:`ScanResult` must carry a valid ``status`` and a
  schema-valid serialised payload even when the package is unusable,
* the CLI must map the result to one of 0/1/2 (internal crash code 3 must
  never appear on malformed input).
"""

from __future__ import annotations

import random

import pytest

import helpers_decks as decks
from layoutproof.cli import main
from layoutproof.engine import scan_file
from layoutproof.models import ScanResult
from layoutproof.report import validate_output


CORPUS = decks.corpus_files()
assert CORPUS, "test_fixtures/corpus must contain real decks for fuzzing"


def _mutations(data: bytes, seed: int) -> dict[str, bytes]:
    rng = random.Random(seed)
    out: dict[str, bytes] = {}
    if not data:
        out["empty"] = b""
        return out
    for ratio in (0.01, 0.1, 0.5, 0.9):
        out[f"truncated_{int(ratio * 100):02d}"] = data[: max(1, int(len(data) * ratio))]
    flipped = bytearray(data)
    for _ in range(max(1, len(data) // 50)):
        flipped[rng.randrange(len(flipped))] = rng.randrange(256)
    out["byte_flips"] = bytes(flipped)
    out["random_append"] = data + bytes(rng.randrange(256) for _ in range(64))
    out["random_prefix"] = bytes(rng.randrange(256) for _ in range(64)) + data
    out["random_binary"] = bytes(rng.randrange(256) for _ in range(min(2048, len(data))))
    out["zero_bytes"] = b"\x00" * min(4096, len(data))
    out["printable_garbage"] = ("not a zip at all " * 40).encode("ascii")
    return out


@pytest.fixture(params=CORPUS, ids=lambda p: p.name)
def real_deck_bytes(request) -> bytes:
    return request.param.read_bytes()


def test_real_deck_loads_clean_as_baseline(tmp_path, real_deck_bytes):
    src = tmp_path / "baseline.pptx"
    src.write_bytes(real_deck_bytes)
    result = scan_file(src, profile="full")
    assert isinstance(result, ScanResult)
    assert result.status in ("ok", "error")
    validate_output(result.to_dict())  # valid even if it degraded to error


def test_byte_mutations_never_crash_engine_or_cli(tmp_path, real_deck_bytes):
    for label, blob in _mutations(real_deck_bytes, seed=20261102).items():
        src = tmp_path / f"mut_{label}.pptx"
        src.write_bytes(blob)

        # Engine path: must return, never raise.
        result = scan_file(src, profile="full")
        assert isinstance(result, ScanResult), label
        assert result.status in ("ok", "error"), label
        assert isinstance(result.issues, list)
        payload = result.to_dict()
        validate_output(payload)  # schema contract holds on degraded output
        if result.status == "error":
            assert result.error, f"error status must carry a reason ({label})"

        # CLI path: valid process status codes only (0 clean, 1 issues, 2 usage/
        # unreadable). Code 3 (internal) signals an unhandled crash and is a bug.
        code = main(["scan", str(src), "--json"])
        assert code in (0, 1, 2), f"CLI returned {code} for {label}"


def test_generated_deck_byte_mutations(tmp_path):
    src = tmp_path / "gen.pptx"
    decks.save_clean_deck(src)
    blob = src.read_bytes()
    for label, mutated in _mutations(blob, seed=7).items():
        target = tmp_path / f"gen_{label}.pptx"
        target.write_bytes(mutated)
        result = scan_file(target, profile="core")
        assert result.status in ("ok", "error"), label
        validate_output(result.to_dict())
