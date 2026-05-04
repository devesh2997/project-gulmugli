"""
Intro Runner — executes the launch-sequence script for an event pack.

## Why this exists

When an event triggers (manual phrase, app button, or auto-midnight),
something needs to *do* the multi-step orchestration:
  1. Play your recorded intro audio
  2. Push a confetti event to the dashboard
  3. Have Vesper speak a follow-up line
  4. Show an on-screen hint
  5. Speak again
  ... etc.

That orchestration is the launch-sequence script. The script itself is
a YAML file living next to each event pack
(`events/<pack>/first_year/intro_script.yaml`). This module reads that
YAML and executes the steps in order.

## Step types

Each step is a dict with a `step` field naming its type. The runner
calls `_run_<type>(step, ctx)` to execute it.

  play_audio
    source: <path relative to pack dir, or absolute>
    wait_for_completion: <bool>   default true

  dashboard_event
    event: <event name string>     pushed to the dashboard via WS
    payload: <object, optional>    arbitrary JSON forwarded along

  speak
    personality: <profile id>      whose voice to use
    text: <string>                 may contain {{ template }} vars

  dashboard_hint
    text: <string>                 toast shown to the user
    duration_s: <number>           how long it stays visible

## Failure handling — be conservative, never crash

Every step is best-effort. If audio is missing, TTS is unavailable, or
the dashboard's WS broadcaster is down, the runner LOGS and continues
to the next step. The contract: **the launch sequence will never crash
the assistant.** Worst case: a few steps no-op and the user sees less,
but the system stays alive.

## Why a state machine, not a simple for-loop

Two reasons:
  1. We want each step to be cancellable. If the user (or you, mid-bug)
     wants to abort, `runner.cancel()` should stop the next step.
  2. Some steps (play_audio with `wait_for_completion: false`) are
     async — the runner needs to track which background processes are
     still running so it can wait on them at the end OR clean them up
     on cancel.

For Phase 1.1 we keep this simple: synchronous-only execution, with a
cancel flag the loop checks between steps. Async-step support can be
added later without breaking the YAML schema.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import yaml

from core.audio_playback import play_file
from core.logger import get_logger

log = get_logger("intro_runner")


# ── Public types ──────────────────────────────────────────────────────


@dataclass
class IntroContext:
    """
    Runtime context handed to each step handler.

    Holds everything a step might need to "reach out" — TTS, dashboard
    pusher, template variables. Built by the caller (typically
    `_handle_event_trigger` in core/intent_handler.py) and passed once.
    """

    pack_dir: Path
    """Resolves relative `source` / file paths in script steps."""

    voice_router: Optional[Any] = None
    """Used by `speak` steps. None = speak steps no-op gracefully."""

    face_ui: Optional[Any] = None
    """Used by `dashboard_event` and `dashboard_hint`. None = no-op."""

    music_provider: Optional[Any] = None
    """Used by `start_playlist` steps. None = playlist steps no-op."""

    template_vars: Dict[str, str] = field(default_factory=dict)
    """{{ keys }} substituted in `speak` text and `dashboard_hint` text."""


@dataclass
class IntroResult:
    """Summary of an intro run — what executed, what failed."""

    total_steps: int
    completed: int
    cancelled: bool
    failures: list[str]   # human-readable reasons, one per failed step

    @property
    def all_succeeded(self) -> bool:
        return self.completed == self.total_steps and not self.failures


# ── IntroRunner ───────────────────────────────────────────────────────


class IntroRunner:
    """
    Loads + executes a single intro script. Single-use — construct one
    per launch. Thread-safe cancel via `cancel()` from another thread.

    Typical use:

        runner = IntroRunner(pack_dir / "first_year/intro_script.yaml")
        ctx = IntroContext(pack_dir=pack_dir, voice_router=vr, face_ui=fu)
        result = runner.run(ctx)
        if not result.all_succeeded:
            log.warning("intro had %d failures", len(result.failures))
    """

    def __init__(self, script_path: Path):
        self._script_path = Path(script_path)
        self._cancel = threading.Event()
        # Step handlers — keyed by `step:` field in the YAML. Adding a
        # new step type = add a key here and the matching method.
        self._handlers: Dict[str, Callable[[Dict[str, Any], IntroContext], None]] = {
            "play_audio":      self._run_play_audio,
            "dashboard_event": self._run_dashboard_event,
            "speak":           self._run_speak,
            "dashboard_hint":  self._run_dashboard_hint,
            "start_playlist":  self._run_start_playlist,
        }

    # ── Public API ─────────────────────────────────────────────────

    def run(self, ctx: IntroContext) -> IntroResult:
        """
        Load + execute the script. Returns a summary; never raises.

        Failures inside individual steps are caught, logged, and counted
        in `failures` — they do NOT abort the rest of the script.
        Only a `cancel()` call OR a malformed script aborts.
        """
        steps = self._load_steps()
        if steps is None:
            return IntroResult(
                total_steps=0, completed=0, cancelled=False,
                failures=[f"could not load script {self._script_path}"],
            )

        log.info("intro_runner: %d steps from %s", len(steps), self._script_path.name)

        completed = 0
        failures: list[str] = []

        for i, step in enumerate(steps, start=1):
            if self._cancel.is_set():
                log.info("intro_runner: cancelled at step %d/%d", i, len(steps))
                return IntroResult(
                    total_steps=len(steps), completed=completed,
                    cancelled=True, failures=failures,
                )

            step_type = step.get("step") if isinstance(step, dict) else None
            if not isinstance(step_type, str):
                msg = f"step {i}: missing or non-string `step:` field"
                log.warning("intro_runner: %s — skipping", msg)
                failures.append(msg)
                continue

            handler = self._handlers.get(step_type)
            if handler is None:
                msg = f"step {i}: unknown step type {step_type!r}"
                log.warning("intro_runner: %s — skipping", msg)
                failures.append(msg)
                continue

            try:
                handler(step, ctx)
                completed += 1
            except Exception as e:
                # Defensive: even a step handler exception MUST NOT
                # propagate. The script is "best effort," not "all or
                # nothing."
                msg = f"step {i} ({step_type}): {type(e).__name__}: {e}"
                log.warning("intro_runner: %s", msg)
                failures.append(msg)

        return IntroResult(
            total_steps=len(steps), completed=completed,
            cancelled=False, failures=failures,
        )

    def cancel(self) -> None:
        """Request abort. Effective at the next step boundary."""
        self._cancel.set()

    # ── Loading ────────────────────────────────────────────────────

    def _load_steps(self) -> Optional[list]:
        """Parse the YAML. Returns None if the file is unusable."""
        if not self._script_path.is_file():
            log.warning("intro_runner: script not found: %s", self._script_path)
            return None
        try:
            with self._script_path.open() as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            log.warning("intro_runner: YAML parse error in %s: %s",
                        self._script_path, e)
            return None
        if not isinstance(data, list):
            log.warning(
                "intro_runner: %s must be a list of steps, got %s",
                self._script_path, type(data).__name__,
            )
            return None
        return data

    # ── Step handlers ──────────────────────────────────────────────

    def _resolve_path(self, source: str, ctx: IntroContext) -> Path:
        """Relative paths are relative to the pack dir; absolute pass through."""
        p = Path(source)
        return p if p.is_absolute() else (ctx.pack_dir / p)

    def _run_play_audio(self, step: Dict[str, Any], ctx: IntroContext) -> None:
        """Play a WAV/MP3. Defaults to blocking (waits for clip to end)."""
        source = step.get("source")
        if not isinstance(source, str) or not source:
            raise ValueError("play_audio: missing `source` field")
        path = self._resolve_path(source, ctx)
        wait = bool(step.get("wait_for_completion", True))
        # Don't raise if the file is missing — log and move on. Recording
        # may not have happened yet (Phase 7.1 records the intro).
        if not path.is_file():
            log.warning("intro_runner: play_audio source missing: %s — skipping",
                        path)
            return
        ok = play_file(path, blocking=wait)
        if not ok:
            # play_file already logged. Don't raise — keep the script alive.
            log.warning("intro_runner: play_audio failed for %s", path.name)

    def _run_dashboard_event(self, step: Dict[str, Any], ctx: IntroContext) -> None:
        """Push a typed event to the dashboard via the FaceUI broadcaster."""
        event_name = step.get("event")
        if not isinstance(event_name, str) or not event_name:
            raise ValueError("dashboard_event: missing `event` field")
        payload = step.get("payload") or {}
        if ctx.face_ui is None:
            log.info("intro_runner: dashboard_event %s — face_ui unavailable, skipping",
                     event_name)
            return
        # The FaceUI's broadcaster API is `broadcast(event_name, payload)`
        # in current design. If it's not present, fall back to a more
        # generic `send` method, then no-op. We don't want this module to
        # break if the FaceUI interface evolves.
        broadcast = (
            getattr(ctx.face_ui, "broadcast", None)
            or getattr(ctx.face_ui, "send", None)
        )
        if broadcast is None:
            log.info(
                "intro_runner: dashboard_event %s — face_ui has no broadcast/send method, skipping",
                event_name,
            )
            return
        try:
            broadcast(event_name, payload)
        except TypeError:
            # Some FaceUI variants expect a single dict arg.
            broadcast({"event": event_name, "payload": payload})

    def _run_speak(self, step: Dict[str, Any], ctx: IntroContext) -> None:
        """Synthesize text and play it through a personality voice."""
        text = step.get("text")
        personality_id = step.get("personality")
        if not isinstance(text, str) or not text:
            raise ValueError("speak: missing `text` field")
        text = self._render_template(text, ctx.template_vars)

        if ctx.voice_router is None:
            log.info("intro_runner: speak — voice_router unavailable, skipping")
            return

        # Look up the personality object the voice_router wants. Optional:
        # if the personality id isn't found, voice_router falls back to
        # the active personality.
        from core.personality import personality_manager
        personality = None
        if isinstance(personality_id, str) and personality_id:
            try:
                personality = personality_manager.get(personality_id)
            except Exception:
                personality = None
        if personality is None:
            personality = personality_manager.active

        # voice_router.speak returns WAV bytes — but we want to actually
        # PLAY them. The router's normal flow goes through the streaming
        # pipeline; here we want a one-shot. Most voice routers expose
        # `say(text, personality)` for blocking synthesis + playback.
        # Fall back gracefully if not present.
        say = getattr(ctx.voice_router, "say", None)
        if callable(say):
            say(text, personality)
            return
        # Older path: synthesize WAV bytes, write to temp file, play.
        speak = getattr(ctx.voice_router, "speak", None)
        if callable(speak):
            wav = speak(text, personality)
            if wav:
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    f.write(wav)
                    tmp = f.name
                play_file(tmp, blocking=True)
                # Best-effort cleanup; OS will sweep /tmp eventually if we miss.
                try:
                    Path(tmp).unlink(missing_ok=True)
                except Exception:
                    pass
            return
        log.info("intro_runner: speak — voice_router has neither .say nor .speak, skipping")

    def _run_dashboard_hint(self, step: Dict[str, Any], ctx: IntroContext) -> None:
        """Show a transient on-screen toast hint."""
        text = step.get("text")
        duration_s = step.get("duration_s", 5)
        if not isinstance(text, str) or not text:
            raise ValueError("dashboard_hint: missing `text` field")
        text = self._render_template(text, ctx.template_vars)
        # Dashboard_hint is just a specialized dashboard_event under the hood.
        self._run_dashboard_event(
            {
                "step": "dashboard_event",
                "event": "intro_hint",
                "payload": {"text": text, "duration_s": float(duration_s)},
            },
            ctx,
        )

    def _run_start_playlist(self, step: Dict[str, Any], ctx: IntroContext) -> None:
        """
        Load a custom playlist YAML and start the first song.

        Step shape:
            - step: start_playlist
              path: media/songs/playlist.yaml   # relative to pack dir, or absolute
              video: false                       # optional, default false

        Best-effort: missing music_provider, missing playlist file, or
        empty playlist all log + return without raising.
        """
        # Lazy import to avoid coupling intro_runner to the playlist module
        # at import time (and to keep the test suite's mock surface small).
        from core.custom_playlist import load_playlist, play_first

        rel = step.get("path", "media/songs/playlist.yaml")
        if not isinstance(rel, str) or not rel:
            raise ValueError("start_playlist: missing `path` field")
        path = self._resolve_path(rel, ctx)
        playlist = load_playlist(path)
        if playlist.is_empty:
            log.info("intro_runner: start_playlist — empty playlist at %s", path)
            return
        if ctx.music_provider is None:
            log.info("intro_runner: start_playlist — no music_provider, skipping")
            return
        title = play_first(
            playlist, ctx.music_provider, video=bool(step.get("video", False))
        )
        if title is None:
            log.warning("intro_runner: start_playlist failed (search/play)")
        else:
            log.info("intro_runner: start_playlist playing %r", title)

    # ── Helpers ────────────────────────────────────────────────────

    @staticmethod
    def _render_template(template: str, vars_: Dict[str, str]) -> str:
        """
        Naive {{ key }} substitution. Missing keys are left in place so
        the user can SEE the template hole if they forgot to fill it.
        Avoids importing jinja2 just for this — the templates are tiny.
        """
        out = template
        for key, value in vars_.items():
            out = out.replace("{{ " + key + " }}", str(value))
            out = out.replace("{{" + key + "}}", str(value))
        return out
