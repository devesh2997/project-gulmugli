# Event Packs

An **event pack** is a self-contained bundle of features, theme overrides, voice
lines, and media that the assistant auto-activates on certain dates. Packs are
the unit of distribution for seasonal / occasion-specific content (a birthday,
Diwali, Christmas, an anniversary, etc.). Each pack lives in its own directory
under `events/` and is fully isolated — drop one in, the assistant picks it up
on next reload; remove one, the assistant forgets it.

The master plan that drives this layout lives at
[`jarvis/BIRTHDAY_ROADMAP.md`](../../BIRTHDAY_ROADMAP.md). Read that first if
you're trying to understand *why* the structure looks the way it does.

## Directory layout

```
events/
├── README.md                    # this file
└── <pack-id>/                   # one directory per pack, kebab-case id
    ├── pack.yaml                # date rule + metadata + feature manifest
    ├── theme/
    │   ├── tokens.json          # CSS-var overrides for the dashboard theme
    │   └── avatar.json          # avatar accessory config (e.g., party hat)
    ├── first_year/              # year-1-only content (e.g., the launch flow)
    │   └── intro_script.yaml
    ├── voice_lines/             # short text snippets for time-of-day greetings
    │   ├── morning.txt
    │   └── goodnight.txt
    ├── media/                   # binary assets, organized by use
    │   ├── photos/              # slideshow photos (with captions JSON)
    │   ├── songs/               # custom playlist audio + happy birthday clip
    │   ├── sounds/              # confetti chimes, laughs, intro voice, etc.
    │   ├── besura/              # recorded singing clips + clips.yaml
    │   ├── voice_memos/         # spoken letters + memos.yaml
    │   └── sorry/               # apology-mode memos
    ├── jokes/                   # joke YAML banks (corpora)
    │   └── *.yaml
    └── quiz/                    # quiz pack YAMLs
        └── *.yaml
```

Subdirectories that need git tracking but are empty use `.gitkeep`. Drop your
binary media files into the relevant directory and reference them from the
metadata YAMLs (`clips.yaml`, `memos.yaml`, etc.).

## `pack.yaml` schema

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | string | yes | Stable identifier, kebab-case (e.g., `astha-birthday`). Must match the directory name. |
| `display_name` | string | yes | Human-readable name shown in logs and UI. |
| `date_rule` | object | yes | When the pack is active. See "Date rules" below. |
| `trigger.auto_midnight` | bool | yes | If true, the pack activates automatically at 00:00 on its day. If false, activation requires a manual trigger (voice intent or app button). |
| `trigger.manual_phrases` | list[string] | yes | Example phrases the NLU intent classifier learns to map to `event_trigger`. NOT regex-matched — these are training examples. Need at least 3. |
| `features` | list[string] | yes | Feature names this pack enables. Each name must correspond to a registered feature in the assistant (see "Feature registration"). |
| `first_year_only` | object | no | Year-1 only content. The most common field is `intro_script`, a path (relative to pack root) to an intro-runner YAML. |

## Date rules

`date_rule` supports three modes — pick exactly one:

1. **Yearly recurrence** — annual fixed-date events (birthdays, Christmas, etc.):
   ```yaml
   date_rule:
     recurs: yearly
     month: 5     # 1-12
     day: 14      # 1-31
   ```
2. **One-time** — anchored to a specific year (a one-off launch, a wedding):
   ```yaml
   date_rule:
     one_time: 2026-05-14
   ```
3. **Range** — multi-day windows (Diwali week, holidays):
   ```yaml
   date_rule:
     range_start: 2026-11-01
     range_days: 5
   ```

Lunar / movable-feast dates are **not** supported yet (Diwali, Eid, Easter
shift each year). Those will arrive with a lookup table when we need them.

## Adding a new pack

Example: a Diwali pack.

1. `mkdir events/diwali`
2. Create `events/diwali/pack.yaml`:
   ```yaml
   id: diwali
   display_name: "Diwali"
   date_rule:
     range_start: 2026-11-01
     range_days: 5
   trigger:
     auto_midnight: true
     manual_phrases:
       - "vesper, diwali shuru"
       - "vesper, light the diyas"
       - "vesper, happy diwali"
   features:
     - diya_avatar
     - festive_playlist
   ```
3. Drop in `theme/tokens.json` (warm gold palette), media as needed, etc.
4. Restart the assistant (or call `event_manager.reload()`). The pack is live.

The same flow works for Christmas, anniversaries, or any new occasion — copy
an existing pack as a template, swap the date rule and feature list, and add
content.

## Feature registration

The strings in `features:` are looked up in a registry inside the assistant.
A feature like `confetti` corresponds to a backend handler + dashboard
component that knows how to react when the pack is active. Adding a feature
to `features:` does not implement it — it just *enables* an already-built one
for this pack.

To add a brand-new feature: build the handler in the assistant codebase, add
it to the feature registry, and reference it by name from any pack that
should use it. The pack itself stays declarative.

## Cross-references

- [`jarvis/BIRTHDAY_ROADMAP.md`](../../BIRTHDAY_ROADMAP.md) — phased plan,
  acceptance criteria for every feature, and the master schedule.
- [`core/event_manager.py`](../core/event_manager.py) — the runtime that
  reads `pack.yaml`, evaluates date rules, and exposes the active pack
  to the rest of the assistant.
- [`tests/test_event_manager.py`](../tests/test_event_manager.py) — unit
  tests for the manager. Run via `python tests/runner.py --suite event_manager`.
