"""
Tests for core.intro_runner.

Strategy: write a YAML script to a temp file with all four step types,
mock voice_router and face_ui, run it, and verify each handler was
called with the expected args. Audio playback is patched at the
audio_playback module boundary so we don't actually shell out.

Coverage:
  - Happy path: all 4 step types execute in order
  - Missing audio file: skipped with a logged warning, sequence continues
  - Unknown step type: logged + skipped, sequence continues
  - Malformed YAML: returns IntroResult with the parse error captured
  - Missing voice_router / face_ui: speak / dashboard_event no-op gracefully
  - Cancellation: cancel() between steps stops the rest
  - Template vars: {{ event_name }} substitution in `speak` text
  - dashboard_hint converts to a dashboard_event under the hood
  - Step handler raising an exception is caught (no crash)
"""

from __future__ import annotations

import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock

# Make the assistant package importable when run directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.intro_runner import IntroContext, IntroResult, IntroRunner  # noqa: E402


# ── Fixture helpers ──────────────────────────────────────────────────


def _write_script(tmp: Path, body: str) -> Path:
    p = tmp / "intro.yaml"
    p.write_text(body)
    return p


def _make_ctx(tmp: Path, **overrides) -> IntroContext:
    base = {
        "pack_dir": tmp,
        "voice_router": MagicMock(name="voice_router"),
        "face_ui": MagicMock(name="face_ui"),
        "music_provider": MagicMock(name="music_provider"),
        "template_vars": {},
    }
    base.update(overrides)
    return IntroContext(**base)


# ── Patches ─────────────────────────────────────────────────────────


def _patch_play_file(monkey_calls: list[tuple]):
    """
    Replace core.audio_playback.play_file with a stub that records calls
    and returns True. We patch BOTH the original and the imported alias
    used by intro_runner.
    """
    import core.intro_runner as ir
    import core.audio_playback as ap

    def stub(path, *, blocking=True, timeout_s=120.0):
        monkey_calls.append((str(path), blocking))
        return True

    ap.play_file = stub
    ir.play_file = stub


# ── Test cases ────────────────────────────────────────────────────────


def test_happy_path_all_step_types():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        # Create a real (empty) audio file so play_audio doesn't skip.
        audio = tmp / "intro.wav"
        audio.write_bytes(b"\x00" * 16)

        script = _write_script(tmp, f"""
- step: play_audio
  source: intro.wav
  wait_for_completion: true

- step: dashboard_event
  event: confetti_burst
  payload:
    pieces: 100

- step: speak
  personality: jarvis
  text: "Hi {{{{ event_name }}}}!"

- step: dashboard_hint
  text: "Try this command"
  duration_s: 5
""")
        play_calls: list[tuple] = []
        _patch_play_file(play_calls)

        ctx = _make_ctx(tmp, template_vars={"event_name": "Astha's Birthday"})
        runner = IntroRunner(script)
        result = runner.run(ctx)

        assert result.total_steps == 4
        assert result.completed == 4
        assert result.failures == []
        assert not result.cancelled

        # play_audio was called once on the right file.
        assert len(play_calls) == 1
        assert "intro.wav" in play_calls[0][0]

        # face_ui got TWO broadcasts: confetti_burst + intro_hint (from dashboard_hint).
        broadcast = ctx.face_ui.broadcast
        assert broadcast.call_count == 2
        first_call = broadcast.call_args_list[0]
        assert first_call.args[0] == "confetti_burst"
        assert first_call.args[1] == {"pieces": 100}
        second_call = broadcast.call_args_list[1]
        assert second_call.args[0] == "intro_hint"
        assert second_call.args[1]["text"] == "Try this command"
        assert second_call.args[1]["duration_s"] == 5.0

        # voice_router.say was called once with the rendered template.
        say = ctx.voice_router.say
        assert say.call_count == 1
        rendered_text = say.call_args.args[0]
        assert rendered_text == "Hi Astha's Birthday!"


