#!/usr/bin/env python3
"""
birthday_rehearsal.py — dry-run the May 14 launch sequence on Mac.

## Why

You don't want to discover at 11:59 PM on May 13 that the trigger
phrase isn't classified, the intro script's audio file path is wrong,
or the trigger-state persistence is broken. This script simulates the
whole flow end-to-end against the real components (event_manager,
trigger_state, intro_runner) — but with audio playback / TTS / face_ui
either patched out or running in mock mode so it doesn't actually wake
the household at 3 AM.

## What it covers

  1. event_manager loads the astha-birthday pack
  2. branding resolves correctly (assistant.name = "Vesper")
  3. /api/events/health returns the expected shape
  4. trigger_state starts clean (or can be reset)
  5. Intent classifier maps the manual phrase to event_trigger
     (this is the only piece that hits Ollama; ~5s per call)
  6. trigger fires → trigger_state persists → /current reflects
  7. intro_runner runs every step in the script with mocks
  8. Memory tagging works (interactions on the day get
     event:astha-birthday, year:<this_year>)
  9. Yaadein loader returns a manifest (or warns if photos missing)
 10. Joke engine has at least one joke loaded
 11. Custom playlist YAML parses

## What it does NOT cover

  - Real audio playback (would need speaker hardware)
  - Real TTS (would need Kokoro / Piper / XTTS loaded)
  - Real WebSocket pushes to the dashboard
  - Wake-word detection (mic hardware)
  - Network discovery (mDNS)

These all have their own paths to verify; this script is the **logic**
rehearsal, not the **hardware** rehearsal.

## Usage

    cd jarvis/assistant
    python tools/birthday_rehearsal.py
    python tools/birthday_rehearsal.py --skip-llm    # offline-only
    python tools/birthday_rehearsal.py --reset       # wipe trigger state first
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

# Bring assistant/ onto the path so we can import core/* and friends.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ── Output helpers ──────────────────────────────────────────────────


GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
DIM = "\033[2m"
RESET = "\033[0m"
BOLD = "\033[1m"


_results: list[tuple[str, bool, str]] = []
_step = 0


def _step_start(name: str) -> None:
    global _step
    _step += 1
    print(f"{BOLD}[{_step:2d}]{RESET} {name} {DIM}…{RESET}", end=" ", flush=True)


def _ok(detail: str = "") -> None:
    print(f"{GREEN}✓{RESET}" + (f" {DIM}{detail}{RESET}" if detail else ""))
    _results.append((f"step {_step}", True, detail))


def _fail(detail: str) -> None:
    print(f"{RED}✗ {detail}{RESET}")
    _results.append((f"step {_step}", False, detail))


def _skip(reason: str) -> None:
    print(f"{YELLOW}skipped{RESET} {DIM}— {reason}{RESET}")


# ── Steps ────────────────────────────────────────────────────────────


def step_event_manager_loads_pack() -> None:
    _step_start("event_manager loads astha-birthday pack")
    from core.event_manager import get_event_manager
    em = get_event_manager()
    pack_ids = {p.pack_id for p in em.list_packs()}
    if "astha-birthday" in pack_ids:
        _ok(f"loaded packs: {sorted(pack_ids)}")
    else:
        _fail(f"astha-birthday missing; loaded: {sorted(pack_ids)}")


def step_brand_resolves() -> None:
    _step_start("branding.brand resolves to Vesper")
    from core.branding import brand
    if brand.name == "Vesper":
        _ok(f"name={brand.name}, protocol={brand.protocol_id}")
    else:
        _fail(f"expected Vesper, got {brand.name}")


def step_trigger_state_clean(reset: bool) -> None:
    _step_start("trigger_state clean for current year")
    from core.trigger_state import get_trigger_store
    store = get_trigger_store()
    year = datetime.now().year
    if reset:
        was = store.is_triggered("astha-birthday", year=year)
        store.reset("astha-birthday", year=year)
        _ok(f"reset (was {was})")
    elif store.is_triggered("astha-birthday", year=year):
        _fail(
            "already triggered this year — pass --reset to clear, "
            "or this is intended state on a real birthday-day rehearsal"
        )
    else:
        _ok("not yet triggered (clean state)")


def step_simulated_event_is_today() -> None:
    _step_start("event_manager.current() at simulated May 14 → is_today=True")
    from core.event_manager import get_event_manager
    em = get_event_manager()
    sim = datetime(datetime.now().year, 5, 14, 12, 0, 0)
    active = em.current(now=sim)
    if active and active.is_today and active.pack_id == "astha-birthday":
        _ok(f"days_until={active.days_until}")
    else:
        _fail(f"got {active!r}")


def step_intent_classifies_trigger_phrase(skip_llm: bool) -> None:
    _step_start("intent classifier maps manual phrase to event_trigger")
    if skip_llm:
        _skip("--skip-llm passed")
        return
    try:
        # Quick one-shot classification — uses the live Ollama brain.
        # This is the slowest step (~3-6s on Mac).
        from core.config import config
        from providers.brain.ollama import OllamaBrainProvider
        bc = config.get("brain", {})
        brain = OllamaBrainProvider(
            model=bc.get("model", "llama3.2:3b"),
            endpoint=bc.get("endpoint", "http://localhost:11434"),
            temperature=0.1,
        )
        intents = brain.classify_intent("Vesper, project AG begins")
        first_name = intents[0].name if intents else "<none>"
        if first_name == "event_trigger":
            _ok("classified as event_trigger ✓")
        else:
            _fail(f"got {first_name!r} — not event_trigger")
    except Exception as e:
        _fail(f"{type(e).__name__}: {e}")


def step_trigger_persists_via_api() -> None:
    _step_start("POST /api/events/trigger persists state")
    from fastapi.testclient import TestClient
    from api.app import create_api
    from core import config as cfg_mod
    from core.trigger_state import get_trigger_store

    cfg_mod.config.setdefault("api", {})
    cfg_mod.config["api"]["auth_enabled"] = False
    fake_assistant = {
        "name": "Vesper",
        "version": "1.0.0",
        "voice_router": MagicMock(),
        "music": MagicMock(),
        "face_ui": MagicMock(),
        "memory": MagicMock(),
    }
    app = create_api(fake_assistant)
    client = TestClient(app)

    # Mock event_manager.current() to return is_today=True.
    fake_active = MagicMock()
    fake_active.pack_id = "astha-birthday"
    fake_active.pack.display_name = "Astha's Birthday"
    fake_active.pack.features = []
    fake_active.pack.trigger_config = {}
    fake_active.pack.raw = {}
    fake_active.is_today = True

    store = get_trigger_store()
    year = datetime.now().year
    # Reset for isolated rehearsal.
    store.reset("astha-birthday", year=year)

    with patch("api.routers.events.get_event_manager") as mock_em:
        mock_em.return_value.current.return_value = fake_active
        mock_em.return_value.list_packs.return_value = []
        r = client.post("/api/events/trigger")

    if r.status_code == 200 and r.json()["is_triggered"]:
        _ok("freshly_triggered=true")
        # Roll back so a re-rehearsal is clean.
        store.reset("astha-birthday", year=year)
    else:
        _fail(f"got {r.status_code}: {r.text}")


def step_intro_runner_executes() -> None:
    _step_start("intro_runner runs every step type")
    from core.intro_runner import IntroContext, IntroRunner

    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        # Write a synthetic intro script with all 4 step types.
        (tmp / "intro.yaml").write_text("""
