#!/usr/bin/env python3
"""
generate_captions.py — write Hinglish captions for the Yaadein slideshow
photos, using Claude Sonnet 4.5 with prompt caching.

## Why this exists

The slideshow has 560 photos spanning Jan 2021 → Apr 2026. Each one
needs a caption that sounds like Devesh wrote it — specifically the
project_ag voice: short, Hinglish, emoji-laced, never poetic, never
cliched.

This tool sends each photo to Claude Sonnet 4.5 along with a system
prompt that includes:
  - 42 verbatim caption samples from project_ag (voice anchors)
  - Style rules drawn from those samples
  - The chapter index with whatever labels the user has provided
  - Per-photo context: date, chapter, position-in-chapter

Output: the `caption:` field in `events/astha-birthday/media/captions.yaml`
gets populated. Iteration is fast because:
  1. The system prompt (~6K tokens) is cached for 5 minutes — re-runs
     cost ~10% of full price for the cached portion.
  2. You can target a single chapter via --chapter N, a single photo
     via --file X, or all 560 via --all.

## Run

  # Generate captions for one chapter (recommended first pass)
  python tools/generate_captions.py --chapter 1

  # Just one photo, useful for testing the voice
  python tools/generate_captions.py --file 001-2021-01-29.jpg

  # All 560
  python tools/generate_captions.py --all

  # Re-do only photos that have no caption yet
  python tools/generate_captions.py --missing-only

  # Force re-generate even photos that already have captions
  python tools/generate_captions.py --all --force

## Cost (with prompt caching)

First run on all 560: ~$2–3 (system prompt cached after first call)
Subsequent re-runs: ~$0.50 each (cache hits)
Single chapter (~30 photos): <$0.20
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import sys
import time
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import anthropic
except ImportError:
    print("ERROR: anthropic not installed. Run: pip install anthropic", file=sys.stderr)
    sys.exit(1)

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed. Run: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

try:
    from PIL import Image
except ImportError:
    print("ERROR: Pillow not installed. Run: pip install Pillow", file=sys.stderr)
    sys.exit(1)


# Don't let PyYAML alphabetize keys.
class OrderedDumper(yaml.SafeDumper):
    pass


def _represent_ordered_dict(dumper, data):
    return dumper.represent_mapping("tag:yaml.org,2002:map", data.items())


OrderedDumper.add_representer(OrderedDict, _represent_ordered_dict)
OrderedDumper.add_representer(dict, _represent_ordered_dict)


# ── Project_ag voice anchors — 42 captions verbatim ───────────────
# These are the voice. The model learns: short, Hinglish, specific,
# emoji-as-punctuation, never cliched, sometimes empty.
PROJECT_AG_CAPTIONS = [
    "This is where it all began 😇",
    "You remember this?? We were so used to holding hands whenever we went out but we couldn't do it there because sab koi the. So we held something else 😅",
    "Tumhara fast tha is din. And we were all stuffing our faces with food. 🥲",
    "Happy Birthday Cutie !!",
    "",
    "I guess our first movie together. And we held hands. It was a turning point for us in a way, because both of felt some spark that day.",
    "",
    "😂",
    "Our early morning hangouts.",
    "Planning every night ki subah jaldi aayenge 😇",
    "Just look at me. Sooo Sooo happy.  😇 😇",
    "Evening snacks  😇. You made coming to office fun for me. Tum nhi hoti to ek ek din kaatna would have been a labour.",
    "I love this dress  😍",
    "I remember sab koi neeche the is samay. And mujhe tu dikh nhi rhi thi. So I came looking for you.",
    "Found you in the gym, practicing. Then I got a private performance from you  😅",
    "I was hanging from the rooftop looking at your performance.",
    "Seekh ke aana tu, fir acting ke alawa we can also do this for real  😂",
    "Our first attempt at clubbing.",
    "Look at you. I can't believe someone as beautiful as you is with me.",
    "Our all time best pic. Main bhi isliye accha lag rha kyunki thoda sa hi dikh rha  😅",
    "When you sent me this. I was soooo sooo happy 😘",
    "Our first holi together 😇",
    "My susheel shona 😅",
    "My susheel shona Part 2. 😅",
    "See.. gusse mein bhi kitna cute lagti  😘",
    "I used to hate shopping. I really did. But you made even that fun. Now, I always want to go shopping with you. Tu kitna excited and khush rehti while shopping.  🥰",
    "Tu kitne acche se trial room ke bahar aake mujhe dikha rhi thi saari dresses. I loved that.  😇",
    "Meri shona ka duck face. Hot 🔥.  😍",
    "Our first valentine's day together  😍 😍 😍 😍",
    "Meri Golu Molu  😂",
    "Meri Golu Molu Part 2  😂",
    "Our first time *working* together at my place. It was a sad day but also a very happy one.  😇",
    "This is one of our first video calls. 🥰🥰",
    "Whatsapp and Signal have played a huge part in our relationship  😅.",
    "After a while, you became comfortable layering in front of me. 😅 😅",
    "Cuuuuuuuuute",
    "My sleeping beauty.  😍 😍",
    "Your last day in gurgaon. Ghar jaana hai.. but layering ke bina nhi ..",
    "Gorgeous.",
    "So, we are not together now.",
    "And we might have to stay apart for a long time.",
    "But you will always be in my heart shona.  😘 😘 😘 😘",
]


SYSTEM_PROMPT_TEMPLATE = """\
You write captions for a private photo-slideshow gift. Recipient: Astha.
Writer: Devesh (her boyfriend). Slideshow plays on her birthday.
Captions are TEXT only — the viewer reads them.

