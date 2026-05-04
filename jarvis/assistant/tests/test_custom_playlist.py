"""
Tests for core.custom_playlist.
"""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.custom_playlist import (  # noqa: E402
    CustomPlaylist, load_playlist, play_first,
)


# ── Helpers ──────────────────────────────────────────────────────────


def _write_pl(tmp: Path, body: str) -> Path:
    p = tmp / "playlist.yaml"
    p.write_text(body)
    return p


# ── Tests ─────────────────────────────────────────────────────────────


def test_load_basic_playlist():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        pl = load_playlist(_write_pl(tmp, """
songs:
  - youtube_search: "Tum Jiyo Hazaaron Saal"
  - youtube_search: "Baar Baar Din"
shuffle: false
loop: true
"""))
        assert pl.queries == ["Tum Jiyo Hazaaron Saal", "Baar Baar Din"]
        assert pl.shuffle is False
        assert pl.loop is True


def test_missing_file_returns_empty():
    with tempfile.TemporaryDirectory() as tmp_str:
        pl = load_playlist(Path(tmp_str) / "ghost.yaml")
        assert pl.is_empty
        assert pl.next_query() is None


def test_malformed_yaml_returns_empty():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        pl = load_playlist(_write_pl(tmp, "not a mapping at all"))
        assert pl.is_empty


def test_skip_entries_without_youtube_search():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        pl = load_playlist(_write_pl(tmp, """
songs:
  - youtube_search: "good entry"
  - some_other_key: "ignored"
  - youtube_search: ""
  - youtube_search: "another good one"
"""))
        assert pl.queries == ["good entry", "another good one"]


def test_in_order_iteration_with_loop():
    pl = CustomPlaylist(queries=["a", "b", "c"], shuffle=False, loop=True)
    assert pl.next_query() == "a"
    assert pl.next_query() == "b"
    assert pl.next_query() == "c"
    # loops back
    assert pl.next_query() == "a"
    assert pl.next_query() == "b"


def test_in_order_iteration_without_loop():
    pl = CustomPlaylist(queries=["a", "b"], shuffle=False, loop=False)
    assert pl.next_query() == "a"
    assert pl.next_query() == "b"
    # exhausted
    assert pl.next_query() is None
    assert pl.next_query() is None


def test_shuffle_visits_every_song_before_repeating():
    pl = CustomPlaylist(queries=["a", "b", "c"], shuffle=True, loop=True)
    first_pass = [pl.next_query() for _ in range(3)]
    assert sorted(first_pass) == ["a", "b", "c"]
    # second pass should also visit each once
    second_pass = [pl.next_query() for _ in range(3)]
    assert sorted(second_pass) == ["a", "b", "c"]


def test_shuffle_no_loop_terminates_after_pool():
    pl = CustomPlaylist(queries=["a", "b"], shuffle=True, loop=False)
    seen = [pl.next_query() for _ in range(2)]
    assert sorted(seen) == ["a", "b"]
    # Pool exhausted, no loop → None forever after.
    assert pl.next_query() is None


def test_reset_starts_over():
    pl = CustomPlaylist(queries=["a", "b"], shuffle=False, loop=False)
    pl.next_query()
    pl.next_query()
    assert pl.next_query() is None
    pl.reset()
    assert pl.next_query() == "a"


def test_play_first_no_provider_returns_none():
    pl = CustomPlaylist(queries=["a"])
    assert play_first(pl, music_provider=None) is None


def test_play_first_searches_and_plays():
    """play_first hands the first query to provider.search → provider.play."""
    pl = CustomPlaylist(queries=["Tum Hi Ho"])
    song = MagicMock(title="Tum Hi Ho")
    provider = MagicMock()
    provider.search = MagicMock(return_value=[song])
    provider.play = MagicMock(return_value=True)

    title = play_first(pl, music_provider=provider)
    assert title == "Tum Hi Ho"
    provider.search.assert_called_once_with("Tum Hi Ho", limit=1)
    provider.play.assert_called_once_with(song, video=False)


def test_play_first_handles_search_exception():
    pl = CustomPlaylist(queries=["Tum Hi Ho"])
    provider = MagicMock()
    provider.search = MagicMock(side_effect=RuntimeError("boom"))
    assert play_first(pl, music_provider=provider) is None


def test_play_first_handles_empty_search_results():
    pl = CustomPlaylist(queries=["Tum Hi Ho"])
    provider = MagicMock()
    provider.search = MagicMock(return_value=[])
    assert play_first(pl, music_provider=provider) is None


def test_play_first_returns_none_when_play_fails():
    pl = CustomPlaylist(queries=["Tum Hi Ho"])
    song = MagicMock(title="Tum Hi Ho")
    provider = MagicMock()
    provider.search = MagicMock(return_value=[song])
    provider.play = MagicMock(return_value=False)
    assert play_first(pl, music_provider=provider) is None


def test_real_pack_playlist_loads():
    """Smoke: the actual playlist file in events/ parses cleanly."""
    project_root = Path(__file__).resolve().parent.parent
    pl_path = project_root / "events" / "astha-birthday" / "media" / "songs" / "playlist.yaml"
    if not pl_path.is_file():
        # Skip if the seed file isn't there yet (CI-friendly).
        return
    pl = load_playlist(pl_path)
    assert not pl.is_empty
    assert all(q for q in pl.queries)


# ── Test runner integration ──────────────────────────────────────────


def _collect_tests():
    return [obj for name, obj in globals().items()
            if name.startswith("test_") and callable(obj)]


def run_custom_playlist_tests() -> dict:
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
    s = run_custom_playlist_tests()
    for r in s["tests"]:
        marker = "PASS" if r["passed"] else "FAIL"
        suffix = f": {r['detail']}" if r["detail"] else ""
        print(f"  [{marker}] {r['name']}{suffix}")
    print(f"\n{s['passed']}/{s['total']} custom_playlist tests passed.")
    return 0 if s["passed"] == s["total"] else 1


if __name__ == "__main__":
    sys.exit(main())