def test_missing_audio_file_skipped_continues():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        script = _write_script(tmp, """
- step: play_audio
  source: does_not_exist.wav

- step: dashboard_event
  event: still_works
""")
        play_calls: list[tuple] = []
        _patch_play_file(play_calls)

        ctx = _make_ctx(tmp)
        result = IntroRunner(script).run(ctx)

        # Both steps "completed" — play_audio's missing-file is a logged
        # warning, not a failure, because it's the most common case during
        # development before recording is done.
        assert result.completed == 2
        assert result.failures == []
        # The play stub was not called (file missing → early return).
        assert play_calls == []
        # The next step still ran.
        assert ctx.face_ui.broadcast.call_count == 1


def test_unknown_step_type_logged_and_skipped():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        script = _write_script(tmp, """
- step: this_does_not_exist
- step: dashboard_event
  event: ok
""")
        ctx = _make_ctx(tmp)
        result = IntroRunner(script).run(ctx)

        assert result.total_steps == 2
        assert result.completed == 1
        assert len(result.failures) == 1
        assert "unknown step type" in result.failures[0]


def test_malformed_yaml_returns_failure():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        script = _write_script(tmp, "this is: not a list\n  it: is a mapping\n")
        ctx = _make_ctx(tmp)
        result = IntroRunner(script).run(ctx)
        assert result.total_steps == 0
        assert result.completed == 0
        assert len(result.failures) == 1


def test_missing_script_file_returns_failure():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        result = IntroRunner(tmp / "ghost.yaml").run(_make_ctx(tmp))
        assert result.total_steps == 0
        assert result.completed == 0
        assert len(result.failures) == 1


def test_no_voice_router_speak_steps_noop():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        script = _write_script(tmp, """
- step: speak
  personality: jarvis
  text: "Hello"
- step: dashboard_event
  event: still_works
""")
        ctx = _make_ctx(tmp, voice_router=None)
        result = IntroRunner(script).run(ctx)
        assert result.completed == 2
        assert result.failures == []
        # The dashboard step still executed.
        assert ctx.face_ui.broadcast.call_count == 1


def test_no_face_ui_dashboard_steps_noop():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        script = _write_script(tmp, """
- step: dashboard_event
  event: confetti
- step: dashboard_hint
  text: hi
- step: speak
  personality: jarvis
  text: still_works
""")
        ctx = _make_ctx(tmp, face_ui=None)
        result = IntroRunner(script).run(ctx)
        assert result.completed == 3
        assert result.failures == []
        assert ctx.voice_router.say.call_count == 1


def test_cancel_stops_remaining_steps():
    """
    Build a script with a sleep-style step (we'll use play_audio with a
    small sleep injected via the play_file stub) and cancel mid-way.
    """
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        audio = tmp / "long.wav"
        audio.write_bytes(b"\x00" * 16)
        script = _write_script(tmp, """
- step: dashboard_event
  event: a
- step: play_audio
  source: long.wav
- step: dashboard_event
  event: b_should_not_run
""")

        runner = IntroRunner(script)

        # The play_file stub will call cancel() during step 2.
        import core.audio_playback as ap
        import core.intro_runner as ir

        def cancelling_stub(path, *, blocking=True, timeout_s=120.0):
            runner.cancel()
            return True

        ap.play_file = cancelling_stub
        ir.play_file = cancelling_stub

        ctx = _make_ctx(tmp)
        result = runner.run(ctx)

        # First two steps ran (dashboard_event + play_audio); cancellation
        # check happens at the TOP of each iteration, so step 3 was skipped.
        assert result.completed == 2
        assert result.cancelled is True
        # face_ui only received the first event — not "b_should_not_run".
        events = [c.args[0] for c in ctx.face_ui.broadcast.call_args_list]
        assert events == ["a"]


def test_step_handler_exception_caught():
    """
    A buggy step (e.g., dashboard_event with no `event` field) raises
    inside the handler; the runner must catch + log + continue.
    """
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        script = _write_script(tmp, """
- step: dashboard_event
  # missing `event`
- step: dashboard_event
  event: this_one_is_fine
""")
        ctx = _make_ctx(tmp)
        result = IntroRunner(script).run(ctx)
        assert result.total_steps == 2
        assert result.completed == 1
        assert len(result.failures) == 1
        assert "missing `event`" in result.failures[0]