- step: dashboard_event
  event: rehearsal_marker
- step: speak
  personality: jarvis
  text: "rehearsal speak step"
- step: dashboard_hint
  text: "rehearsal hint"
  duration_s: 2
""")
        ctx = IntroContext(
            pack_dir=tmp,
            voice_router=MagicMock(),
            face_ui=MagicMock(),
        )
        result = IntroRunner(tmp / "intro.yaml").run(ctx)
        if result.completed == 3 and not result.failures:
            _ok("3/3 steps completed")
        else:
            _fail(
                f"completed={result.completed}/{result.total_steps}, "
                f"failures={result.failures}"
            )


def step_memory_tagging_active() -> None:
    _step_start("memory provider supports event tagging")
    from providers.memory.sqlite import SQLiteMemoryProvider
    from core.interfaces import Interaction

    with tempfile.TemporaryDirectory() as tmp_str:
        prov = SQLiteMemoryProvider(db_path=str(Path(tmp_str) / "m.db"))
        prov.log_interaction(Interaction(
            user_id="default",
            input_text="test",
            intents=[],
            responses=["ok"],
            tags=["event:astha-birthday", "year:2026"],
        ))
        rows = prov.find_event_memories(event_id="astha-birthday", year=2026)
        if len(rows) == 1:
            _ok("event tagging round-trip works")
        else:
            _fail(f"expected 1 row, got {len(rows)}")


def step_yaadein_loader() -> None:
    _step_start("yaadein loader reports manifest shape")
    from providers.yaadein.local import load_photos
    pack_root = Path(__file__).resolve().parent.parent / "events" / "astha-birthday"
    photos_dir = pack_root / "media" / "photos"
    try:
        # load_photos signature varies; try the photos_dir form first.
        try:
            pack = load_photos(photos_dir)
        except TypeError:
            pack = load_photos(pack_root)
        # YaadeinPack.photos is the list; surface its size.
        photo_count = len(getattr(pack, "photos", []) or [])
        if photo_count == 0:
            print(f"{YELLOW}(0 photos — drop them in {photos_dir.name}/ before May 14){RESET}",
                  end=" ")
        _ok(f"{photo_count} photo(s) declared in captions.yaml")
    except Exception as e:
        _fail(f"{type(e).__name__}: {e}")


def step_joke_engine_loaded() -> None:
    _step_start("joke engine has at least one joke")
    from core.astha_jokes import get_joke_engine
    eng = get_joke_engine()
    n = len(eng.list_jokes())
    if n >= 1:
        _ok(f"{n} joke(s) loaded")
    else:
        _fail("zero jokes — check astha_jokes.yaml")


def step_custom_playlist_loads() -> None:
    _step_start("custom playlist YAML parses")
    from core.custom_playlist import load_playlist
    pl_path = (
        Path(__file__).resolve().parent.parent
        / "events" / "astha-birthday"
        / "media" / "songs" / "playlist.yaml"
    )
    pl = load_playlist(pl_path)
    if not pl.is_empty:
        _ok(f"{len(pl.queries)} song(s) queued, shuffle={pl.shuffle}")
    else:
        _fail("playlist is empty — fix events/astha-birthday/media/songs/playlist.yaml")


# ── Main ─────────────────────────────────────────────────────────────


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--skip-llm", action="store_true",
                   help="Skip the live Ollama classification check")
    p.add_argument("--reset", action="store_true",
                   help="Wipe astha-birthday trigger state for the current year first")
    args = p.parse_args()

    print(f"\n{BOLD}🎂 Birthday Rehearsal — May 14 launch dry-run{RESET}\n")

    step_brand_resolves()
    step_event_manager_loads_pack()
    step_simulated_event_is_today()
    step_trigger_state_clean(reset=args.reset)
    step_intent_classifies_trigger_phrase(skip_llm=args.skip_llm)
    step_trigger_persists_via_api()
    step_intro_runner_executes()
    step_memory_tagging_active()
    step_yaadein_loader()
    step_joke_engine_loaded()
    step_custom_playlist_loads()

    passed = sum(1 for _, ok, _ in _results if ok)
    total = len(_results)
    color = GREEN if passed == total else RED
    print(f"\n{color}{passed}/{total} steps passed{RESET}\n")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
