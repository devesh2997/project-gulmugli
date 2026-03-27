# Dashboard UI Redesign — Design Spec

**Date:** 2026-03-27
**Status:** Approved
**Scope:** Complete visual and architectural redesign of the Jarvis assistant dashboard

## Context

The current dashboard is a functional React + Vite + Tailwind app with WebSocket-driven state sync. It uses a dark glassmorphism aesthetic with cyan accents and a card-based layout showing all panels simultaneously. The redesign transforms it into an ultra-minimal, bedside-friendly ambient display that is contextually reactive and personality-driven.

## Design Principles

1. **Ultra-minimal by default, reactive on demand** — the idle screen shows only the avatar and time. Everything else appears contextually and leaves when done.
2. **Adaptive** — colors shift by time of day and personality. The UI adapts to its environment.
3. **Lego architecture** — every component is self-contained, composable, and configurable via tokens. No hardcoded visual values. All tokens are updatable at runtime via the assistant.
4. **AI-controllable** — the LLM can update any visual token, trigger transitions, and control UI state. The dashboard is an extension of the assistant, not a separate app.
5. **Personality is identity** — each personality has its own avatar style, color accent, and expressive behavior. Switching personalities is a theatrical moment, not a dropdown change.

---

## 1. Screen Architecture

Three stacked layers, not side-by-side panels:

### Canvas Layer (always visible)
- Full-screen background with adaptive color gradient
- Functions as ambient light in the room
- Gradient shifts warm→cool based on time of day
- Personality tints the base gradient

### Avatar Layer (always visible)
- Centered avatar (personality-specific)
- Time display directly below
- Tiny status dot (top-right corner) for connection state
- This is the resting state — nothing else competes

### Context Layer (appears/disappears)
- Intent badges float in from edges during actions
- Now-playing pill sits at bottom when music plays
- Panels slide in via gesture (swipe up/left/right)
- Empty by default — elements earn screen time by being relevant

### Navigation Model
| Touch Gesture | Keyboard/Mouse Equivalent | Action |
|---------------|--------------------------|--------|
| Idle | Idle | Canvas + Avatar + Time only |
| Active interaction | Active interaction | Intent badges + contextual pills animate in |
| Swipe up | `↑` arrow or scroll up | Transcript/conversation history slides up |
| Swipe left | `←` arrow | Settings/controls panel |
| Swipe right | `→` arrow | Lights/smart home controls |
| Tap now-playing pill | Click pill | Expands to full music controls |
| Tap expanded controls | Click outside or `Esc` | Collapses back to pill after 5s idle |
| Swipe down / tap outside | `↓` arrow or `Esc` | Dismiss any open panel |

All gestures have keyboard and mouse equivalents for desktop development and non-touch screens.

---

## 2. Adaptive Color System

### Time-of-Day Palettes

| Period | Hours | Base Palette | Orb Glow | Rationale |
|--------|-------|-------------|----------|-----------|
| Morning | 6am–12pm | Soft teal + muted sky blue | Cool, crisp | Waking energy |
| Afternoon/Evening | 12pm–9pm | Warm gold + amber | Rich, warm | Active hours |
| Night | 9pm–6am | Deep lavender + muted rose | Dim, barely there | Sleep-friendly |

Transitions between periods are gradual. A `useTimeOfDay` hook recalculates palette values every 60 seconds and updates CSS variables via the `TokenProvider`. The interpolation is linear between the two nearest period palettes, using the current time's position within the transition window. This updates ~20 CSS variables once per minute — negligible performance cost.

### Personality Accents

| Personality | Accent Color | Tint Effect |
|-------------|-------------|-------------|
| Jarvis | Neutral gold | Closest to base palette |
| Devesh | Cyan-teal | Pulls cooler, more digital |
| Girlfriend | Rose-pink | Pulls warmer, softer |
| Chandler | Warm orange | Slightly more saturated, playful |

Personality and time-of-day combine multiplicatively. "Girlfriend at night" = deep rose-lavender. "Devesh in the morning" = teal-cyan.

### Night Mode Specifics
- All UI element opacity drops to ~30-40% of daytime values
- Orb breathing slows (6s cycle vs 4s during day)
- Intent badges are dimmer and smaller
- No white text — everything tinted with the palette
- Screen brightness configurable via token

---

## 3. Intent Badges & Reactive UI

### Intent Badge Flow

1. Assistant classifies intents → sends `{type: "intents", intents: [{id, label, icon, status}]}` via WebSocket
2. All badges appear simultaneously as small pills below the orb (parallel burst)
3. Each pill shows: icon + short label + status indicator (spinning = processing, check = done, x = failed)
4. Backend streams `{type: "intent_update", id, status}` as each resolves
5. Resolved badges animate to checkmark, fade out after 2 seconds
6. Long-running intents pulse subtly while active
7. Failed intents flash red briefly, transcript gets the detail

