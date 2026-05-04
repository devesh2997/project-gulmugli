"""Tests for core.voice_memos."""

from __future__ import annotations

import sys
import tempfile
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.voice_memos import (  # noqa: E402
    MemoContext, VoiceMemoLibrary, _parse_memo, play_memo,
)


# ── Helpers ──────────────────────────────────────────────────────────


def _write_bank(tmp: Path, body: str) -> Path:
    p = tmp / "memos.yaml"
    p.write_text(body)
    return p


# ── Tests ────────────────────────────────────────────────────────────


def test_load_basic_bank():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        lib = VoiceMemoLibrary(_write_bank(tmp, """
memos:
  - file: a.wav
    title: A
    tags: [default]
  - file: b.wav
    title: B
    tags: [sad]
"""))
        assert len(lib.list_all()) == 2


def test_pick_by_tag_returns_match():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        lib = VoiceMemoLibrary(_write_bank(tmp, """
memos:
  - file: a.wav
    title: A
    tags: [sad]
  - file: b.wav
    title: B
    tags: [happy]
"""))
        m = lib.pick_by_tag("sad")
        assert m is not None and m.file == "a.wav"
        m2 = lib.pick_by_tag("happy")
        assert m2 is not None and m2.file == "b.wav"


def test_pick_by_tag_no_match_returns_none():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        lib = VoiceMemoLibrary(_write_bank(tmp, """
memos:
  - file: a.wav
    title: A
    tags: [happy]
"""))
        assert lib.pick_by_tag("nonexistent") is None


def test_pick_by_tag_prefers_default():
    """Within a tag pool, memos tagged 'default' are preferred."""
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        lib = VoiceMemoLibrary(_write_bank(tmp, """
memos:
  - file: x.wav
    title: X
    tags: [birthday]
  - file: y.wav
    title: Y
    tags: [birthday, default]
"""))
        # 50 picks all return y.wav since it has the default tag.
        picks = {lib.pick_by_tag("birthday").file for _ in range(50)}
        assert picks == {"y.wav"}


def test_available_from_gates_playability():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        lib = VoiceMemoLibrary(_write_bank(tmp, """
memos:
  - file: future.wav
    title: Future
    tags: [birthday]
    available_from: "2026-05-14"
"""))
        # Before the date — silent.
        assert lib.pick_by_tag("birthday", today=date(2026, 5, 13)) is None
        # On the date — playable.
        m = lib.pick_by_tag("birthday", today=date(2026, 5, 14))
        assert m is not None
        # After the date — still playable.
        assert lib.pick_by_tag("birthday", today=date(2027, 1, 1)) is not None


def test_available_from_null_means_always():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        lib = VoiceMemoLibrary(_write_bank(tmp, """
memos:
  - file: any.wav
    title: A
    tags: [comfort]
    available_from: null
"""))
        # Any date — playable.
        for d in (date(2020, 1, 1), date(2099, 12, 31)):
            assert lib.pick_by_tag("comfort", today=d) is not None


def test_list_available_filters_by_date():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        lib = VoiceMemoLibrary(_write_bank(tmp, """
memos:
  - file: a.wav
    title: A
    tags: []
  - file: b.wav
    title: B
    tags: []
    available_from: "2026-12-31"
"""))
        avail_today = lib.list_available(today=date(2026, 5, 14))
        assert {m.file for m in avail_today} == {"a.wav"}


def test_pick_default_falls_back_to_random():
    """When no memo is tagged default, pick_default returns a random one."""
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        lib = VoiceMemoLibrary(_write_bank(tmp, """
memos:
  - file: a.wav
    title: A
    tags: [random_tag]
"""))
        m = lib.pick_default()
        assert m is not None and m.file == "a.wav"


def test_missing_bank_file_returns_empty():
    with tempfile.TemporaryDirectory() as tmp_str:
        lib = VoiceMemoLibrary(Path(tmp_str) / "ghost.yaml")
        assert lib.list_all() == []
        assert lib.pick_by_tag("anything") is None


def test_malformed_memo_skipped():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        # First memo missing `file` — skipped. Second loads.
        lib = VoiceMemoLibrary(_write_bank(tmp, """
memos:
  - title: missing file
  - file: ok.wav
    title: OK
    tags: []
"""))
        assert len(lib.list_all()) == 1
        assert lib.list_all()[0].file == "ok.wav"


def test_invalid_iso_date_treated_as_always_available():
    """Bad date string logs but doesn't crash; memo treated as always-available."""
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        lib = VoiceMemoLibrary(_write_bank(tmp, """
memos:
  - file: a.wav
    title: A
    tags: [x]
    available_from: "not-a-date"
"""))
        m = lib.pick_by_tag("x", today=date(2020, 1, 1))
        assert m is not None


def test_play_memo_with_missing_file_returns_false():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        from core.voice_memos import Memo
        memo = Memo(file="nope.wav", title="x", tags=())
        ctx = MemoContext(bank_dir=tmp)
        assert play_memo(memo, ctx) is False


def test_parse_memo_rejects_non_dict():
    try:
        _parse_memo("not a dict")
    except ValueError as e:
        assert "must be a dict" in str(e)
    else:
        raise AssertionError("expected ValueError")


# ── Test runner integration ──────────────────────────────────────────


def _collect_tests():
    return [obj for name, obj in globals().items()
            if name.startswith("test_") and callable(obj)]


def run_voice_memos_tests() -> dict:
    results = []
    total_latency = 0.0
    for t in _collect_tests():
        start = time.time()
        try:
            t()
            elapsed = time.time() - start
            total_latency += elapsed
            results.append({
                "name": t.__name__, "input": "", "passed": True,
                "latency": elapsed, "detail": "", "tier": "easy", "tags": [],
            })
        except AssertionError as e:
            elapsed = time.time() - start
            total_latency += elapsed
            results.append({
                "name": t.__name__, "input": "", "passed": False,
                "latency": elapsed, "detail": str(e),
                "tier": "easy", "tags": [],
            })
        except Exception as e:
            elapsed = time.time() - start
            total_latency += elapsed
            results.append({
                "name": t.__name__, "input": "", "passed": False,
                "latency": elapsed,
                "detail": f"{type(e).__name__}: {e}",
                "tier": "easy", "tags": [],
            })
    passed = sum(1 for r in results if r["passed"])
    return {
        "total": len(results), "passed": passed,
        "total_latency": total_latency, "tests": results,
    }


def main() -> int:
    s = run_voice_memos_tests()
    for r in s["tests"]:
        marker = "PASS" if r["passed"] else "FAIL"
        suffix = f": {r['detail']}" if r["detail"] else ""
        print(f"  [{marker}] {r['name']}{suffix}")
    print(f"\n{s['passed']}/{s['total']} voice_memos tests passed.")
    return 0 if s["passed"] == s["total"] else 1


if __name__ == "__main__":
    sys.exit(main())
