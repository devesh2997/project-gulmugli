# Dashboard UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the Jarvis dashboard from a card-based layout into an ultra-minimal, bedside-friendly ambient display with personality-driven avatars, adaptive colors, and contextually reactive intent badges.

**Architecture:** Layered full-screen UI (canvas → avatar → context) driven by a runtime token system. Four avatar variants per personality, all configurable via JSON tokens updatable at runtime over WebSocket. Backend streams intent status updates so the UI accurately reflects assistant activity.

**Tech Stack:** React 19, TypeScript, Vite 8, Tailwind CSS 4, Framer Motion 12, WebSocket (existing), SVG for avatars, CSS custom properties for theming.

**Spec:** `docs/superpowers/specs/2026-03-27-dashboard-ui-redesign-design.md`

---

## File Structure

### New Files

```
jarvis/assistant/dashboard/src/
├── tokens/
│   ├── time.json                    — Time-of-day color palettes
│   ├── personalities.json           — Per-personality accent, avatar type, glow
│   ├── animation.json               — Timing, easing, spring configs
│   ├── layout.json                  — Sizes, spacing, breakpoints
│   └── ui.json                      — Pill styles, opacity levels
├── context/
│   └── TokenProvider.tsx            — React context for runtime token system + CSS var sync
├── hooks/
│   ├── useTimeOfDay.ts              — Calculates interpolated palette every 60s
│   └── useGesture.ts                — Touch swipe + keyboard navigation detection
├── components/
│   ├── Canvas.tsx                   — Full-screen adaptive gradient background
│   ├── Clock.tsx                    — Centered time display with adaptive styling
│   ├── Avatar.tsx                   — Router: reads personality → renders correct variant
│   ├── avatars/
│   │   ├── AvatarOrb.tsx            — Jarvis: abstract energy sphere
│   │   ├── AvatarPixel.tsx          — Devesh: 32×32 pixel grid face
│   │   ├── AvatarLight.tsx          — Girlfriend: light strokes + glow halos
│   │   └── AvatarCaricature.tsx     — Chandler: line caricature
│   ├── Pill.tsx                     — Generic floating pill (icon + label + status)
│   ├── PillCluster.tsx              — Manages multiple pills with layout/animation
│   ├── NowPlayingPill.tsx           — Compact now-playing indicator (pill variant)
│   ├── NowPlayingExpanded.tsx       — Full music controls panel
│   ├── SlidePanel.tsx               — Generic sliding overlay container
│   ├── StatusDot.tsx                — Tiny connection/state indicator
│   ├── ProgressBar.tsx              — Reusable seekable progress bar
│   ├── SettingsPanel.tsx            — Placeholder settings panel (swipe-left target)
│   ├── LightsPanel.tsx              — Placeholder lights control panel (swipe-right target)
│   └── TransitionDissolver.tsx      — Dissolve/reform animation controller
```

**Note:** No new npm dependencies needed — React 19, Framer Motion 12, and Tailwind CSS 4 are already installed. `resolveJsonModule` is already `true` in the existing `tsconfig.json`. The existing `useWindowSize.ts` hook is no longer needed (the new layout is full-screen with `clamp()` scaling, no breakpoint-dependent rendering logic) but can be kept for now and removed during cleanup.

### Modified Files

```
jarvis/assistant/dashboard/src/
├── App.tsx                          — Complete rewrite: layered architecture
├── types/assistant.ts               — Add new message types (intents, intent_update, mood, token_update, gesture)
├── hooks/useAssistant.ts            — Handle new message types, remove theme handler
├── index.css                        — Replace CSS variables with token-driven system
├── components/
│   ├── Transcript.tsx               — Adapt for SlidePanel overlay (was always-visible)
│   └── NowPlaying.tsx               — Split into NowPlayingPill + NowPlayingExpanded

jarvis/assistant/ui/
├── server.py                        — Add send_intents(), update_intent(), update_token() methods
├── actions.py                       — Add gesture handling
```

### Removed / Replaced

```
jarvis/assistant/dashboard/src/components/
├── StatusBar.tsx                    — Replaced by minimal StatusDot + Clock (extracted parts)
├── Orb.tsx                          — Replaced by Avatar system (AvatarOrb is the evolution)
```

---

## Phase 1: Foundation

### Task 1: Token JSON Files

**Files:**
- Create: `jarvis/assistant/dashboard/src/tokens/time.json`
- Create: `jarvis/assistant/dashboard/src/tokens/personalities.json`
- Create: `jarvis/assistant/dashboard/src/tokens/animation.json`
- Create: `jarvis/assistant/dashboard/src/tokens/layout.json`
- Create: `jarvis/assistant/dashboard/src/tokens/ui.json`

