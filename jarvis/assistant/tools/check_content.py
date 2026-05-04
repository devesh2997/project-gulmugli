#!/usr/bin/env python3
"""
check_content.py — audit which user content is filled in vs missing.

The Phase 7 user-content slots are spread across the event pack
(photos, captions, voice memos, recorded songs, joke bank, quiz
questions, recorded intro / reveal / sorry memos, etc.) plus the
personality config (Astha tone). It's easy to lose track of what's
still placeholder.

This tool walks every slot, reports filled / placeholder / missing,
and at the end prints a checklist of action items. No code changes —
just a read-only audit.

## Usage

    cd jarvis/assistant
    python tools/check_content.py
    python tools/check_content.py --verbose   # show detailed reasons

## Exit code

    0  All required content present (still warns on optional items)
    1  At least one REQUIRED slot is empty / placeholder
    2  Tool error (missing dir, etc.)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

import yaml


# ── Output helpers ──────────────────────────────────────────────────


GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
DIM = "\033[2m"
RESET = "\033[0m"
BOLD = "\033[1m"


# Each check returns (status, detail) where status is one of:
#   "filled"      — content present and not a placeholder
#   "placeholder" — file exists but is a known stub / template
#   "missing"     — file or dir doesn't exist
#   "warn"        — some content present but might want more
STATUSES = {
    "filled":      f"{GREEN}✓ filled{RESET}",
    "placeholder": f"{YELLOW}~ placeholder{RESET}",
    "missing":     f"{RED}✗ missing{RESET}",
    "warn":        f"{YELLOW}△ thin{RESET}",
}


def _report(label: str, status: str, detail: str = "") -> tuple[str, str, str]:
    print(f"  {STATUSES[status]:30s} {label}"
          + (f" {DIM}— {detail}{RESET}" if detail else ""))
    return (label, status, detail)


# ── Path helpers ────────────────────────────────────────────────────


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PACK_DIR = PROJECT_ROOT / "events" / "astha-birthday"


def _has_audio(d: Path) -> int:
    """Return count of .wav/.mp3/.m4a files in a directory."""
    if not d.is_dir():
        return 0
    return sum(1 for _ in d.iterdir()
               if _.is_file() and _.suffix.lower() in (".wav", ".mp3", ".m4a"))


def _yaml_load(p: Path) -> Optional[dict | list]:
    if not p.is_file():
        return None
    try:
        with p.open() as f:
            return yaml.safe_load(f)
    except Exception:
        return None


# ── Checks ──────────────────────────────────────────────────────────


def check_photos() -> list[tuple]:
    """captions.yaml + photos/ dir."""
    print(f"\n{BOLD}📸 Photos (Yaadein){RESET}")
    results = []

    photos_dir = PACK_DIR / "media" / "photos"
    captions = _yaml_load(photos_dir / "captions.yaml")
    img_count = sum(1 for p in photos_dir.iterdir()
                    if p.is_file() and p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")) if photos_dir.is_dir() else 0

    if img_count == 0:
        results.append(_report(
            "photos in media/photos/", "missing",
            "drop chronological photos here",
        ))
    elif img_count < 10:
        results.append(_report(
            "photos in media/photos/", "warn",
            f"only {img_count} photo(s) — project_ag had ~40",
        ))
    else:
        results.append(_report(
            "photos in media/photos/", "filled",
            f"{img_count} photo(s)",
        ))

    if captions is None:
        results.append(_report("captions.yaml", "missing"))
    else:
        # Schema: captions.yaml may be a {photos: [...]} dict or just a list.
        photo_entries = []
        if isinstance(captions, dict):
            photo_entries = captions.get("photos") or []
        elif isinstance(captions, list):
            photo_entries = captions
        # Detect placeholder by sample-text matching.
        placeholder_phrases = ["sample caption", "placeholder", "[caption]", "TODO"]
        is_placeholder = any(
            any(ph.lower() in str(e.get("caption", "")).lower()
                for ph in placeholder_phrases)
            for e in photo_entries
            if isinstance(e, dict)
        )
        if not photo_entries:
            results.append(_report("captions.yaml entries", "missing"))
        elif is_placeholder:
            results.append(_report(
                "captions.yaml entries", "placeholder",
                f"{len(photo_entries)} entries but with sample text — write Hinglish memories per photo",
            ))
        else:
            results.append(_report(
                "captions.yaml entries", "filled",
                f"{len(photo_entries)} captioned",
            ))

    return results


def check_voice_memos() -> list[tuple]:
    print(f"\n{BOLD}💌 Voice memos{RESET}")
    results = []
    memos_yaml = _yaml_load(PACK_DIR / "media" / "voice_memos" / "memos.yaml")
    audio_count = _has_audio(PACK_DIR / "media" / "voice_memos")

    memo_list = (memos_yaml or {}).get("memos") if isinstance(memos_yaml, dict) else None
    if memo_list is None:
        memo_list = []

    if not memo_list:
        results.append(_report(
            "memos.yaml entries", "missing",
            "add at least one memo (birthday letter)",
        ))
    else:
        results.append(_report(
            "memos.yaml entries", "filled",
            f"{len(memo_list)} declared",
        ))

    if audio_count == 0:
        results.append(_report(
            "voice memo audio files", "missing",
            "record at least the birthday letter into media/voice_memos/",
        ))
    else:
        results.append(_report(
            "voice memo audio files", "filled",
            f"{audio_count} audio file(s)",
        ))

    return results


def check_intro() -> list[tuple]:
    print(f"\n{BOLD}🎬 Launch intro{RESET}")
    results = []

    intro_audio = PACK_DIR / "media" / "sounds" / "devesh_intro.wav"
    if not intro_audio.is_file():
        # Try mp3 variant
        intro_mp3 = PACK_DIR / "media" / "sounds" / "devesh_intro.mp3"
        if intro_mp3.is_file():
            results.append(_report(
                "devesh_intro recording", "filled",
                f"{intro_mp3.stat().st_size // 1024} KB (mp3)",
            ))
        else:
            results.append(_report(
                "devesh_intro recording", "missing",
                "record ~30s warm intro to media/sounds/devesh_intro.wav",
            ))
    else:
        size_kb = intro_audio.stat().st_size // 1024
        if size_kb < 50:
            results.append(_report(
                "devesh_intro recording", "warn",
                f"only {size_kb} KB — too short? aim for ~30s",
            ))
        else:
            results.append(_report(
                "devesh_intro recording", "filled",
                f"{size_kb} KB",
            ))

    intro_script = PACK_DIR / "first_year" / "intro_script.yaml"
    if not intro_script.is_file():
        results.append(_report("intro_script.yaml", "missing"))
    else:
        try:
            with intro_script.open() as f:
                script_data = yaml.safe_load(f)
            if isinstance(script_data, list) and script_data:
                results.append(_report(
                    "intro_script.yaml steps", "filled",
                    f"{len(script_data)} steps",
                ))
            else:
                results.append(_report(
                    "intro_script.yaml steps", "missing",
                    "empty or invalid script",
                ))
        except Exception as e:
            results.append(_report("intro_script.yaml", "missing", f"parse error: {e}"))

    return results


def check_jokes() -> list[tuple]:
    print(f"\n{BOLD}😂 Astha jokes bank{RESET}")
    results = []
    jokes = _yaml_load(PACK_DIR / "jokes" / "astha_jokes.yaml")
    if not isinstance(jokes, list):
        results.append(_report("astha_jokes.yaml", "missing"))
    elif len(jokes) < 5:
        results.append(_report(
            "astha_jokes.yaml", "warn",
            f"{len(jokes)} jokes — aim for >= 10 (5 from Astha + 5 seed)",
        ))
    else:
        results.append(_report(
            "astha_jokes.yaml", "filled",
            f"{len(jokes)} joke(s)",
        ))
    return results


def check_quiz() -> list[tuple]:
    print(f"\n{BOLD}🎯 Birthday quiz{RESET}")
    results = []
    quiz = _yaml_load(PACK_DIR / "quiz" / "about_us.yaml")
    if not isinstance(quiz, dict):
        results.append(_report("quiz/about_us.yaml", "missing"))
        return results

    questions = quiz.get("questions") or []
    if len(questions) < 3:
        results.append(_report(
            "quiz questions", "warn",
            f"{len(questions)} question(s) — aim for >= 5",
        ))
    else:
        # Detect placeholder questions (the ones the sub-agent seeded).
        placeholder_ids = {"q_favorite_food", "q_favorite_snack",
                           "q_favorite_singer", "q_first_meeting",
                           "q_first_movie"}
        placeholders = [q for q in questions
                        if isinstance(q, dict) and q.get("id") in placeholder_ids]
        if placeholders:
            results.append(_report(
                "quiz questions", "placeholder",
                f"{len(questions)} question(s); {len(placeholders)} are seed/placeholder — write real ones",
            ))
        else:
            results.append(_report(
                "quiz questions", "filled",
                f"{len(questions)} real question(s)",
            ))

    reveal = quiz.get("final_reveal") or {}
    audio = reveal.get("audio_file")
    if audio:
        audio_path = PACK_DIR / audio if not audio.startswith("/") else Path(audio)
        if audio_path.is_file():
            results.append(_report("quiz reveal recording", "filled"))
        else:
            results.append(_report(
                "quiz reveal recording", "missing",
                f"file referenced but not found: {audio}",
            ))
    elif reveal.get("fallback_text"):
        results.append(_report(
            "quiz reveal", "warn",
            "fallback_text only — record the audio for a stronger payoff",
        ))
    else:
        results.append(_report("quiz reveal", "missing"))

    return results


def check_besura() -> list[tuple]:
    print(f"\n{BOLD}🎤 Besura (Devesh singing){RESET}")
    results = []
    clips = _yaml_load(PACK_DIR / "media" / "besura" / "clips.yaml")
    audio_count = _has_audio(PACK_DIR / "media" / "besura")
    clip_list = (clips or {}).get("clips") if isinstance(clips, dict) else None
    if clip_list is None:
        clip_list = []

    if not clip_list and audio_count == 0:
        results.append(_report(
            "besura clips", "missing",
            "record at least 1 song clip into media/besura/",
        ))
    elif audio_count == 0:
        results.append(_report(
            "besura audio files", "missing",
            f"{len(clip_list)} declared but no audio files yet",
        ))
    else:
        results.append(_report(
            "besura clips", "filled",
            f"{audio_count} audio file(s), {len(clip_list)} declared",
        ))
    return results


def check_sorry_mode() -> list[tuple]:
    print(f"\n{BOLD}🥺 Sorry mode{RESET}")
    results = []
    audio_count = _has_audio(PACK_DIR / "media" / "sorry")
    if audio_count == 0:
        # Sorry-mode also reads from voice_memos with tag=sorry — check that path too.
        memos = _yaml_load(PACK_DIR / "media" / "voice_memos" / "memos.yaml")
        memo_list = (memos or {}).get("memos") if isinstance(memos, dict) else None
        sorry_tagged = [
            m for m in (memo_list or [])
            if isinstance(m, dict) and any(
                t.lower() in ("sorry", "apology")
                for t in (m.get("tags") or [])
            )
        ]
        if not sorry_tagged:
            results.append(_report(
                "sorry mode content", "missing",
                "record at least one apology — drop into media/sorry/ or tag a memo with 'sorry'",
            ))
        else:
            results.append(_report(
                "sorry mode (via tagged memos)", "warn",
                f"{len(sorry_tagged)} memo(s) tagged sorry — verify audio file exists",
            ))
    else:
        results.append(_report(
            "sorry mode audio", "filled",
            f"{audio_count} apology recording(s)",
        ))
    return results


def check_birthday_song() -> list[tuple]:
    print(f"\n{BOLD}🎂 Sing happy birthday{RESET}")
    results = []
    songs_dir = PACK_DIR / "media" / "songs"
    found = any((songs_dir / f"happy_birthday{ext}").is_file()
                for ext in (".wav", ".mp3", ".m4a"))
    if not found:
        results.append(_report(
            "happy_birthday recording", "warn",
            "TTS fallback works but a real recording lands better — record media/songs/happy_birthday.wav",
        ))
    else:
        results.append(_report("happy_birthday recording", "filled"))
    return results


def check_playlist() -> list[tuple]:
    print(f"\n{BOLD}🎶 Custom playlist{RESET}")
    results = []
    pl = _yaml_load(PACK_DIR / "media" / "songs" / "playlist.yaml")
    songs = (pl or {}).get("songs") if isinstance(pl, dict) else None
    if not songs:
        results.append(_report("playlist.yaml", "missing"))
        return results
    # Detect generic seeds (Bollywood birthday classics) vs Astha-personalized.
    generic_seeds = {
        "Tum Jiyo Hazaaron Saal", "Baar Baar Din Ye Aaye",
        "Sajni Arijit Singh", "Tum Hi Ho Aashiqui 2",
        "Channa Mereya Ae Dil Hai Mushkil", "Tujhe Kitna Chahne Lage Hum",
    }
    queries = [s.get("youtube_search", "") for s in songs if isinstance(s, dict)]
    placeholder_count = sum(1 for q in queries if q in generic_seeds)
    if placeholder_count == len(queries):
        results.append(_report(
            "playlist.yaml", "placeholder",
            f"all {len(queries)} entries are seed Bollywood classics — replace with Astha's actual favorites",
        ))
    elif placeholder_count > 0:
        results.append(_report(
            "playlist.yaml", "warn",
            f"{placeholder_count}/{len(queries)} are still seeds",
        ))
    else:
        results.append(_report(
            "playlist.yaml", "filled",
            f"{len(queries)} curated song(s)",
        ))
    return results


def check_astha_personality() -> list[tuple]:
    print(f"\n{BOLD}🧑‍🎤 Astha personality tone{RESET}")
    results = []
    cfg = _yaml_load(PROJECT_ROOT / "config.yaml")
    if cfg is None:
        results.append(_report("config.yaml", "missing"))
        return results
    profiles = (cfg.get("personalities") or {}).get("profiles") or {}
    astha = profiles.get("astha")
    if not astha:
        results.append(_report("astha personality profile", "missing"))
        return results
    tone = (astha.get("tone") or "")
    if "[CUSTOMIZE" in tone or "her mannerisms, pet phrases" in tone.lower():
        results.append(_report(
            "astha tone", "placeholder",
            "still has [CUSTOMIZE] placeholder — write 4-6 sentences in her voice",
        ))
    else:
        results.append(_report("astha tone", "filled", f"{len(tone)} chars"))
    return results


def check_laugh_clip() -> list[tuple]:
    print(f"\n{BOLD}🔊 Joke laugh audio{RESET}")
    results = []
    laugh = PACK_DIR / "media" / "sounds" / "laugh.wav"
    if laugh.is_file():
        results.append(_report("laugh.wav", "filled"))
    else:
        results.append(_report(
            "laugh.wav", "warn",
            "optional — astha_jokes setup_then_punchline plays this after the punchline",
        ))
    return results


# ── Main ─────────────────────────────────────────────────────────────


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--verbose", action="store_true",
                   help="Show extra detail per check")
    args = p.parse_args()

    if not PACK_DIR.is_dir():
        print(f"{RED}Pack dir not found: {PACK_DIR}{RESET}", file=sys.stderr)
        return 2

    print(f"\n{BOLD}🎂 Birthday Content Audit — events/astha-birthday/{RESET}")

    all_results = []
    all_results.extend(check_photos())
    all_results.extend(check_voice_memos())
    all_results.extend(check_intro())
    all_results.extend(check_birthday_song())
    all_results.extend(check_besura())
    all_results.extend(check_sorry_mode())
    all_results.extend(check_jokes())
    all_results.extend(check_quiz())
    all_results.extend(check_playlist())
    all_results.extend(check_laugh_clip())
    all_results.extend(check_astha_personality())

    # Summary table.
    counts = {"filled": 0, "warn": 0, "placeholder": 0, "missing": 0}
    for _, status, _ in all_results:
        counts[status] = counts.get(status, 0) + 1

    print(f"\n{BOLD}{'─' * 50}{RESET}")
    print(f"{BOLD}Summary{RESET}")
    print(f"  {GREEN}filled{RESET}      {counts['filled']:3d}")
    print(f"  {YELLOW}thin/warn{RESET}   {counts['warn']:3d}")
    print(f"  {YELLOW}placeholder{RESET} {counts['placeholder']:3d}")
    print(f"  {RED}missing{RESET}     {counts['missing']:3d}")

    # Action items: missing + placeholder are critical.
    critical = [r for r in all_results if r[1] in ("missing", "placeholder")]
    if critical:
        print(f"\n{BOLD}Action items before May 14:{RESET}")
        for label, status, detail in critical:
            color = RED if status == "missing" else YELLOW
            print(f"  {color}•{RESET} {label}"
                  + (f" {DIM}— {detail}{RESET}" if detail else ""))
        print()
        return 1

    print(f"\n{GREEN}All required content present. Optional warnings remain (see above).{RESET}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