# Your only job

Write ONE caption for the photo I show you. Just the caption text.
No preamble, no quotes, no JSON, no labels. The caption appears
verbatim over the image.

**Critical: write in FIRST PERSON as Devesh.** You ARE Devesh — refer
to yourself as "I" / "main" / "mera". Refer to Astha as "you" / "tu" /
"tum" / "Astha" / "shona" / one of the pet names. NEVER refer to
Devesh in third person ("Devesh did X"). The caption is being written
BY Devesh, FOR Astha.

# Devesh's writing voice — DO NOT COPY VERBATIM

Below are 42 actual captions Devesh wrote for a previous version of
this slideshow (project_ag, made for an earlier birthday). They define
the VOICE — the rhythm, register, restraint, the specific cadence of
his Hinglish.

**These samples are reference, not vocabulary.** Do NOT copy any
phrase verbatim. Match the SHAPE of the voice — short sentences,
mid-sentence code switching, emoji as punctuation, specific over
abstract — but the words come from this photo's actual content +
context. Reusing project_ag phrases makes the new slideshow feel like
a recycled gift.

VOICE SAMPLES:
{voice_samples}

# What good captions sound like (in Devesh's voice)

✓ "Tu kitne acche se trial room ke bahar aake mujhe dikha rhi thi
   saari dresses. I loved that 😇"
   — references a specific gesture, mid-sentence Hindi→English, one emoji

✓ "My susheel shona 😅"
   — pet name + emoji, that's the whole caption, photo speaks rest

✓ "I used to hate shopping. I really did. But you made even that fun."
   — confesses something specific, no emoji needed

✓ "Cuuuuuuuuute"
   — single word with elongation, when the photo IS that

# What bad AI captions look like (DO NOT produce these)

✗ "A beautiful celebration with friends 🎉"
   — generic, describes scene, default emoji
✗ "Office wale sab log enjoying the moment 😇"
   — narration, not feeling; "enjoying the moment" is corporate
✗ "You light up my world like nobody else 💖"
   — pop-song cliché, English idiom Devesh would never use
✗ "Pehli baar tumhe red mein dekha tha"
   — could be okay but if photo isn't about red dress, it's invented
✗ "This is where it all began 😇"
   — verbatim copy from project_ag voice samples
✗ "Office fam celebrating with us. Sab koi happy the. 😇"
   — describes the obvious, default emoji again

# Hard rules

1. **Maximum 25 words.** Usually fewer.
2. **One emoji is the default.** Two for emotional peaks. Three or
   more is reserved for slideshow finales only.
3. **Cycle through emojis.** Don't reuse the same emoji as the most
   recent caption you generated. Common Devesh emojis to draw from:
   😇 😅 😍 🥰 😘 🥲 😌 😂 🥺 🔥 😎 🙃 🫶 💛
4. **Engage with the photo's actual content.** Look at it carefully:
   - What's the gesture? expression? action?
   - What's in the frame that's specific (a cake, a chair, a road)?
   - Caption THAT, not the scene category