- [ ] **Step 1: Create `time.json`** with three palettes (morning/afternoon/night), each containing: `hours` range, `canvas_gradient_start`, `canvas_gradient_end`, `accent_primary`, `accent_glow`, `text_primary_opacity`, `orb_breathe_duration`. Use the colors from the spec: morning = teal/sky, afternoon = gold/amber, night = lavender/rose.

- [ ] **Step 2: Create `personalities.json`** with four entries (jarvis, devesh, girlfriend, chandler), each containing: `avatarType` (orb/pixel/light/caricature), `accent`, `tint` (neutral/cool/warm), `glow_color`, `mood_default`. Use colors from spec.

- [ ] **Step 3: Create `animation.json`** with sections: `orb` (breathe duration, scale range), `pill` (enter/exit duration, resolve delay), `transition` (dissolve/pause/reform durations), `spring` (stiffness, damping).

- [ ] **Step 4: Create `layout.json`** with sections: `avatar_size` (compact/medium/large clamp values), `clock_size` (per breakpoint), `pill` (height, padding, gap), `panel` (width per breakpoint).

- [ ] **Step 5: Create `ui.json`** with sections: `pill` (background, border, border_radius, icon_size), `status_dot` (size, colors per connection state), `night_mode` (opacity_multiplier, breathe_slowdown).

- [ ] **Step 6: Commit** — `git commit -m "feat(dashboard): add token JSON files for adaptive theming"`

---

### Task 2: TypeScript Types Update

**Files:**
- Modify: `jarvis/assistant/dashboard/src/types/assistant.ts`

- [ ] **Step 1: Add new message type interfaces.** Add `IntentsMessage`, `IntentUpdateMessage`, `MoodMessage`, `TokenUpdateMessage`, `GestureMessage` types matching the spec JSON schemas. Add `IntentBadge` type with fields: `id`, `intent_type`, `label`, `icon`, `status`. Add `AssistantMood` type as union of valid mood strings. Add `AvatarType` as `'orb' | 'pixel' | 'light' | 'caricature'`.

- [ ] **Step 2: Update `ServerMessage` union** to include the new message types. Remove `ThemeMessage` (superseded by `token_update`).

- [ ] **Step 3: Update `AssistantStore`** to include: `intents: IntentBadge[]`, `mood: AssistantMood`.

- [ ] **Step 4: Update `AssistantActions`** to include: `sendGesture(gesture: string, target?: string): void`.

- [ ] **Step 5: Commit** — `git commit -m "feat(dashboard): add TypeScript types for intents, mood, tokens, gestures"`

---

### Task 3: TokenProvider Context

**Files:**
- Create: `jarvis/assistant/dashboard/src/context/TokenProvider.tsx`

- [ ] **Step 1: Create context shell.** Import all 5 token JSON files. Create a `TokenContext` with `React.createContext`. Create `TokenProvider` component that holds merged tokens in `useState`. Export `useTokens()` convenience hook.

- [ ] **Step 2: Add `getToken` helper.** Implement dot-notation path resolution: `getToken("animation.orb.breathe.duration")` → walks the nested state object → returns `"4s"`. Handle missing paths gracefully (return `undefined`).

- [ ] **Step 3: Add `updateToken` function.** Accepts `(path: string, value: any)`. Deep-clones state, sets the nested value, calls `setState`. This is the function that `useAssistant` will call when it receives a `token_update` WebSocket message — pass it as a prop or expose via context.

- [ ] **Step 4: Add CSS variable sync.** In a `useEffect` that depends on the token state, iterate the flattened token tree and set CSS custom properties on `document.documentElement.style`. Convention: `animation.orb.breathe.duration` → `--animation-orb-breathe-duration`. Only sync leaf values (strings/numbers).

- [ ] **Step 5: Add personality accessor.** Provide `currentPersonality` and `setPersonality(id)` in context. When personality changes, merge that personality's tokens from `personalities.json` into the active set and re-sync CSS vars.