def test_template_substitution_handles_missing_keys():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        script = _write_script(tmp, """
- step: speak
  personality: jarvis
  text: "Hi {{ name }}, welcome to {{ unknown }}"
""")
        ctx = _make_ctx(tmp, template_vars={"name": "Astha"})
        result = IntroRunner(script).run(ctx)
        assert result.completed == 1
        rendered = ctx.voice_router.say.call_args.args[0]
        # `name` substituted, `unknown` left as-is so a dev sees the hole.
        assert "Astha" in rendered
        assert "{{ unknown }}" in rendered


def test_start_playlist_calls_play_first():
    """start_playlist loads the YAML and feeds the first query to music_provider."""
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        # Drop a playlist file the runner can resolve relative to pack_dir.
        (tmp / "playlist.yaml").write_text("""
songs:
  - youtube_search: "test song"
shuffle: false
loop: false
""")
        script = _write_script(tmp, """
- step: start_playlist
  path: playlist.yaml
""")
        # Mock the music provider; play_first will call .search and .play.
        from unittest.mock import MagicMock
        mp = MagicMock()
        mp.search = MagicMock(return_value=[MagicMock(title="test song")])
        mp.play = MagicMock(return_value=True)

        ctx = _make_ctx(tmp, music_provider=mp)
        result = IntroRunner(script).run(ctx)
        assert result.completed == 1
        assert result.failures == []
        mp.search.assert_called_once_with("test song", limit=1)
        assert mp.play.call_count == 1


def test_start_playlist_no_music_provider_noop():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        (tmp / "playlist.yaml").write_text("""
songs:
  - youtube_search: "x"
""")
        script = _write_script(tmp, """
- step: start_playlist
  path: playlist.yaml
""")
        ctx = _make_ctx(tmp, music_provider=None)
        result = IntroRunner(script).run(ctx)
        assert result.completed == 1
        assert result.failures == []


def test_start_playlist_missing_file_noop():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        script = _write_script(tmp, """
- step: start_playlist
  path: ghost.yaml
""")
        from unittest.mock import MagicMock
        mp = MagicMock()
        ctx = _make_ctx(tmp, music_provider=mp)
        result = IntroRunner(script).run(ctx)
        # Step "completed" because empty playlist is a logged no-op, not a failure.
        assert result.completed == 1
        assert result.failures == []
        # Provider should NOT have been touched.
        mp.search.assert_not_called()


def test_dashboard_hint_routes_through_dashboard_event():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        script = _write_script(tmp, """
- step: dashboard_hint
  text: "Try saying X"
  duration_s: 7
""")
        ctx = _make_ctx(tmp)
        result = IntroRunner(script).run(ctx)
        assert result.completed == 1
        # The hint became an `intro_hint` dashboard_event.
        broadcast = ctx.face_ui.broadcast
        assert broadcast.call_count == 1
        ev_name, payload = broadcast.call_args.args
        assert ev_name == "intro_hint"
        assert payload["text"] == "Try saying X"
        assert payload["duration_s"] == 7.0


# ── Test runner integration ──────────────────────────────────────────


def _collect_tests():
    return [obj for name, obj in globals().items()
            if name.startswith("test_") and callable(obj)]


def run_intro_runner_tests() -> dict:
    """Suite-runner entry point — same shape as the other test modules."""
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
    s = run_intro_runner_tests()
    for r in s["tests"]:
        marker = "PASS" if r["passed"] else "FAIL"
        suffix = f": {r['detail']}" if r["detail"] else ""
        print(f"  [{marker}] {r['name']}{suffix}")
    print(f"\n{s['passed']}/{s['total']} intro_runner tests passed.")
    return 0 if s["passed"] == s["total"] else 1


if __name__ == "__main__":
    sys.exit(main())