5. **Use the chapter context as the FACTUAL anchor.** If the chapter
   intro says "Astha wrote 'Happy Birthday Cutiee' on the cake" and
   the photo shows a cake — REFERENCE it. If the photo shows people
   but no cake, the chapter context still tells you what day it is.
6. **Use location specifics when given.** "Gurgaon office", "Goa",
   "Ooty", "Lucknow" — anchors the memory. Drop generic location
   words ("at the venue", "on the trip") in favor of the actual place.
7. **Time of day matters.** "Late raat", "subah ki", "office ke
   baad" — when the per-photo metadata gives you this, USE it.
8. **Burst photos.** If the metadata says burst_size > 1, this photo
   is one of N near-identical shots from the same moment. Most should
   be `<NO_CAPTION>` (silent) — caption only ONE of them, ideally the
   most expressive. The others get a brief silent pass.
9. **Empty captions are FINE.** If the photo is a quiet portrait or
   a close-up that needs no words, return exactly: <NO_CAPTION>
10. **Pet names allowed but rare** — "shona", "cutie", "cutiee",
    "golu molu", "susheel shona". Maybe 1 in every 8 captions, not more.
11. **Vary sentence structures.** Don't start every caption with "Our"
    or "This is" or "Tum/Tu". Mix.

# What NEVER to write

- "To the moon and back", "you complete me", any pop-song idiom
- Flowery metaphors ("sunshine", "rainbow", "stars")
- Hindi shayari / Urdu poetic register
- Generic compliments ("you look stunning", "perfect smile")
- Literal scene description ("a person standing in a park")
- The exact phrase "This is where it all began" (reserved — project_ag
  used it once, never reuse)
- "Just" as a hedge ("just a moment", "just us")

# Chapter index — the album's story arc

{chapter_index}

# Output format — STRICT

Your entire response is EITHER:
  (a) The caption text — nothing else. The very first character of
      your response is the very first character of the caption. The
      very last character of your response is the last character of
      the caption (typically a letter, period, or emoji).
  (b) The literal seven-character string `<NO_CAPTION>` — nothing else.

You may NOT include ANY of the following in your response:
  - Reasoning, analysis, or explanation ("Looking at this photo...")
  - Phrases like "Caption:" / "Here is the caption:" / "I think..."
  - Quotation marks around the caption
  - Markdown formatting
  - Multiple options or alternatives
  - Preamble, commentary, or hedging
  - The words "considering", "given that", "since this is"

EXAMPLE OF CORRECT RESPONSE (single line, just the caption):
  Meri pehli birthday with you 🎂

EXAMPLE OF INCORRECT RESPONSE (NEVER do this):
  Looking at this photo, I can see Astha at her birthday celebration.
  Given the chapter context about the office, I'll caption:

  Meri pehli birthday with you 🎂

The incorrect example leaks reasoning into the output. The correct
example is just the caption. Imagine your response will be pasted
directly under the photo with zero post-processing — anything you
write that isn't the caption itself shows up as garbage on the
slideshow.

If your response includes any pre-amble like "Looking at this photo"
or "Given the context", you've failed the format check. Strip
EVERYTHING except the caption itself.

# When `<NO_CAPTION>` is the right answer