- [ ] **Step 6: Wire to useAssistant.** The `useAssistant` hook cannot consume context directly (it's a hook, not a component). Solution: in `App.tsx`, read `updateToken` from `useTokens()` and pass it to `useAssistant` as a callback parameter. Update `useAssistant` to accept an optional `onTokenUpdate` callback and call it when `token_update` messages arrive.

- [ ] **Step 4: Commit** — `git commit -m "feat(dashboard): add TokenProvider context with CSS variable sync"`

---

### Task 4: useTimeOfDay Hook

**Files:**
- Create: `jarvis/assistant/dashboard/src/hooks/useTimeOfDay.ts`

- [ ] **Step 1: Create hook.** Read `time.json` tokens from TokenProvider context. Every 60 seconds (via `setInterval`), determine current time period and calculate linear interpolation between adjacent palettes. Return the interpolated palette values.

- [ ] **Step 2: Add interpolation logic.** For color strings, parse hex to RGB, interpolate each channel linearly, convert back to hex. For numbers (opacity), interpolate directly. For strings (duration), parse numeric part, interpolate, re-append unit.

- [ ] **Step 3: Add CSS var updates.** On each recalculation, call `updateToken` from TokenProvider for each interpolated value. This triggers the CSS var sync automatically.

- [ ] **Step 4: Commit** — `git commit -m "feat(dashboard): add useTimeOfDay hook for adaptive color transitions"`

---

### Task 5: Update useAssistant Hook

**Files:**
- Modify: `jarvis/assistant/dashboard/src/hooks/useAssistant.ts`

- [ ] **Step 1: Add intent state management.** Add `intents` array and `mood` string to the hook's state. Handle `intents` message: replace entire intents array. Handle `intent_update` message: find intent by ID, update its status and optional detail. Handle `mood` message: update mood state.

- [ ] **Step 2: Replace theme handler with token_update.** Remove the `theme` case from `handleMessage`. Add `token_update` case that calls `updateToken(msg.path, msg.value)` on the TokenProvider context (will need to accept context ref or callback as parameter).

- [ ] **Step 3: Add gesture sending.** Add `sendGesture(gesture, target?)` to the actions object. Sends `{type: "gesture", gesture, target}` over WebSocket.

- [ ] **Step 4: Verify existing handlers still work.** Ensure `state`, `personality`, `transcript`, `now_playing`, `music_paused`, `music_stopped`, `lights`, `volume`, `personalities` messages all still function correctly.

- [ ] **Step 5: Commit** — `git commit -m "feat(dashboard): update useAssistant for intents, token_update, gestures"`

---

### Task 6: Backend WebSocket Protocol Update

**Files:**
- Modify: `jarvis/assistant/ui/server.py`

- [ ] **Step 1: Add `send_intents` method.** Accepts a list of intent dicts, broadcasts `{type: "intents", intents: [...]}` to all clients. Thread-safe via existing `_broadcast` + `asyncio.run_coroutine_threadsafe` pattern. Also initialize `self._token_overrides = {}` in `__init__`.

- [ ] **Step 2: Add `update_intent` method.** Accepts `intent_id`, `status`, optional `detail`. Broadcasts `{type: "intent_update", id, status, detail}`.

- [ ] **Step 3: Add `update_token` method.** Accepts `path` string and `value` any. Broadcasts `{type: "token_update", path, value}`. Store in `self._token_overrides` dict so they can be re-sent on client connect.

- [ ] **Step 4: Update `_sync_state` (on-connect handler).** After sending existing state (state, personality, volume, etc.), also send any stored token overrides.

- [ ] **Step 5: Expand message routing in `_handle_client`.** The current code (line ~240) checks `"action" in data` for UI actions. Add a second check: `if data.get("type") == "gesture"`, route to `on_action` callback with the gesture data. This handles the new `type`-based message format alongside the existing `action`-based format.

- [ ] **Step 6: Add `set_mood` stub (v2).** Add method signature `def set_mood(self, mood: str) -> None: pass` with a TODO comment. This satisfies the spec's "schema defined now" requirement without implementing v2 functionality.

- [ ] **Step 7: Commit** — `git commit -m "feat(backend): add intent streaming and token update to FaceUI WebSocket"`

---

## Phase 2: The Idle Screen

### Task 7: Canvas Component

**Files:**
- Create: `jarvis/assistant/dashboard/src/components/Canvas.tsx`

- [ ] **Step 1: Create Canvas.** A full-screen `div` positioned fixed behind everything (`z-index: 0`). Background is a CSS gradient using `var(--canvas-gradient-start)` and `var(--canvas-gradient-end)` — these are set by the `useTimeOfDay` hook via TokenProvider.

- [ ] **Step 2: Add personality tint overlay.** A second layer (absolute positioned) with a radial gradient using the personality's `glow_color` at ~5% opacity, centered. This provides the personality tint on top of the time-of-day base.

- [ ] **Step 3: Commit** — `git commit -m "feat(dashboard): add Canvas component with adaptive gradient"`

---

### Task 8: Clock Component

**Files:**
- Create: `jarvis/assistant/dashboard/src/components/Clock.tsx`

- [ ] **Step 1: Create Clock.** Displays time (HH:MM format) and day name. Updates every second via `setInterval`. Reads font size from layout tokens. Color uses `var(--accent-primary)` at reduced opacity (~40%). Day name is uppercase, smaller, with wide letter-spacing.

- [ ] **Step 2: Add responsive sizing.** Read `clock_size` from layout tokens for compact/medium/large. Use the value directly as CSS `font-size`.

- [ ] **Step 3: Commit** — `git commit -m "feat(dashboard): add Clock component with adaptive styling"`

---

### Task 9: StatusDot Component

**Files:**
- Create: `jarvis/assistant/dashboard/src/components/StatusDot.tsx`

- [ ] **Step 1: Create StatusDot.** Tiny circle (6px) positioned absolute top-right. Color from `ui.json` status_dot tokens: green-ish tint for connected, dim for disconnected. Pulses gently when connected.

- [ ] **Step 2: Commit** — `git commit -m "feat(dashboard): add StatusDot component"`

---

### Task 10: AvatarOrb (Jarvis)

**Files:**
- Create: `jarvis/assistant/dashboard/src/components/avatars/AvatarOrb.tsx`

- [ ] **Step 1: Create AvatarOrb.** Port the existing `Orb.tsx` logic but read all values from tokens instead of hardcoded constants. Accept props: `size`, `state`, `mood`, `theme` (colors from TokenProvider). Keep the 4-layer composition (outer glow, mid-ring, core, inner highlight).

- [ ] **Step 2: Update state configs.** Map each `AssistantState` to animation values (scale, opacity, glowOpacity, pulseSpeed, rotation) but read base values from `animation.json` tokens. The state configs become multipliers on token values rather than absolute numbers.

- [ ] **Step 3: Add sleeping state.** Opacity drops to ~20%, breathing slows to 8s, glow reduced to bare minimum. Contracts slightly.

- [ ] **Step 4: Add mood prop (no-op for orb).** Accept `mood` prop but ignore it — the orb has no facial features to express mood. This satisfies the shared interface.

- [ ] **Step 5: Commit** — `git commit -m "feat(dashboard): add AvatarOrb component for Jarvis personality"`

---

### Task 11: AvatarPixel (Devesh)

**Files:**
- Create: `jarvis/assistant/dashboard/src/components/avatars/AvatarPixel.tsx`

- [ ] **Step 1a: Define idle state pixel data.** Create a `pixelFaces.ts` data file. Define a type `PixelData = {x: number, y: number, opacity: number}[]` per feature. Map each facial feature (left_brow, right_brow, left_eye, right_eye, nose, mouth) to pixel positions for the `idle` state. Use the 32×32 grid coordinates from the brainstorm mockups.

- [ ] **Step 1b: Define remaining state pixel data.** Add `listening` (attentive brows, open eyes), `thinking` (raised brows, wide eyes, O mouth), `speaking` (animated mouth, normal eyes), `sleeping` (only status pixels visible). Each state is a separate entry in the data map.

- [ ] **Step 2: Create renderer.** Render an SVG with `viewBox="0 0 32 32"` and `image-rendering: pixelated`. Map each active pixel to a `<rect>` element with `width="1" height="1"`. Color from personality accent token.

- [ ] **Step 3: Add state transitions.** Use Framer Motion `animate` on each rect's `x`, `y`, and `opacity` props. Add staggered delay (cascading pixel effect) using index-based `transition.delay`.

- [ ] **Step 4: Add mood overlays.** For `shy`/`happy`: add blush pixels (pink color) at cheek positions. For `surprised`: widen eye pixel blocks. For `gotcha`: asymmetric brow + smirk mouth. Store mood pixel overlays as separate data arrays that merge with state data.

- [ ] **Step 5: Add sleeping state.** All pixels fade to ~15% opacity except 2-3 "status" pixels that pulse dimly.

- [ ] **Step 6: Commit** — `git commit -m "feat(dashboard): add AvatarPixel component for Devesh personality"`

---

### Task 12: AvatarLight (Girlfriend)

**Files:**
- Create: `jarvis/assistant/dashboard/src/components/avatars/AvatarLight.tsx`

- [ ] **Step 1a: Define idle state stroke data.** Create a `lightFaces.ts` data file. Define SVG path `d` strings and glow parameters for each facial feature in the `idle` state: eyebrow arcs, eye dashes + halo circles, nose line, mouth arc. Include stroke width and opacity per feature.

- [ ] **Step 1b: Define remaining state stroke data.** Add `listening` (raised brows, ear glow circles), `thinking` (higher brows, forehead glow, O-mouth ellipse), `speaking` (wider mouth arc, animated), `sleeping` (all faded to ~10% opacity).

- [ ] **Step 2: Create renderer.** Render SVG with face glow ellipse background, stroke features, and radial gradient halos around eyes. Use personality accent color for strokes, reduced opacity.

- [ ] **Step 3: Add state transitions.** Animate SVG path `d` attributes between states using Framer Motion's `motion.path`. Animate glow circle radii and opacities. Thinking = forehead glow circle, listening = ear glow circles on sides.

- [ ] **Step 4: Add mood overlays.** For `shy`: add pink radial gradient circles at cheek positions (blush). For `happy`: morph eye lines into upward crescents. For `romantic`: softer, warmer glow overall. Mood overlays are additional SVG elements that fade in/out.

- [ ] **Step 5: Add sleeping state.** All strokes fade to ~10% opacity, glows nearly invisible.

- [ ] **Step 6: Commit** — `git commit -m "feat(dashboard): add AvatarLight component for Girlfriend personality"`

---

### Task 13: AvatarCaricature (Chandler)

**Files:**
- Create: `jarvis/assistant/dashboard/src/components/avatars/AvatarCaricature.tsx`

- [ ] **Step 1a: Research Chandler reference.** Search for reference images. Identify the 4-5 most recognizable features: hair style, brow shape, smirk angle, jawline. Note the key proportions.

- [ ] **Step 1b: Design idle state SVG paths.** Create a `chandlerFaces.ts` data file. Encode the reference into ~15-20 SVG path elements for the idle/neutral expression. Keep strokes minimal — this is a line sketch, not a portrait.

- [ ] **Step 2: Create renderer.** Similar to AvatarLight but with more detail paths. Use personality accent color (warm orange). Strokes slightly thicker than Light variant for more presence.

- [ ] **Step 3: Add state transitions.** Thinking = one eyebrow raised (skeptical). Speaking = mouth opens, chin moves. Listening = both brows slightly up. Sleeping = eyes close (arcs flip downward).

- [ ] **Step 4: Add mood overlays.** For `sarcastic`: eye roll (pupils shift up), one-sided smirk. For `gotcha`: both brows raise, big grin. For `playful`: mischievous half-smile. Chandler's expressions should be the most exaggerated of all avatars.

- [ ] **Step 5: Add sleeping state.** Lines thin and fade, like the sketch disappearing.

- [ ] **Step 6: Commit** — `git commit -m "feat(dashboard): add AvatarCaricature component for Chandler personality"`

---

### Task 14: Avatar Router

**Files:**
- Create: `jarvis/assistant/dashboard/src/components/Avatar.tsx`

- [ ] **Step 1: Create Avatar router.** Read `currentPersonality` from TokenProvider context. Look up `avatarType` from `personalities.json` token. Render the corresponding variant: `orb` → `AvatarOrb`, `pixel` → `AvatarPixel`, `light` → `AvatarLight`, `caricature` → `AvatarCaricature`. Pass through `size`, `state`, `mood` props.

- [ ] **Step 2: Wrap in AnimatePresence.** When personality changes, the old avatar unmounts and new one mounts. This enables the dissolve/reform transition (Task 20).

- [ ] **Step 3: Commit** — `git commit -m "feat(dashboard): add Avatar router component"`

---

## Phase 3: Reactive Layer

### Task 15: Pill Component

**Files:**
- Create: `jarvis/assistant/dashboard/src/components/Pill.tsx`

- [ ] **Step 1: Create Pill.** A small rounded capsule with: optional icon (left), label text (center), status indicator (right). Read styling from `ui.json` pill tokens. Background is semi-transparent with glassmorphism blur. Uses Framer Motion for enter/exit animations (scale + fade).

- [ ] **Step 2: Add status indicator.** `queued` = dim dot, `processing` = spinning loader, `done` = checkmark that animates in, `failed` = X mark in red. Each is a small SVG icon.

- [ ] **Step 3: Add icon set.** Map icon names (`music`, `bulb`, `brain`, `volume`, `personality`, `timer`, `search`, `general`) to simple SVG icons. Keep each icon under 5 path elements — these are tiny.

- [ ] **Step 4: Commit** — `git commit -m "feat(dashboard): add Pill component with status indicators"`

---

### Task 16: PillCluster Component

**Files:**
- Create: `jarvis/assistant/dashboard/src/components/PillCluster.tsx`

- [ ] **Step 1: Create PillCluster.** Accepts an array of `IntentBadge` objects. Renders a flex-wrap container centered below the avatar. Uses `AnimatePresence` so pills animate in/out individually.

- [ ] **Step 2: Add auto-dismiss.** When a pill's status becomes `done`, start a 2-second timer, then remove it from the display (Framer Motion exit animation). Failed pills dismiss after 3 seconds.

- [ ] **Step 3: Add layout animation.** Use Framer Motion `layout` prop so remaining pills reflow smoothly when one exits.

- [ ] **Step 4: Commit** — `git commit -m "feat(dashboard): add PillCluster for intent badge management"`

---

### Task 17: NowPlayingPill (Compact)

**Files:**
- Create: `jarvis/assistant/dashboard/src/components/NowPlayingPill.tsx`

- [ ] **Step 1: Create compact pill.** Fixed at bottom center of screen. Wraps the `Pill` component with custom content: album art thumbnail (32px circle, or music note icon fallback from Pill's icon system) + song title (truncated, or scrolling marquee if long). This reuses Pill for the capsule shell and adds NowPlaying-specific content inside.

- [ ] **Step 2: Add tap-to-expand.** On click, calls a callback to switch to expanded view. Framer Motion `layoutId` shared with NowPlayingExpanded for smooth transition.

- [ ] **Step 3: Add enter/exit animation.** Slides up from bottom when music starts. Slides down when music stops. Uses `AnimatePresence`.

- [ ] **Step 4: Commit** — `git commit -m "feat(dashboard): add NowPlayingPill compact music indicator"`

---

### Task 18: NowPlayingExpanded

**Files:**
- Create: `jarvis/assistant/dashboard/src/components/NowPlayingExpanded.tsx`

- [ ] **Step 1: Port from existing NowPlaying.tsx.** Adapt the current `NowPlaying` component's controls (play/pause, skip, stop, progress bar, volume) but restyle with token-driven colors. Remove the card/panel styling — this is a floating overlay.

- [ ] **Step 2: Add auto-collapse.** After 5 seconds of no interaction, collapse back to pill view. Reset timer on any button press or seek interaction.

- [ ] **Step 3: Add shared layoutId.** Use Framer Motion `layoutId="now-playing"` shared with NowPlayingPill for the smooth expand/collapse morph.

- [ ] **Step 4: Commit** — `git commit -m "feat(dashboard): add NowPlayingExpanded with auto-collapse"`

---

## Phase 4: Navigation & Panels

### Task 19: useGesture Hook

**Files:**
- Create: `jarvis/assistant/dashboard/src/hooks/useGesture.ts`

- [ ] **Step 1: Create hook.** Detect touch swipe gestures (up/down/left/right) using `touchstart`/`touchmove`/`touchend` events. Minimum swipe distance threshold: 50px. Returns the detected gesture direction.

- [ ] **Step 2: Add keyboard equivalents.** Listen for arrow keys (↑↓←→) and Escape. Map to the same gesture callbacks.

- [ ] **Step 3: Add mouse drag support.** For desktop: detect mousedown + mousemove + mouseup with same distance threshold as touch.

- [ ] **Step 4: Send gesture to backend.** Call `actions.sendGesture()` from useAssistant when a gesture is detected, so the backend knows about navigation events.

- [ ] **Step 5: Commit** — `git commit -m "feat(dashboard): add useGesture hook for touch/keyboard/mouse navigation"`

---

### Task 20: SlidePanel Component

**Files:**
- Create: `jarvis/assistant/dashboard/src/components/SlidePanel.tsx`

- [ ] **Step 1: Create SlidePanel.** A generic overlay container that slides in from a specified direction (left/right/bottom). Uses Framer Motion for slide animation. Background has glassmorphism blur. Accepts `children` for content.

- [ ] **Step 2: Add dismiss behavior.** Clicking outside the panel, pressing Escape, or swiping in the dismiss direction closes it. Calls an `onClose` callback.

- [ ] **Step 3: Add responsive width.** Full-width on compact screens, 60% width on medium/large (from layout tokens).

- [ ] **Step 4: Commit** — `git commit -m "feat(dashboard): add SlidePanel generic overlay component"`

---

### Task 21: Adapt TranscriptPanel

**Files:**
- Modify: `jarvis/assistant/dashboard/src/components/Transcript.tsx`

- [ ] **Step 1: Wrap in SlidePanel.** The transcript is no longer always-visible. It lives inside a `SlidePanel` that slides up from the bottom. Keep the existing auto-scroll and message rendering logic.

- [ ] **Step 2: Restyle messages.** Replace card/glassmorphism message bubbles with minimal, soft-colored text. User messages in accent color, assistant messages in muted text color. No borders or backgrounds on individual messages.

- [ ] **Step 3: Commit** — `git commit -m "refactor(dashboard): adapt Transcript for SlidePanel overlay"`

---

### Task 22: ProgressBar Component

**Files:**
- Create: `jarvis/assistant/dashboard/src/components/ProgressBar.tsx`

- [ ] **Step 1: Create ProgressBar.** Reusable seekable progress bar. Props: `current` (seconds), `total` (seconds), `onSeek(position)` callback. Thin horizontal bar, fill color from accent token. Click/drag to seek.

- [ ] **Step 2: Commit** — `git commit -m "feat(dashboard): add reusable ProgressBar component"`

---

### Task 23: Placeholder Panels (Settings + Lights)

**Files:**
- Create: `jarvis/assistant/dashboard/src/components/SettingsPanel.tsx`
- Create: `jarvis/assistant/dashboard/src/components/LightsPanel.tsx`

- [ ] **Step 1: Create SettingsPanel placeholder.** A simple component inside a `SlidePanel` that shows "Settings — Coming Soon" text in muted accent color. This is the swipe-left target. Will be populated when settings features are built.

- [ ] **Step 2: Create LightsPanel placeholder.** Same pattern, "Lights Control — Coming Soon". Swipe-right target. Will be populated when lights control iteration begins.

- [ ] **Step 3: Commit** — `git commit -m "feat(dashboard): add placeholder Settings and Lights panels"`

---

## Phase 5: Personality Switch

### Task 24: TransitionDissolver

**Files:**
- Create: `jarvis/assistant/dashboard/src/components/TransitionDissolver.tsx`

- [ ] **Step 1: Create dissolve controller.** Wraps the `Avatar` component. When `personality` prop changes, triggers a 3-phase sequence: dissolve (600ms) → dark pause (400ms) → reform (800ms). During dissolve, applies a CSS class/Framer variant that triggers the current avatar's exit animation. During pause, renders nothing (just canvas). During reform, mounts the new avatar with its entrance animation.

- [ ] **Step 2: Add color shift.** During the transition, animate the canvas gradient from old personality's palette to new. Use the TokenProvider's `setPersonality()` during the dark pause so CSS vars update during the gap.

- [ ] **Step 3: Add shimmer effect.** During dark pause, render a subtle radial pulse in the new personality's accent color at center. This is a simple `motion.div` with a scale + opacity animation.

- [ ] **Step 4: Commit** — `git commit -m "feat(dashboard): add TransitionDissolver for personality switch animation"`

---

## Phase 6: App Layout & Integration

### Task 25: Rewrite App.tsx

**Files:**
- Modify: `jarvis/assistant/dashboard/src/App.tsx`
- Verify: `jarvis/assistant/dashboard/src/main.tsx` — no changes needed (it renders `<App />` in StrictMode, TokenProvider goes inside App)

- [ ] **Step 1: Replace layout.** Remove the existing 3-tier responsive grid layout with cards. Replace with the 3-layer stack: `Canvas` (fixed background), centered `Avatar` + `Clock` + `StatusDot`, and conditional context layer elements.

- [ ] **Step 2: Integrate TokenProvider.** Wrap the entire app in `<TokenProvider>`. Initialize with personality from `useAssistant` state.

- [ ] **Step 3: Wire useTimeOfDay.** Call the hook inside TokenProvider to start the 60-second palette recalculation loop.

- [ ] **Step 4: Wire useGesture.** Connect gesture detections to panel open/close state. `swipe_up` → open transcript, `swipe_left` → open settings (placeholder), `swipe_right` → open lights (placeholder). `swipe_down` or `Esc` → close any open panel.

- [ ] **Step 5: Wire intent badges.** Read `intents` from useAssistant state, pass to `PillCluster` positioned below the avatar.

- [ ] **Step 6: Wire now-playing.** Read `nowPlaying` from useAssistant. If music is playing, show `NowPlayingPill` at bottom. Manage expanded/collapsed state locally.

- [ ] **Step 7: Wire personality switch.** When `personality` changes in useAssistant state, the `TransitionDissolver` handles the animation automatically.

- [ ] **Step 8: Commit** — `git commit -m "feat(dashboard): rewrite App.tsx with layered architecture"`

---

### Task 26: Update index.css

**Files:**
- Modify: `jarvis/assistant/dashboard/src/index.css`

- [ ] **Step 1: Replace CSS variables.** Remove all existing `--bg-*`, `--accent-*`, `--border-*` etc. variables. Replace `:root` block with minimal defaults that the TokenProvider will override at runtime. Keep only structural CSS (body margin, font-family, box-sizing reset).

- [ ] **Step 2: Remove component-specific styles.** Delete `.glassmorphism`, `.card`, and other old design system classes. Components now use Tailwind classes and inline styles driven by tokens.

- [ ] **Step 3: Add utility animations.** Keep the `@keyframes` for `pulse-slow` and `breathing` but make them reference CSS variables for timing.

- [ ] **Step 4: Commit** — `git commit -m "refactor(dashboard): replace CSS variables with token-driven system"`

---

### Task 27: Backend Intent Streaming Integration

**Files:**
- Modify: `jarvis/assistant/ui/server.py` (already done in Task 6)
- Modify: `jarvis/assistant/ui/actions.py`
- Modify: `jarvis/assistant/main.py` (or `jarvis/assistant/core/intent_handler.py` / `jarvis/assistant/core/pipeline.py` — wherever intents are executed)

- [ ] **Step 1: Identify intent execution entry point.** Read `core/intent_handler.py` and `core/pipeline.py` to find where intents are classified and executed sequentially.

- [ ] **Step 2: Add intent streaming calls.** The `face_ui` instance is accessible via the `assistant` dict that's passed through `build_assistant()` in `main.py` — it's stored as `assistant["face_ui"]`. After classification in the intent handler, call `face_ui.send_intents(intents_list)` with all detected intents (status: "queued"). Before each intent executes, call `face_ui.update_intent(id, "processing")`. After each intent completes, call `face_ui.update_intent(id, "done", detail)` or `"failed"`.

- [ ] **Step 3: Generate intent IDs.** Use `uuid.uuid4().hex[:8]` for short unique IDs. Map intent types to icon names and human-readable labels.

- [ ] **Step 4: Test the flow.** Run the assistant, say "play Sajni and set lights to red." Verify that the dashboard shows two intent badges that resolve sequentially.

- [ ] **Step 5: Commit** — `git commit -m "feat(backend): stream intent status updates to dashboard"`

---

### Task 28: Remove Old Components

**Files:**
- Delete: `jarvis/assistant/dashboard/src/components/StatusBar.tsx`
- Delete: `jarvis/assistant/dashboard/src/components/Orb.tsx`
- Delete: `jarvis/assistant/dashboard/src/components/NowPlaying.tsx` (replaced by Pill + Expanded)

- [ ] **Step 1: Verify no imports remain.** Search for any remaining imports of `StatusBar`, `Orb`, or old `NowPlaying` in the codebase. Fix any references.

- [ ] **Step 2: Delete the files.**

- [ ] **Step 3: Commit** — `git commit -m "chore(dashboard): remove old StatusBar, Orb, NowPlaying components"`

---

## Phase 7: Polish & Verify

### Task 29: Responsive Tuning

**Files:**
- Modify: `jarvis/assistant/dashboard/src/components/Canvas.tsx`
- Modify: `jarvis/assistant/dashboard/src/App.tsx`

- [ ] **Step 1: Test compact layout.** Resize browser to 375px width. Verify: avatar scales down, clock is readable, pills wrap correctly, SlidePanel is full-width.

- [ ] **Step 2: Test medium layout.** Resize to 768px. Verify: avatar at medium size, panels slide in at 60% width.

- [ ] **Step 3: Test large layout.** Full desktop width. Verify: avatar at largest size, everything centered and calm.

- [ ] **Step 4: Fix any overflow or clipping issues.** Ensure no scrollbars appear on the main idle screen. All animated elements stay within viewport.

- [ ] **Step 5: Commit** — `git commit -m "fix(dashboard): responsive tuning across breakpoints"`

---

### Task 30: Night Mode Verification

- [ ] **Step 1: Test time-of-day transitions.** Temporarily set the `useTimeOfDay` hook to use accelerated time (1 minute = 1 hour). Watch the gradient shift from morning → afternoon → night.

- [ ] **Step 2: Verify night mode dimming.** During "night" palette: check all UI elements are at reduced opacity, orb breathes slowly, no bright white text anywhere.

- [ ] **Step 3: Verify personality + time combination.** Switch to "girlfriend" during night mode. Confirm rose-lavender tones. Switch to "devesh" during morning. Confirm teal-cyan.

- [ ] **Step 4: Remove accelerated time hack.** Reset `useTimeOfDay` to normal 60-second interval.

- [ ] **Step 5: Commit** — `git commit -m "fix(dashboard): verify and tune night mode + personality color blending"`

---

### Task 31: Full Integration Test

- [ ] **Step 1: Start assistant in default mode** (with voice, wake word, the works).

- [ ] **Step 2: Test idle state.** Dashboard shows avatar + time + status dot only. No other elements visible.

- [ ] **Step 3: Test voice interaction.** Speak a command. Verify: state transitions (idle → listening → thinking → speaking → idle) reflect in the avatar animation.

- [ ] **Step 4: Test intent badges.** Say "play Sajni and set lights to red." Verify: two pills appear below avatar, each resolves and fades.

- [ ] **Step 5: Test now-playing.** While music plays: verify compact pill at bottom. Click to expand. Verify controls work. Verify auto-collapse after 5s.

- [ ] **Step 6: Test personality switch.** Say "switch to [personality]." Verify: dissolve → dark pause → reform animation. Colors change. Avatar changes.

- [ ] **Step 7: Test navigation.** Press ↑ arrow — transcript slides up. Press Esc — dismisses. Press ← — settings placeholder. Press → — lights placeholder.

- [ ] **Step 8: Commit** — `git commit -m "test(dashboard): verify full integration of redesigned UI"`