### Now-Playing Pill
- Appears at screen bottom when music starts
- Compact: album art thumbnail (if available) + scrolling song title
- When no album art: music note icon in the personality's accent color as fallback
- Tap to expand into full controls (play/pause, skip, progress bar, volume)
- Tap again or 5s idle to collapse
- Absent when no music — clean screen

### Other Contextual Pills
- Lights changed → bulb pill with color indicator, fades after 3s
- Timer set → timer pill persists until completion
- Error → red pill, fades after 3s
- All pills are the same `Pill` component with different config

---

## 4. Avatar System

### Two Independent Axes

**State** (what it's doing): idle, listening, thinking, speaking, sleeping
**Mood** (how it's feeling): neutral, happy, sad, shy, playful, sarcastic, romantic, surprised, gotcha

These compose — "speaking + shy" or "thinking + playful." State drives structural animation (pulse, eye openness). Mood drives expressive overlay (blush, smirk, brow angle).

**V1 scoping:** Mood tagging from the LLM is deferred to v2. For v1, mood defaults to `neutral` for all responses. The avatar components will accept a `mood` prop from day one so no refactoring is needed when mood tagging is added. The LLM prompt modifications and response parsing for mood extraction will be specced separately.

### Four Avatar Types

#### Jarvis — Abstract Orb
- No face. Pure energy sphere with layered radial gradients
- State via: scale, pulse speed, glow intensity, rotation
- Thinking: slow rotation + warm color shift. Speaking: rhythmic pulse. Idle: gentle breathing
- The "default AI" feel

#### Devesh — Pixel Entity
- 32×32 pixel grid rendered as SVG rects with `image-rendering: pixelated`
- Chunky, deliberate, clearly digital
- State via: pixel position shifts (brows up/down), opacity changes, color shifts
- Transitions have "rendering" stagger — pixels cascade like a screen refreshing
- Most playful, most "constructed"

#### Girlfriend — Light Strokes
- Thin SVG strokes (arcs, lines) + radial glow halos for emotion
- State via: stroke morph (path animation), glow color/intensity, ambient light washes
- Blush = pink radial glow on cheeks. Thinking = warm forehead glow. Listening = ear glows
- Most ethereal, most bedroom-friendly

#### Chandler — Line Caricature
- Minimal line art capturing recognizable Chandler features: distinctive hair, slight smirk, expressive eyebrows
- More detail than other faces but still just strokes — like a quick sketch
- State via: exaggerated expressions (eye roll for sarcasm, one eyebrow raise for wit)
- Leans most "human" in avatar style, matching the character

#### Sleeping State (all avatars)
- Triggered when wake word detection is paused or via explicit "sleep" command
- All avatars: opacity drops to ~20%, breathing slows to 8s cycle
- Pixel Entity: pixels dim to near-invisible, only a few "status" pixels faintly glow
- Light Strokes: all strokes fade to ~10% opacity, glows nearly invisible
- Abstract Orb: contracts slightly, glow reduced to bare minimum
- Line Caricature: lines thin and fade, like the sketch is disappearing
- Any voice or tap interaction triggers a "wake up" animation (reverse of dimming)

### Avatar Selection Mechanism
The `Avatar` component reads the current `personality_id` from the `TokenProvider` context, looks up the `avatarType` field in the personality's token config, and renders the corresponding variant component (`AvatarPixel`, `AvatarLight`, `AvatarOrb`, or `AvatarCaricature`). This mapping is defined in `personalities.json`.

### Shared Behavior
- All respond to the same state machine
- All have `breathe` animation at rest (scale/opacity micro-pulse)
- All accept theme colors from the adaptive color system
- All implement the same component interface: `render(size, state, mood, theme)`

---

## 5. Personality Switch Transition

**"Dissolve and Reform"** — ~1.8 seconds total

### Sequence

1. **Trigger** (0ms) — voice command or UI tap
2. **Dissolve** (0–600ms) — current avatar breaks apart:
   - Pixel Entity: pixels scatter outward with random drift, fade to 0
   - Light Strokes: strokes break into segments that drift apart, glows dim
   - Abstract Orb: sphere contracts to a point, glow fades
   - Line Caricature: lines unravel from endpoints inward, like being erased
3. **Dark pause** (600–1000ms) — just the canvas gradient. Subtle shimmer in new personality's accent color begins at center
4. **Reform** (1000–1800ms) — new avatar assembles:
   - Pixel Entity: pixels rain in from random positions, snap to grid
   - Light Strokes: strokes draw themselves from center outward, glows bloom
   - Abstract Orb: point expands to sphere, glow pulses outward
   - Line Caricature: lines sketch themselves in quick strokes, like being drawn live
5. **Color shift** (overlapping steps 2–4) — canvas gradient and all tokens cross-fade to new personality's palette throughout

---

## 6. Component Architecture (Lego System)

### Token Hierarchy

```
tokens/
  time.json          — time-of-day palettes (morning/afternoon/night base colors)
  personalities.json — per-personality accent, tint, avatar config, mood defaults
  animation.json     — timing, easing, spring configs
  layout.json        — sizes, spacing, breakpoints
  ui.json            — badge styles, pill styles, opacity levels
```

Token files live in `dashboard/src/tokens/` and are bundled at build time as default values. At runtime, the `TokenProvider` holds all tokens in React state. The backend can override any token value via the `token_update` WebSocket message, which updates the provider state and syncs to CSS variables. On page refresh, tokens reset to bundled defaults unless the backend re-sends overrides (which it does on WebSocket connect via the existing sync mechanism).

#### Representative Token Schemas

**`time.json`** — three palettes, each with the CSS variable names they map to:
```json
{
  "morning": {
    "hours": [6, 12],
    "canvas_gradient_start": "#0a0d0d",
    "canvas_gradient_end": "#080c0b",
    "accent_primary": "#2dd4bf",
    "accent_glow": "#0ea5e9",
    "text_primary_opacity": 0.7,
    "orb_breathe_duration": "4s"
  },
  "afternoon": { "hours": [12, 21], "..." : "..." },
  "night": { "hours": [21, 6], "..." : "..." }
}
```

**`personalities.json`** — per-personality config:
```json
{
  "jarvis": {
    "avatarType": "orb",
    "accent": "#c99568",
    "tint": "neutral",
    "glow_color": "#c9956830",
    "mood_default": "neutral"
  },
  "devesh": {
    "avatarType": "pixel",
    "accent": "#2dd4bf",
    "tint": "cool",
    "glow_color": "#2dd4bf30",
    "mood_default": "neutral"
  }
}
```

**`animation.json`** — timing tokens:
```json
{
  "orb": { "breathe": { "duration": "4s", "scale_range": [0.97, 1.03] } },
  "pill": { "enter_duration": "300ms", "exit_duration": "200ms", "resolve_delay": "2000ms" },
  "transition": { "dissolve": "600ms", "pause": "400ms", "reform": "800ms" },
  "spring": { "stiffness": 200, "damping": 20 }
}
```

### Component Inventory

| Component | Purpose | Reusable in |
|-----------|---------|-------------|
| `Avatar` | Renders personality-specific avatar | Center of idle screen |
| `AvatarPixel` | Pixel grid variant | Avatar for Devesh |
| `AvatarLight` | Light strokes variant | Avatar for Girlfriend |
| `AvatarOrb` | Abstract orb variant | Avatar for Jarvis |
| `AvatarCaricature` | Line caricature variant | Avatar for Chandler |
| `Clock` | Time display with adaptive styling | Idle screen, status bar |
| `Pill` | Generic floating pill (icon + label + status) | Intent badges, now-playing compact, lights, timer |
| `PillCluster` | Manages multiple pills with layout/animation | Below avatar during actions |
| `NowPlayingExpanded` | Full music controls panel | Expanded from pill tap |
| `ProgressBar` | Seekable track progress | NowPlaying, timers |
| `TranscriptPanel` | Scrollable conversation history | Swipe-up overlay |
| `SettingsPanel` | Configurable settings grid | Swipe-left overlay |
| `LightsPanel` | Smart home controls | Swipe-right overlay |
| `SlidePanel` | Generic sliding overlay container | Wraps any panel |
| `Toggle` | On/off switch | Settings, lights |
| `Slider` | Range input with label | Volume, brightness, color temp |
| `ColorPicker` | Color selection for lights | Lights panel |
| `StatusDot` | Tiny connection/state indicator | Status bar, pills |
| `IconBadge` | Small icon with optional count | Intent types, notifications |
| `TransitionDissolver` | Dissolve/reform animation controller | Personality switch |
| `GestureHandler` | Swipe detection wrapper | Root layout |
| `TokenProvider` | React context for runtime token system | Root — wraps everything |

### Token Update Protocol

The assistant updates tokens via WebSocket:

```json
{
  "type": "token_update",
  "path": "animation.orb.breathe.duration",
  "value": "6s"
}
```

The `TokenProvider` receives this, updates its state, and all components reading that token re-render. CSS variables are synced automatically.

---

## 7. Backend Changes Required

### Streaming State Updates
- Intent classification results must stream to the UI as they're detected, not after all processing is complete
- Each intent status update (queued → processing → done/failed) sends a WebSocket message
- The LLM's mood tag must be included in response metadata

### Non-Blocking Parallel Execution
- Independent intents (e.g., "play music" and "set lights") should execute concurrently
- The UI shows both badges processing simultaneously
- Dependent intents still execute sequentially but the UI reflects the queue

### New WebSocket Message Types

The existing `theme` message type is **superseded** by `token_update`. The `theme` handler in `useAssistant.ts` should be removed and replaced with `token_update` handling in the `TokenProvider`. This is a breaking change — the old `set_theme()` Python method is replaced by `update_token()`.

#### Full Message Schemas

**`intents`** (server→client) — sent after classification, before execution:
```json
{
  "type": "intents",
  "intents": [
    {"id": "intent_1a2b", "intent_type": "music_play", "label": "Playing music", "icon": "music", "status": "queued"},
    {"id": "intent_2c3d", "intent_type": "light_control", "label": "Lights", "icon": "bulb", "status": "queued"}
  ]
}
```
Valid `status` values: `"queued"`, `"processing"`, `"done"`, `"failed"`
Valid `icon` values: `"music"`, `"bulb"`, `"brain"`, `"volume"`, `"personality"`, `"timer"`, `"search"`, `"general"`

**`intent_update`** (server→client) — sent as each intent progresses:
```json
{"type": "intent_update", "id": "intent_1a2b", "status": "done", "detail": "Playing Sajni by Arijit Singh"}
```
`detail` is optional — shown briefly in the badge before it fades.

**`mood`** (server→client) — deferred to v2, but schema defined now:
```json
{"type": "mood", "mood": "happy"}
```
Valid values: `"neutral"`, `"happy"`, `"sad"`, `"shy"`, `"playful"`, `"sarcastic"`, `"romantic"`, `"surprised"`, `"gotcha"`

**`token_update`** (server→client only for v1) — runtime token override:
```json
{"type": "token_update", "path": "animation.orb.breathe.duration", "value": "6s"}
```
Client-to-server token updates are deferred to v2 (when the settings panel can modify tokens). For v1, all token updates originate from the backend/assistant.

**`gesture`** (client→server) — UI interaction events:
```json
{"type": "gesture", "gesture": "swipe_up", "target": null}
{"type": "gesture", "gesture": "tap", "target": "now_playing_pill"}
```
Valid `gesture` values: `"swipe_up"`, `"swipe_down"`, `"swipe_left"`, `"swipe_right"`, `"tap"`, `"long_press"`

### New Python FaceUI Methods

```python
def send_intents(self, intents: list[dict]) -> None: ...
def update_intent(self, intent_id: str, status: str, detail: str = None) -> None: ...
def set_mood(self, mood: str) -> None: ...  # v2
def update_token(self, path: str, value: Any) -> None: ...
```

### V1 Backend Scoping: Sequential with Streaming

For v1, intent execution remains **sequential** (the existing `for` loop), but each step now streams status updates to the UI via `send_intents()` and `update_intent()`. This gives the user visibility into what's happening without requiring the parallel execution refactor. Parallel execution is deferred to v2 — it requires careful handling of shared state (mpv player, Tuya connections) and is a separate architectural change.

---

## 8. Responsive Behavior

The layered architecture is inherently full-screen, which simplifies responsiveness. Key adaptations:

| Screen Size | Avatar Size | Clock Size | Pill Size | Panels |
|-------------|-------------|------------|-----------|--------|
| Compact (<640px, 3.5"–5") | `clamp(80px, 30vw, 120px)` | 24px | Small, single line | Full-screen overlays |
| Medium (640–900px, 7") | `clamp(120px, 20vw, 180px)` | 32px | Standard | Slide-in from edges |
| Large (>900px, desktop) | `clamp(160px, 15vw, 260px)` | 42px | Standard | Slide-in from edges |

The `PillCluster` wraps to multiple rows on compact screens. `SlidePanel` overlays are always full-width on compact, 60% width on medium/large. Avatar and clock sizes use `clamp()` for fluid scaling within each tier — no jarring breakpoint jumps.

---

## 9. What This Spec Does NOT Cover

- Speaker recognition for auto personality switching (future)
- AudioOutputProvider implementation (separate workstream)
- Hardware-specific optimizations for Jetson/Pi (addressed during implementation if needed)
- Chandler avatar reference photo sourcing (done during implementation)
- Specific settings panel contents (designed when settings features are built)
- Lights panel UX (designed when lights control iteration begins)
- LLM mood tagging — deferred to v2, avatars default to `neutral` mood
- Parallel intent execution — deferred to v2, v1 uses sequential with streaming status
- Client-to-server token updates — deferred to v2, v1 is server-to-client only