ONLY use `<NO_CAPTION>` in these specific situations:
  - The photo is a near-duplicate of an earlier burst photo
    (`burst_size > 1` AND this isn't the most expressive one)
  - The photo is a quiet portrait that genuinely needs no words
    (rare — most photos benefit from a caption)
  - The photo is purely scenic with no people / story moment

Default to WRITING a caption. <NO_CAPTION> is the exception, not
the rule. About 1 in 6 photos in a typical slideshow should be silent.
If you're tempted to go silent because you're unsure what to write,
that means you should write something specific instead.
"""


@dataclass
class PhotoTask:
    file: str               # filename in the photos folder
    path: Path
    date: str               # YYYY-MM-DD
    chapter: int
    position: int           # 1-based position in the album
    chapter_title: str
    chapter_position: str   # e.g. "3 of 46"
    enriched: dict          # all fields from enriched_metadata.json (or {})
    keep: bool = False      # user marked this for the slideshow
    highlight: bool = False # user marked this as a visual climax


def load_api_key() -> str:
    """Load API key from ~/.anthropic/api_key.vesper (preferred) or env."""
    p = Path.home() / ".anthropic" / "api_key.vesper"
    if p.exists():
        return p.read_text().strip()
    import os
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError(
            "No API key found. Save to ~/.anthropic/api_key.vesper "
            "or set ANTHROPIC_API_KEY."
        )
    return key


def encode_image(image_path: Path, max_dim: int = 1568) -> tuple[str, str]:
    """Read, downscale, re-encode as JPEG, return (b64, media_type).

    Claude charges by image tokens. 1568px is roughly the sweet spot
    for vision — anything larger doesn't improve recognition much but
    costs proportionally more tokens.
    """
    img = Image.open(image_path)
    if img.mode != "RGB":
        img = img.convert("RGB")
    # Preserve aspect ratio.
    img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88, optimize=True)
    b64 = base64.standard_b64encode(buf.getvalue()).decode()
    return b64, "image/jpeg"


def build_chapter_index(captions_doc: dict) -> str:
    """Render the chapter dict as a markdown table for the system prompt."""
    chapters = captions_doc.get("chapters", {})
    lines = []
    for key, meta in chapters.items():
        title = meta.get("title", "")
        date_range = meta.get("date_range", "")
        count = meta.get("photo_count", "?")
        intro = meta.get("intro_caption", "")
        # Strip the [edit] prefix — that's a placeholder for the user.
        clean = title.replace("[edit] ", "")
        ch_num = key.replace("chapter_", "")
        line = f"- Chapter {ch_num} ({date_range}, {count} photos): {clean}"
        if intro:
            line += f"\n    Note: {intro}"
        lines.append(line)
    return "\n".join(lines)


def build_system_prompt(captions_doc: dict) -> str:
    """Assemble the full system prompt with voice samples + chapter index."""
    # Number the voice samples for clarity in the prompt.
    voice_block = "\n".join(
        f'{i+1}. {repr(c)[1:-1] if c else "[empty caption — photo stood alone]"}'
        for i, c in enumerate(PROJECT_AG_CAPTIONS)
    )
    chapter_block = build_chapter_index(captions_doc)
    return SYSTEM_PROMPT_TEMPLATE.format(
        voice_samples=voice_block,
        chapter_index=chapter_block,
    )


def build_photo_tasks(
    manifest: dict,
    captions_doc: dict,
    photos_dir: Path,
    enriched: dict | None = None,
) -> list[PhotoTask]:
    """Combine manifest + captions.yaml + enriched metadata into per-photo tasks."""
    enriched = enriched or {}

    # Count photos per chapter for "position in chapter" framing.
    by_chapter: dict[int, list[str]] = {}
    for p in captions_doc.get("photos", []):
        by_chapter.setdefault(p["chapter"], []).append(p["file"])

    # Chapter titles
    titles = {}
    for key, meta in captions_doc.get("chapters", {}).items():
        ch_num = int(key.replace("chapter_", ""))
        titles[ch_num] = meta.get("title", "").replace("[edit] ", "")

    tasks: list[PhotoTask] = []
    for pos, entry in enumerate(captions_doc.get("photos", []), 1):
        fname = entry["file"]
        ch = entry["chapter"]
        ch_files = by_chapter.get(ch, [])
        ch_pos = ch_files.index(fname) + 1 if fname in ch_files else 0
        tasks.append(PhotoTask(
            file=fname,
            path=photos_dir / fname,
            date=entry.get("date", "unknown"),
            chapter=ch,
            position=pos,
            chapter_title=titles.get(ch, ""),
            chapter_position=f"{ch_pos} of {len(ch_files)}",
            enriched=enriched.get(fname, {}),
            keep=bool(entry.get("keep", False)),
            highlight=bool(entry.get("highlight", False)),
        ))
    return tasks


def format_enriched_context(task: PhotoTask) -> str:
    """Render enriched metadata into a compact context block for the LLM.
    Only includes fields with values — keeps the prompt lean."""
    e = task.enriched
    if not e:
        return ""
    lines: list[str] = []

    # Date + time-of-day
    t_parts = []
    if e.get("day_of_week"):
        t_parts.append(e["day_of_week"])
    if e.get("time_of_day"):
        t_parts.append(e["time_of_day"])
    if e.get("season_india"):
        t_parts.append(f"{e['season_india']} season")
    if t_parts:
        lines.append(f"  When: {', '.join(t_parts)}")

    # Location
    loc_parts = []
    if e.get("locality") and e.get("locality") != e.get("city"):
        loc_parts.append(e["locality"])
    if e.get("city"):
        loc_parts.append(e["city"])
    if e.get("state"):
        loc_parts.append(e["state"])
    if loc_parts:
        lines.append(f"  Where: {', '.join(loc_parts)}")

    # Story-arc anchors
    if e.get("days_since_album_start") is not None:
        d = e["days_since_album_start"]
        if d == 0:
            arc = "day 1 of the entire album story"
        elif d < 30:
            arc = f"day {d} since the album's first photo"
        else:
            yrs = d / 365
            arc = f"~{yrs:.1f} years into the story (day {d})"
        lines.append(f"  Story-arc: {arc}")

    gap = e.get("days_since_prev_photo")
    if gap is not None:
        if gap < 0.5:
            gap_desc = "same moment as previous photo (burst)"
        elif gap < 1:
            gap_desc = "later the same day"
        elif gap < 2:
            gap_desc = "next day"
        elif gap < 14:
            gap_desc = f"{int(gap)} days after previous"
        elif gap < 60:
            gap_desc = f"{int(gap)} days after previous (significant gap)"
        else:
            gap_desc = f"{int(gap)} days after previous (long gap — new chapter)"
        lines.append(f"  Continuity: {gap_desc}")

    # Burst
    if e.get("burst_size", 1) > 1:
        lines.append(f"  Burst: 1 of {e['burst_size']} near-identical shots — "
                     f"most should be silent, caption only the most expressive")

    # Camera / device (subtle era hint)
    if e.get("camera"):
        # Trim long camera strings
        cam = e["camera"].replace("ONEPLUS", "OnePlus")
        if len(cam) <= 30:
            lines.append(f"  Device: {cam}")

    # Orientation (helps the caption length match the shape)
    if e.get("orientation") == "portrait":
        lines.append(f"  Frame: portrait (often selfie / single subject)")
    elif e.get("orientation") == "square":
        lines.append(f"  Frame: square")

    # Flash
    if e.get("flash_fired"):
        lines.append("  Lighting: flash fired (likely indoor / night)")

    return "\n".join(lines)


def generate_caption(
    client: anthropic.Anthropic,
    system_prompt: str,
    task: PhotoTask,
    model: str = "claude-sonnet-4-5",
) -> tuple[str, dict]:
    """Send one photo to Claude. Returns (caption, usage_dict)."""
    b64, media_type = encode_image(task.path)

    context_lines = [
        f"# Photo {task.position} of 560",
        f"  Date: {task.date}",
        f"  Chapter: {task.chapter}"
        + (f" — {task.chapter_title}" if task.chapter_title else "")
        + f" (position {task.chapter_position})",
    ]
    # ── Crucial: tell Claude when the user has explicitly chosen this
    # photo. If burst_size > 1 but the user picked THIS shot, it
    # means this is the one — go write a caption, don't go silent.
    if task.highlight:
        context_lines.append(
            "  STATUS: HIGHLIGHTED by user — this is a visual climax. "
            "Write a strong, specific caption."
        )
    elif task.keep:
        context_lines.append(
            "  STATUS: KEPT by user — they explicitly chose this photo "
            "for the slideshow. Write a caption. If this is a burst, "
            "the user already picked THIS shot — do NOT go silent."
        )
    enriched_block = format_enriched_context(task)
    if enriched_block:
        context_lines.append(enriched_block)
    context_lines.append("")
    context_lines.append(
        "Write the caption now. Just the caption text. No quotes, no labels."
    )
    context_text = "\n".join(context_lines)

    user_message = [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": b64,
            },
        },
        {"type": "text", "text": context_text},
    ]

    # Cache the system prompt — 5-minute TTL. Subsequent calls within
    # 5 min hit the cache and pay ~10% for the cached portion.
    resp = client.messages.create(
        model=model,
        max_tokens=200,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_message}],
    )

    caption = resp.content[0].text.strip()

    # ── Safety net: strip leaked reasoning ─────────────────────────
    # Sometimes Claude leaks its internal reasoning into the output
    # (e.g., "Looking at this photo carefully... <newline>... <caption>").
    # Post-process: if the response has multiple lines, take only the
    # LAST non-empty line. The reasoning is always above; the caption
    # is always last.
    if "\n" in caption:
        lines = [l.strip() for l in caption.splitlines() if l.strip()]
        if lines:
            caption = lines[-1]
    # Also strip common preamble phrases that might appear inline.
    for prefix in ("Caption:", "caption:", "Here's the caption:",
                   "I'll write:", "Final caption:"):
        if caption.startswith(prefix):
            caption = caption[len(prefix):].strip()
    # Strip wrapping quotes
    if (caption.startswith('"') and caption.endswith('"')) or \
       (caption.startswith("'") and caption.endswith("'")):
        caption = caption[1:-1].strip()

    # Handle the NO_CAPTION token cleanly
    if caption == "<NO_CAPTION>":
        caption = ""

    usage = {
        "input_tokens": resp.usage.input_tokens,
        "output_tokens": resp.usage.output_tokens,
        "cache_read": resp.usage.cache_read_input_tokens or 0,
        "cache_create": resp.usage.cache_creation_input_tokens or 0,
    }
    return caption, usage


def estimate_cost(usage: dict) -> float:
    """Rough USD cost. Sonnet 4.5 pricing (May 2026):
       input = $3/M, output = $15/M, cache read = $0.30/M,
       cache create = $3.75/M (25% premium over input)."""
    return (
        usage["input_tokens"] * 3.0 / 1_000_000
        + usage["output_tokens"] * 15.0 / 1_000_000
        + usage["cache_read"] * 0.30 / 1_000_000
        + usage["cache_create"] * 3.75 / 1_000_000
    )


def filter_tasks(
    tasks: list[PhotoTask], captions_doc: dict, args
) -> list[PhotoTask]:
    """Apply --chapter / --file / --missing-only / --force / --skipped-too /
    --include-undecided flags.

    Default targeting:
      - Skipped photos: excluded (waste of money — won't be in slideshow).
        Override with --skipped-too.
      - Undecided photos: excluded (user hasn't decided to keep these yet).
        Override with --include-undecided OR --all.
      - Kept + Highlighted: included.
    """
    entries = {p["file"]: p for p in captions_doc.get("photos", [])}

    out = []
    for t in tasks:
        entry = entries.get(t.file, {})

        # Filename / chapter filters first
        if args.chapter and t.chapter != args.chapter:
            continue
        if args.file and t.file != args.file:
            continue

        # Skip photos (user explicitly excluded from slideshow)
        if entry.get("skip") and not args.skipped_too and not args.all:
            continue

        # Undecided photos (user hasn't decided yet)
        is_undecided = (not entry.get("keep")
                        and not entry.get("highlight")
                        and not entry.get("skip"))
        if is_undecided and not args.include_undecided and not args.all:
            continue

        # `--missing-only`: skip photos that already have a non-empty
        # caption.
        if args.missing_only and entry.get("caption"):
            continue

        # Default deny when no selection flag set
        if (not args.force and not args.missing_only and not args.all
                and not args.chapter and not args.file):
            continue

        out.append(t)
    return out


def save_captions_yaml(captions_doc: dict, output_path: Path) -> None:
    """Atomic write of captions.yaml."""
    tmp = output_path.with_suffix(".yaml.tmp")
    tmp.write_text(
        yaml.dump(captions_doc, Dumper=OrderedDumper,
                  sort_keys=False, allow_unicode=True, width=200)
    )
    tmp.replace(output_path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate Hinglish captions for the slideshow photos.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--captions", default="events/astha-birthday/media/captions.yaml")
    parser.add_argument("--manifest", default="events/astha-birthday/media/photos/manifest.json")
    parser.add_argument("--photos-dir", default="events/astha-birthday/media/photos")
    parser.add_argument("--chapter", type=int, help="Only this chapter")
    parser.add_argument("--file", help="Only this filename")
    parser.add_argument("--all", action="store_true", help="All 560")
    parser.add_argument("--missing-only", action="store_true",
                        help="Only photos without a caption yet")
    parser.add_argument("--force", action="store_true",
                        help="Re-generate even photos that already have captions")
    parser.add_argument("--skipped-too", action="store_true",
                        help="Also caption photos marked skip:true (default: "
                        "skipped photos are excluded since they won't appear "
                        "in the slideshow anyway)")
    parser.add_argument("--include-undecided", action="store_true",
                        help="Also caption photos not yet decided (default: "
                        "only KEEP + HIGHLIGHT photos are captioned, since "
                        "undecided photos may end up skipped)")
    parser.add_argument("--model", default="claude-sonnet-4-5")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    here = Path(__file__).resolve().parent.parent
    captions_path = Path(args.captions)
    if not captions_path.is_absolute():
        captions_path = here / captions_path
    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = here / manifest_path
    photos_dir = Path(args.photos_dir)
    if not photos_dir.is_absolute():
        photos_dir = here / photos_dir

    if not captions_path.exists():
        print(f"ERROR: captions.yaml not at {captions_path}.\n"
              f"Run scaffold_captions.py first.", file=sys.stderr)
        return 1

    captions_doc = yaml.safe_load(captions_path.read_text())
    manifest = json.loads(manifest_path.read_text())

    # Load enriched metadata (camera, GPS-city, time-of-day, burst, etc.)
    enriched_path = photos_dir / "enriched_metadata.json"
    enriched = {}
    if enriched_path.exists():
        try:
            enriched = json.loads(enriched_path.read_text()).get("photos", {})
            print(f"  Loaded enriched metadata for {len(enriched)} photos")
        except (json.JSONDecodeError, KeyError):
            print(f"  WARNING: enriched_metadata.json malformed, ignoring")
    else:
        print(f"  No enriched_metadata.json — run tools/enrich_metadata.py first "
              f"for better caption context")

    tasks = build_photo_tasks(manifest, captions_doc, photos_dir, enriched)
    tasks = filter_tasks(tasks, captions_doc, args)

    if not tasks:
        print("Nothing to do. Pass --chapter N / --file F / --all / --missing-only.")
        return 0

    print(f"== generate_captions.py ==")
    print(f"Photos to caption: {len(tasks)}")
    print(f"Model: {args.model}")
    print()

    if args.dry_run:
        for t in tasks[:20]:
            print(f"  {t.file}  ch{t.chapter:>2d}  {t.chapter_position:>10s}  "
                  f"{t.date}  ({t.chapter_title or 'no title'})")
        if len(tasks) > 20:
            print(f"  ... and {len(tasks) - 20} more")
        return 0

    client = anthropic.Anthropic(api_key=load_api_key())
    system_prompt = build_system_prompt(captions_doc)
    entries = {p["file"]: p for p in captions_doc["photos"]}

    total_cost = 0.0
    total_usage = {"input_tokens": 0, "output_tokens": 0,
                   "cache_read": 0, "cache_create": 0}
    start = time.time()

    for i, task in enumerate(tasks, 1):
        try:
            caption, usage = generate_caption(client, system_prompt, task, args.model)
        except anthropic.APIError as e:
            print(f"  [{i}/{len(tasks)}] {task.file}  ✗ API error: {e}")
            continue
        except FileNotFoundError:
            print(f"  [{i}/{len(tasks)}] {task.file}  ✗ photo missing")
            continue

        for k, v in usage.items():
            total_usage[k] += v
        cost = estimate_cost(usage)
        total_cost += cost

        # Update the YAML doc in memory; write at end.
        entries[task.file]["caption"] = caption

        # Show caption inline.
        display = caption if caption else "<silent>"
        print(f"  [{i:>3d}/{len(tasks)}]  {task.file}  →  {display}")

        # Save every 10 photos so a crash doesn't lose work.
        if i % 10 == 0:
            save_captions_yaml(captions_doc, captions_path)

    save_captions_yaml(captions_doc, captions_path)

    elapsed = time.time() - start
    print()
    print(f"Done in {elapsed:.0f}s.")
    print(f"Tokens: input={total_usage['input_tokens']:,} "
          f"output={total_usage['output_tokens']:,} "
          f"cache_read={total_usage['cache_read']:,} "
          f"cache_create={total_usage['cache_create']:,}")
    print(f"Estimated cost: ${total_cost:.4f}")
    print(f"Captions written to: {captions_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
