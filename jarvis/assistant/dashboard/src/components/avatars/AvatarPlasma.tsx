/**
 * AvatarPlasma — A liquid, morphing organic blob.
 *
 * Think lava lamp meets Slime Rancher meets jellyfish: ONE big amorphous shape
 * that's continuously alive, with two darker "void" eyes that drift INSIDE the
 * goo (not drawn on top of it — they ARE inside it). Internal particles speed
 * up, the shape stretches, breathes, ripples. The mouth is a transient bubble
 * that opens and closes during speech.
 *
 * Visual layering (back to front):
 *   1. Outer atmospheric glow (large soft radial blur)
 *   2. Inner halo (slightly smaller, more saturated blur)
 *   3. The blob body — single morphing path with iridescent gradient fill
 *   4. Inner specular highlight (frosted upper sheen)
 *   5. Internal turbulence particles (small darker specks drifting in liquid)
 *   6. Eye voids (two darker "bubbles" — they belong INSIDE the blob)
 *   7. Eye glints (subtle cyan-ish reflections inside the voids)
 *   8. Mouth bubble (only appears during speaking)
 *   9. Surface ripple ring (transient, on surprised mood / state changes)
 *
 * Path morphing:
 *   All blob paths use IDENTICAL command structure (M + 6 cubic beziers + Z)
 *   so framer-motion can interpolate `d` smoothly. We pre-compute 5 organic
 *   shape sets per state/mood combination by perturbing radii around 6 angles.
 *
 * Colors come from CSS custom properties set by TokenProvider:
 *   --personality-accent       primary blob color
 *   --personality-accent-rgb   RGB triplet for rgba math
 *   --personality-glow_color   outer glow halo
 */

import { useMemo } from 'react'
import { motion } from 'framer-motion'
import { useLightMode } from '../../hooks/useLightMode'
import type { AssistantState, AssistantMood } from '../../types/assistant'

export interface AvatarPlasmaProps {
  size: number
  state: AssistantState
  mood: AssistantMood
}

// ─── Geometry: viewBox is 100x100, blob centered at (50, 50) ────────────────

const CX = 50
const CY = 50
const BASE_R = 32 // base radius — keeps the blob comfortably within viewBox

// 6 angle samples around the circle (every 60°). More points = smoother but
// harder to tune asymmetry. Six gives good organic feel without "polygonal" look.
const ANGLES = [
  -Math.PI / 2,                    // top (270° / -90°)
  -Math.PI / 2 + (Math.PI * 2) / 6, // upper-right
  -Math.PI / 2 + (Math.PI * 4) / 6, // lower-right
  -Math.PI / 2 + Math.PI,           // bottom
  -Math.PI / 2 + (Math.PI * 8) / 6, // lower-left
  -Math.PI / 2 + (Math.PI * 10) / 6, // upper-left
]

// ─── Path generator ────────────────────────────────────────────────────────

/**
 * Build a closed blob path from 6 radii (one per ANGLES sample).
 *
 * Uses cubic beziers with control handles tangent to the circle for smooth
 * curvature. Each segment between two anchor points has 2 control points,
 * one offset perpendicular from each anchor. This is the "Catmull-like"
 * tangent smoothing trick that gives organic shapes their soft, fluid look.
 *
 * The output always has exactly: 1 M + 6 C + 1 Z = same command structure,
 * which is what framer-motion needs for smooth `d` interpolation.
 *
 * Optional offsets shift the entire shape (cx, cy) and skew it (skewX, skewY)
 * for mood-driven asymmetry like sad's downward droop or sarcastic's tilt.
 */
function buildBlob(
  radii: number[],
  cx = CX,
  cy = CY,
  skewX = 0,
  skewY = 0,
): string {
  // Convert each (angle, radius) into a Cartesian anchor point. Skew is
  // multiplied with sin/cos so vertical squash affects mostly top/bottom and
  // horizontal squash affects mostly sides — feels natural for liquid.
  const points = ANGLES.map((a, i) => {
    const r = radii[i]
    const x = cx + Math.cos(a) * r * (1 + skewX)
    const y = cy + Math.sin(a) * r * (1 + skewY)
    return { x, y, a }
  })

  // Cubic bezier control magnitude: for a circle approximated by 4 segments,
  // the magic number is r * 0.5523. With 6 segments the equivalent is ~0.36 of
  // the chord length, but 0.55 still looks soft for organic shapes — anything
  // more makes loops, anything less makes a hexagon.
  const HANDLE = 0.36

  let path = `M ${points[0].x.toFixed(2)} ${points[0].y.toFixed(2)}`

  for (let i = 0; i < points.length; i++) {
    const p0 = points[i]
    const p1 = points[(i + 1) % points.length]
    // Tangent direction perpendicular to the radial line, scaled by the chord
    // length between the two anchors.
    const chord = Math.hypot(p1.x - p0.x, p1.y - p0.y)
    const t0x = -Math.sin(p0.a) * chord * HANDLE
    const t0y = Math.cos(p0.a) * chord * HANDLE
    const t1x = -Math.sin(p1.a) * chord * HANDLE
    const t1y = Math.cos(p1.a) * chord * HANDLE
    const c1x = p0.x + t0x
    const c1y = p0.y + t0y
    const c2x = p1.x - t1x
    const c2y = p1.y - t1y
    path += ` C ${c1x.toFixed(2)} ${c1y.toFixed(2)} ${c2x.toFixed(2)} ${c2y.toFixed(2)} ${p1.x.toFixed(2)} ${p1.y.toFixed(2)}`
  }
  return path + ' Z'
}

// ─── Pre-computed shape sets ────────────────────────────────────────────────
// Each set is 5 frames the blob morphs through. All sets MUST share the same
// command structure (which buildBlob guarantees) so framer-motion can morph.

/** Symmetric breathing — used for idle. Subtle radius variation. */
const IDLE_FRAMES: string[] = [
  buildBlob([1.00, 1.02, 0.98, 1.00, 0.97, 1.03].map(m => m * BASE_R)),
  buildBlob([1.04, 0.97, 1.02, 0.96, 1.03, 0.99].map(m => m * BASE_R)),
  buildBlob([0.98, 1.03, 0.99, 1.04, 0.96, 1.02].map(m => m * BASE_R)),
  buildBlob([1.02, 0.99, 1.05, 0.98, 1.01, 0.97].map(m => m * BASE_R)),
  buildBlob([1.00, 1.02, 0.98, 1.00, 0.97, 1.03].map(m => m * BASE_R)), // close loop
]

/** Listening — elongated upward, like a curious ear. */
const LISTENING_FRAMES: string[] = [
  buildBlob([1.18, 1.10, 0.94, 0.92, 0.94, 1.08].map(m => m * BASE_R)),
  buildBlob([1.22, 1.08, 0.96, 0.90, 0.96, 1.12].map(m => m * BASE_R)),
  buildBlob([1.16, 1.12, 0.93, 0.94, 0.93, 1.06].map(m => m * BASE_R)),
  buildBlob([1.20, 1.06, 0.97, 0.91, 0.97, 1.10].map(m => m * BASE_R)),
  buildBlob([1.18, 1.10, 0.94, 0.92, 0.94, 1.08].map(m => m * BASE_R)),
]

/** Thinking — nervous compress/stretch in horizontal axis. */
const THINKING_FRAMES: string[] = [
  buildBlob([0.92, 1.08, 1.06, 0.94, 1.10, 1.04].map(m => m * BASE_R)),
  buildBlob([1.06, 0.94, 0.92, 1.08, 0.94, 1.10].map(m => m * BASE_R)),
  buildBlob([0.96, 1.10, 1.04, 0.96, 1.08, 0.94].map(m => m * BASE_R)),
  buildBlob([1.10, 0.92, 0.94, 1.06, 0.96, 1.08].map(m => m * BASE_R)),
  buildBlob([0.92, 1.08, 1.06, 0.94, 1.10, 1.04].map(m => m * BASE_R)),
]

/** Speaking — outward pulse with rhythmic variation. */
const SPEAKING_FRAMES: string[] = [
  buildBlob([1.04, 1.06, 1.05, 1.06, 1.05, 1.06].map(m => m * BASE_R)),
  buildBlob([0.95, 0.96, 0.94, 0.96, 0.94, 0.96].map(m => m * BASE_R)),
  buildBlob([1.08, 1.04, 1.07, 1.04, 1.07, 1.04].map(m => m * BASE_R)),
  buildBlob([0.96, 0.98, 0.95, 0.98, 0.95, 0.98].map(m => m * BASE_R)),
  buildBlob([1.04, 1.06, 1.05, 1.06, 1.05, 1.06].map(m => m * BASE_R)),
]

/** Sleeping — settled into wide low shape. Top flattens, bottom widens. */
const SLEEPING_FRAMES: string[] = [
  buildBlob([0.78, 0.90, 1.10, 1.15, 1.10, 0.90].map(m => m * BASE_R)),
  buildBlob([0.76, 0.92, 1.12, 1.14, 1.12, 0.92].map(m => m * BASE_R)),
  buildBlob([0.78, 0.90, 1.10, 1.15, 1.10, 0.90].map(m => m * BASE_R)),
  buildBlob([0.80, 0.88, 1.08, 1.16, 1.08, 0.88].map(m => m * BASE_R)),
  buildBlob([0.78, 0.90, 1.10, 1.15, 1.10, 0.90].map(m => m * BASE_R)),
]

// Mood overlays — these REPLACE the state frames when active. We synthesize
// per-mood shape sets so the blob keeps its character regardless of state.

/** Happy — lifts upward, slight bounce. */
const HAPPY_FRAMES: string[] = [
  buildBlob([1.10, 1.04, 1.00, 0.95, 1.00, 1.04].map(m => m * BASE_R), CX, CY - 1.5),
  buildBlob([1.14, 1.06, 0.98, 0.94, 0.98, 1.06].map(m => m * BASE_R), CX, CY - 2.5),
  buildBlob([1.10, 1.04, 1.00, 0.95, 1.00, 1.04].map(m => m * BASE_R), CX, CY - 1.5),
  buildBlob([1.12, 1.06, 0.98, 0.96, 0.98, 1.06].map(m => m * BASE_R), CX, CY - 2.0),
  buildBlob([1.10, 1.04, 1.00, 0.95, 1.00, 1.04].map(m => m * BASE_R), CX, CY - 1.5),
]

/** Sad — droops, heavier at the bottom, narrower at top. */
const SAD_FRAMES: string[] = [
  buildBlob([0.85, 0.92, 1.12, 1.18, 1.12, 0.92].map(m => m * BASE_R), CX, CY + 2),
  buildBlob([0.83, 0.94, 1.14, 1.20, 1.14, 0.94].map(m => m * BASE_R), CX, CY + 2.5),
  buildBlob([0.85, 0.92, 1.12, 1.18, 1.12, 0.92].map(m => m * BASE_R), CX, CY + 2),
  buildBlob([0.86, 0.90, 1.10, 1.16, 1.10, 0.90].map(m => m * BASE_R), CX, CY + 1.5),
  buildBlob([0.85, 0.92, 1.12, 1.18, 1.12, 0.92].map(m => m * BASE_R), CX, CY + 2),
]

/** Shy — compressed, smaller overall, slight downward tilt. */
const SHY_FRAMES: string[] = [
  buildBlob([0.88, 0.90, 0.92, 0.94, 0.92, 0.90].map(m => m * BASE_R), CX, CY + 1),
  buildBlob([0.86, 0.92, 0.94, 0.92, 0.94, 0.92].map(m => m * BASE_R), CX, CY + 1.5),
  buildBlob([0.88, 0.90, 0.92, 0.94, 0.92, 0.90].map(m => m * BASE_R), CX, CY + 1),
  buildBlob([0.90, 0.88, 0.94, 0.92, 0.94, 0.88].map(m => m * BASE_R), CX, CY + 0.5),
  buildBlob([0.88, 0.90, 0.92, 0.94, 0.92, 0.90].map(m => m * BASE_R), CX, CY + 1),
]

/** Playful — asymmetric, leans to one side, plays around. */
const PLAYFUL_FRAMES: string[] = [
  buildBlob([1.06, 1.14, 0.98, 1.02, 0.92, 1.04].map(m => m * BASE_R)),
  buildBlob([1.04, 0.94, 1.10, 0.96, 1.16, 0.98].map(m => m * BASE_R)),
  buildBlob([1.10, 1.12, 0.96, 1.04, 0.94, 1.06].map(m => m * BASE_R)),
  buildBlob([1.02, 0.96, 1.08, 0.98, 1.14, 1.00].map(m => m * BASE_R)),
  buildBlob([1.06, 1.14, 0.98, 1.02, 0.92, 1.04].map(m => m * BASE_R)),
]

/** Sarcastic — tilted, asymmetric (one side higher than the other). */
const SARCASTIC_FRAMES: string[] = [
  buildBlob([1.04, 1.10, 1.00, 0.94, 1.02, 0.96].map(m => m * BASE_R), CX, CY, 0.02, -0.02),
  buildBlob([1.06, 1.12, 0.98, 0.96, 1.00, 0.94].map(m => m * BASE_R), CX, CY, 0.03, -0.02),
  buildBlob([1.04, 1.10, 1.00, 0.94, 1.02, 0.96].map(m => m * BASE_R), CX, CY, 0.02, -0.02),
  buildBlob([1.05, 1.08, 1.02, 0.93, 1.04, 0.98].map(m => m * BASE_R), CX, CY, 0.02, -0.03),
  buildBlob([1.04, 1.10, 1.00, 0.94, 1.02, 0.96].map(m => m * BASE_R), CX, CY, 0.02, -0.02),
]

/** Surprised — inflated outward, larger and rounder. */
const SURPRISED_FRAMES: string[] = [
  buildBlob([1.14, 1.13, 1.13, 1.14, 1.13, 1.13].map(m => m * BASE_R)),
  buildBlob([1.16, 1.15, 1.15, 1.16, 1.15, 1.15].map(m => m * BASE_R)),
  buildBlob([1.14, 1.13, 1.13, 1.14, 1.13, 1.13].map(m => m * BASE_R)),
  buildBlob([1.15, 1.14, 1.14, 1.15, 1.14, 1.14].map(m => m * BASE_R)),
  buildBlob([1.14, 1.13, 1.13, 1.14, 1.13, 1.13].map(m => m * BASE_R)),
]

/** Romantic — softer, more rounded edges, gentle sway. */
const ROMANTIC_FRAMES: string[] = [
  buildBlob([1.04, 1.06, 1.04, 1.04, 1.04, 1.06].map(m => m * BASE_R)),
  buildBlob([1.06, 1.04, 1.06, 1.04, 1.06, 1.04].map(m => m * BASE_R)),
  buildBlob([1.04, 1.06, 1.04, 1.04, 1.04, 1.06].map(m => m * BASE_R)),
  buildBlob([1.05, 1.05, 1.05, 1.05, 1.05, 1.05].map(m => m * BASE_R)),
  buildBlob([1.04, 1.06, 1.04, 1.04, 1.04, 1.06].map(m => m * BASE_R)),
]

/** Gotcha — narrowed and elongated upward (smug stretch). */
const GOTCHA_FRAMES: string[] = [
  buildBlob([1.18, 1.04, 0.92, 1.10, 0.92, 1.04].map(m => m * BASE_R), CX, CY - 1),
  buildBlob([1.22, 1.02, 0.90, 1.12, 0.90, 1.02].map(m => m * BASE_R), CX, CY - 1.5),
  buildBlob([1.18, 1.04, 0.92, 1.10, 0.92, 1.04].map(m => m * BASE_R), CX, CY - 1),
  buildBlob([1.20, 1.03, 0.91, 1.11, 0.91, 1.03].map(m => m * BASE_R), CX, CY - 1.2),
  buildBlob([1.18, 1.04, 0.92, 1.10, 0.92, 1.04].map(m => m * BASE_R), CX, CY - 1),
]

const STATE_FRAMES: Record<AssistantState, string[]> = {
  idle: IDLE_FRAMES,
  listening: LISTENING_FRAMES,
  thinking: THINKING_FRAMES,
  speaking: SPEAKING_FRAMES,
  sleeping: SLEEPING_FRAMES,
}

const MOOD_FRAMES: Partial<Record<AssistantMood, string[]>> = {
  happy: HAPPY_FRAMES,
  sad: SAD_FRAMES,
  shy: SHY_FRAMES,
  playful: PLAYFUL_FRAMES,
  sarcastic: SARCASTIC_FRAMES,
  surprised: SURPRISED_FRAMES,
  romantic: ROMANTIC_FRAMES,
  gotcha: GOTCHA_FRAMES,
}

// ─── State morph timing ─────────────────────────────────────────────────────

interface StateTiming {
  /** Seconds for one full morph cycle. Slower = lazier liquid. */
  morphDuration: number
  /** Seconds between eye-drift retargets — controls how often eyes wander. */
  eyeDriftInterval: number
  /** Pixel range eyes drift inside the blob (in viewBox units). */
  eyeDriftRadius: number
  /** Particle motion speed multiplier (1 = normal). */
  particleSpeed: number
  /** Overall opacity multiplier — sleeping fades the whole shape. */
  opacityMul: number
}

const STATE_TIMING: Record<AssistantState, StateTiming> = {
  idle:      { morphDuration: 5.5, eyeDriftInterval: 2.4, eyeDriftRadius: 3.0, particleSpeed: 1.0, opacityMul: 0.95 },
  listening: { morphDuration: 3.0, eyeDriftInterval: 1.3, eyeDriftRadius: 2.5, particleSpeed: 1.4, opacityMul: 1.00 },
  thinking:  { morphDuration: 1.6, eyeDriftInterval: 0.7, eyeDriftRadius: 4.0, particleSpeed: 1.8, opacityMul: 0.95 },
  speaking:  { morphDuration: 0.9, eyeDriftInterval: 1.5, eyeDriftRadius: 2.0, particleSpeed: 1.5, opacityMul: 1.00 },
  sleeping:  { morphDuration: 9.0, eyeDriftInterval: 5.0, eyeDriftRadius: 0.5, particleSpeed: 0.4, opacityMul: 0.55 },
}

// ─── Eye configuration per mood ────────────────────────────────────────────

interface EyeConfig {
  /** Vertical center offset in viewBox units (positive = lower in blob). */
  yOffset: number
  /** Horizontal half-spacing between eyes. */
  spacing: number
  /** Eye radius in viewBox units — gets squished by scaleY. */
  radius: number
  /** Vertical squash — 1 = round, <1 = squinted closed, 0 = thin line. */
  scaleY: number
  /** Horizontal squash. */
  scaleX: number
  /** Tilt of the whole eye pair (degrees) — for sarcastic. */
  tilt: number
  /** Vertical asymmetry: positive moves left eye up, right eye down. */
  asymmetry: number
  /** Whether to use heart-shaped voids instead of circles. */
  hearts: boolean
}

const BASE_EYE: EyeConfig = {
  yOffset: -3,
  spacing: 9,
  radius: 4.5,
  scaleY: 1,
  scaleX: 1,
  tilt: 0,
  asymmetry: 0,
  hearts: false,
}

const MOOD_EYES: Record<AssistantMood, Partial<EyeConfig>> = {
  neutral:   {},
  happy:     { scaleY: 0.45, yOffset: -4, radius: 5.0 },
  sad:       { scaleY: 0.85, yOffset: -1, scaleX: 1.05 },
  shy:       { scaleY: 0.80, yOffset: -1, radius: 4.0 },
  playful:   { yOffset: -3, radius: 5.0 },
  sarcastic: { tilt: -8, asymmetry: 2.5, scaleY: 0.7 },
  surprised: { scaleY: 1.25, scaleX: 1.25, radius: 5.5 },
  romantic:  { hearts: true, radius: 5.2, yOffset: -3 },
  gotcha:    { scaleY: 0.35, yOffset: -4, scaleX: 1.1 },
}

// State-driven eye overrides on top of mood. State has gentler hand than mood
// so it only nudges things not strictly determined by emotion.
const STATE_EYES: Partial<Record<AssistantState, Partial<EyeConfig>>> = {
  listening: { yOffset: -6 },         // eyes look up
  sleeping:  { scaleY: 0.10, yOffset: -2 }, // eyes "closed"
}

function resolveEyes(state: AssistantState, mood: AssistantMood): EyeConfig {
  return { ...BASE_EYE, ...MOOD_EYES[mood], ...(STATE_EYES[state] ?? {}) }
}

// ─── Heart path (used for romantic mood) ────────────────────────────────────
// A unit heart centered at (0,0), to be scaled by `r` and translated.

function heartPath(cx: number, cy: number, r: number): string {
  const s = r * 1.4
  // Classic heart bezier construction. Two top lobes meet at the bottom point.
  return [
    `M ${cx} ${cy + s * 0.55}`,
    `C ${cx + s * 0.95} ${cy - s * 0.05} ${cx + s * 0.55} ${cy - s * 0.65} ${cx} ${cy - s * 0.25}`,
    `C ${cx - s * 0.55} ${cy - s * 0.65} ${cx - s * 0.95} ${cy - s * 0.05} ${cx} ${cy + s * 0.55}`,
    `Z`,
  ].join(' ')
}

// ─── Component ──────────────────────────────────────────────────────────────

export function AvatarPlasma({ size, state, mood }: AvatarPlasmaProps) {
  const isLight = useLightMode()

  // Pick the morph frames. Mood frames take precedence over state frames if
  // the mood has a non-neutral overlay, because the user's emotional state
  // should read more strongly than what the assistant is "doing".
  // Exception: speaking state always uses speaking frames so the rhythmic
  // pulse stays in sync with TTS regardless of mood.
  const frames = useMemo(() => {
    if (state === 'speaking') return SPEAKING_FRAMES
    if (state === 'sleeping') return SLEEPING_FRAMES
    if (mood !== 'neutral' && MOOD_FRAMES[mood]) return MOOD_FRAMES[mood]!
    return STATE_FRAMES[state]
  }, [state, mood])

  const timing = STATE_TIMING[state]
  const eyes = useMemo(() => resolveEyes(state, mood), [state, mood])

  // ── Color resolution ──────────────────────────────────────────────────
  // We build the iridescent gradient from rgba(accent) at multiple opacities
  // plus white blends for the "lighter" stop and dark blends for the "darker"
  // stop. color-mix gives us hue interpolation without needing JS color math.
  const accentRgb = 'var(--personality-accent-rgb)'
  const accent = 'var(--personality-accent)'
  const glow = 'var(--personality-glow_color)'
  const a = (op: number) => `rgba(${accentRgb}, ${op})`

  // Light-mode accent: push toward dark brown so the blob reads on white BG.
  const darkRgb = '42, 26, 10'
  const d = (op: number) => `rgba(${darkRgb}, ${op})`

  // Mood color tints — these blend INTO the gradient for emotional read.
  const moodTint: { rgb: string; weight: number } = (() => {
    switch (mood) {
      case 'happy':     return { rgb: '255, 200, 80',  weight: 0.25 } // warm gold
      case 'sad':       return { rgb: '90, 130, 200',  weight: 0.30 } // cool blue
      case 'shy':       return { rgb: '255, 150, 200', weight: 0.30 } // pink
      case 'playful':   return { rgb: '255, 170, 120', weight: 0.20 } // peach
      case 'sarcastic': return { rgb: '180, 120, 220', weight: 0.20 } // violet
      case 'surprised': return { rgb: '255, 240, 130', weight: 0.30 } // bright yellow
      case 'romantic':  return { rgb: '255, 100, 140', weight: 0.45 } // strong pink/red
      case 'gotcha':    return { rgb: '200, 160, 255', weight: 0.20 } // playful purple
      default:          return { rgb: '0, 0, 0',       weight: 0    }
    }
  })()
  const tintColor = (op: number) => `rgba(${moodTint.rgb}, ${op})`

  // Unique IDs so multiple AvatarPlasma instances don't collide on gradient/filter defs.
  const uid = useMemo(() => Math.random().toString(36).slice(2, 8), [])

  // ── Eye geometry ──────────────────────────────────────────────────────
  const eyeY = CY + eyes.yOffset
  const leftEyeX = CX - eyes.spacing
  const rightEyeX = CX + eyes.spacing

  // ── Mouth (only meaningful for speaking) ──────────────────────────────
  const mouthY = CY + 8
  const mouthW = 8
  const mouthH = state === 'speaking' ? 4 : 0

  // ── Outer container size ──────────────────────────────────────────────
  // We render at `size` but reserve 2x size in the parent box so glow doesn't
  // get clipped by surrounding layout.
  const containerW = size * 2
  const containerH = size * 2

  // ── Animation transition objects ──────────────────────────────────────
  const morphTransition = {
    duration: timing.morphDuration,
    repeat: Infinity,
    ease: 'easeInOut' as const,
  }

  // Hue-rotate cycle on the gradient — slow cycling iridescence
  const hueDuration = state === 'thinking' ? 4 : state === 'sleeping' ? 20 : 12

  return (
    <div
      className="relative flex items-center justify-center"
      style={{ width: containerW, height: containerH }}
    >
      {/* Outer atmospheric glow. Big soft halo behind the blob. */}
      <motion.div
        className="absolute rounded-full"
        style={{
          width: size * 1.7,
          height: size * 1.7,
          background: isLight
            ? 'radial-gradient(circle, rgba(0,0,0,0.06) 0%, transparent 65%)'
            : `radial-gradient(circle, ${glow} 0%, transparent 65%)`,
          filter: `blur(${size * 0.22}px)`,
          opacity: 0.55 * timing.opacityMul,
        }}
        animate={{
          scale: [1, 1.1, 1],
          opacity: [
            0.45 * timing.opacityMul,
            0.65 * timing.opacityMul,
            0.45 * timing.opacityMul,
          ],
        }}
        transition={{
          duration: timing.morphDuration * 1.2,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
      />

      {/* The blob SVG. Width/height match `size`, and viewBox stretches across. */}
      <motion.svg
        viewBox="0 0 100 100"
        width={size}
        height={size}
        style={{ overflow: 'visible' }}
        animate={{
          // Subtle hue rotation gives the iridescent shimmer. We do it on the
          // SVG element so the whole gradient cycles together.
          filter: [
            'hue-rotate(0deg)',
            'hue-rotate(15deg)',
            'hue-rotate(0deg)',
            'hue-rotate(-12deg)',
            'hue-rotate(0deg)',
          ],
        }}
        transition={{
          duration: hueDuration,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
      >
        <defs>
          {/* Iridescent main gradient — multi-stop linear from upper-left to lower-right.
              The middle stop carries the mood tint; outer stops are lighter/darker
              variants of the personality accent. */}
          <linearGradient
            id={`plasma-fill-${uid}`}
            x1="20%"
            y1="10%"
            x2="80%"
            y2="95%"
          >
            <stop offset="0%"  stopColor={isLight ? d(0.85) : a(0.95)} />
            <stop offset="35%" stopColor={isLight ? d(0.70) : a(0.80)} />
            <stop offset="55%" stopColor={tintColor(moodTint.weight)} stopOpacity={moodTint.weight > 0 ? 1 : 0} />
            <stop offset="80%" stopColor={isLight ? d(0.60) : a(0.65)} />
            <stop offset="100%" stopColor={isLight ? d(0.50) : a(0.50)} />
          </linearGradient>

          {/* Inner radial overlay for "depth" — lighter near the upper-left, fading to transparent. */}
          <radialGradient
            id={`plasma-sheen-${uid}`}
            cx="35%"
            cy="28%"
            r="55%"
          >
            <stop offset="0%"  stopColor="white" stopOpacity={isLight ? 0.35 : 0.45} />
            <stop offset="50%" stopColor="white" stopOpacity={isLight ? 0.10 : 0.15} />
            <stop offset="100%" stopColor="white" stopOpacity="0" />
          </radialGradient>

          {/* Eye void gradient — radial dark center, subtle edge softening. */}
          <radialGradient
            id={`plasma-eye-${uid}`}
            cx="40%"
            cy="35%"
            r="65%"
          >
            <stop offset="0%"   stopColor={isLight ? '#000000' : '#000000'} stopOpacity="0.85" />
            <stop offset="60%"  stopColor={isLight ? '#1a0e05' : '#000000'} stopOpacity="0.78" />
            <stop offset="100%" stopColor={isLight ? d(0.6) : a(0.5)}      stopOpacity="0.55" />
          </radialGradient>

          {/* Soft blur filter for the inner halo behind the blob. */}
          <filter id={`plasma-blur-${uid}`} x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="2.4" />
          </filter>

          {/* Light blur for the specular highlight. */}
          <filter id={`plasma-highlight-blur-${uid}`} x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="1.2" />
          </filter>
        </defs>

        {/* Inner halo — a softer copy of the blob behind the main shape. */}
        <motion.path
          fill={isLight ? d(0.18) : a(0.30)}
          filter={`url(#plasma-blur-${uid})`}
          style={{ opacity: 0.6 * timing.opacityMul }}
          animate={{ d: frames, scale: [1.08, 1.10, 1.08, 1.10, 1.08] }}
          transition={morphTransition}
          transform-origin="50px 50px"
        />

        {/* Main blob body with iridescent fill. */}
        <motion.path
          fill={`url(#plasma-fill-${uid})`}
          style={{ opacity: timing.opacityMul }}
          animate={{ d: frames }}
          transition={morphTransition}
        />

        {/* Inner sheen — radial highlight on top of the blob. We morph the sheen
            shape with the blob so it stays "inside" the silhouette via overlay
            (we let it bleed slightly because the sheen radial is bounded). */}
        <motion.path
          fill={`url(#plasma-sheen-${uid})`}
          animate={{ d: frames }}
          transition={morphTransition}
          style={{ pointerEvents: 'none' }}
        />

        {/* Specular highlight — a small bright crescent on the upper-left.
            We don't morph this with the blob because it's a localized lens flare;
            instead it gently drifts to feel alive. */}
        <motion.ellipse
          cx={CX - 10}
          cy={CY - 14}
          rx={9}
          ry={4}
          fill="white"
          filter={`url(#plasma-highlight-blur-${uid})`}
          style={{ opacity: isLight ? 0.35 : 0.45 }}
          animate={{
            cx: [CX - 10, CX - 8, CX - 11, CX - 10],
            cy: [CY - 14, CY - 13, CY - 15, CY - 14],
            rx: [9, 10, 8.5, 9],
          }}
          transition={{
            duration: timing.morphDuration * 0.9,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
        />

        {/* Internal turbulence particles. Three tiny darker specks drifting at
            different speeds and Lissajous-like paths to feel like particulate
            in a lava lamp. They stay near the blob center to avoid leaving the
            silhouette during morph. */}
        <Particle
          baseX={CX - 6}
          baseY={CY + 6}
          rx={4}
          ry={5}
          color={isLight ? d(0.45) : a(0.55)}
          duration={3.5 / timing.particleSpeed}
          size={1.6}
        />
        <Particle
          baseX={CX + 7}
          baseY={CY + 2}
          rx={5}
          ry={3.5}
          color={isLight ? d(0.40) : a(0.50)}
          duration={4.2 / timing.particleSpeed}
          size={1.2}
          delay={0.6}
        />
        <Particle
          baseX={CX - 2}
          baseY={CY + 12}
          rx={3}
          ry={3}
          color={isLight ? d(0.35) : a(0.45)}
          duration={5.0 / timing.particleSpeed}
          size={0.9}
          delay={1.2}
        />

        {/* Eye voids — drift inside the blob via Lissajous-like animation.
            Each eye uses an independent <g> with its own animate so they
            move semi-independently like real eyeballs in liquid. */}
        <Eye
          baseX={leftEyeX}
          baseY={eyeY - eyes.asymmetry}
          eyes={eyes}
          fillId={`plasma-eye-${uid}`}
          driftRadius={timing.eyeDriftRadius}
          driftPeriod={timing.eyeDriftInterval}
          mood={mood}
        />
        <Eye
          baseX={rightEyeX}
          baseY={eyeY + eyes.asymmetry}
          eyes={eyes}
          fillId={`plasma-eye-${uid}`}
          driftRadius={timing.eyeDriftRadius}
          driftPeriod={timing.eyeDriftInterval}
          mood={mood}
          phase={0.5}
        />

        {/* Mouth bubble — appears only during speaking. A small darker oval
            that opens and closes as the blob speaks. */}
        {state === 'speaking' && (
          <motion.ellipse
            cx={CX}
            cy={mouthY}
            rx={mouthW / 2}
            fill={isLight ? d(0.65) : 'rgba(0,0,0,0.7)'}
            animate={{
              ry: [0.5, mouthH, 1.5, mouthH * 0.9, 0.5],
              cy: [mouthY, mouthY + 0.5, mouthY, mouthY + 0.4, mouthY],
            }}
            transition={{
              duration: 0.45,
              repeat: Infinity,
              ease: 'easeInOut',
            }}
          />
        )}

        {/* Surprise ripple ring — only on surprised mood. Outward expanding
            transparent ring suggests a shockwave through the goo. */}
        {mood === 'surprised' && (
          <motion.circle
            cx={CX}
            cy={CY}
            fill="none"
            stroke={isLight ? d(0.5) : a(0.55)}
            strokeWidth={0.6}
            animate={{
              r: [BASE_R * 0.5, BASE_R * 1.4],
              opacity: [0.7, 0],
            }}
            transition={{
              duration: 1.2,
              repeat: Infinity,
              ease: 'easeOut',
            }}
          />
        )}

        {/* Cheek "bubbles" for shy mood — tiny pink bubbles inside the blob,
            beneath each eye. They subtly pulse to feel alive. */}
        {mood === 'shy' && (
          <>
            <motion.circle
              cx={leftEyeX - 1}
              cy={eyeY + 7}
              r={2.2}
              fill="rgba(255, 150, 200, 0.55)"
              animate={{ r: [2.0, 2.5, 2.0], opacity: [0.5, 0.7, 0.5] }}
              transition={{ duration: 2.5, repeat: Infinity, ease: 'easeInOut' }}
            />
            <motion.circle
              cx={rightEyeX + 1}
              cy={eyeY + 7}
              r={2.2}
              fill="rgba(255, 150, 200, 0.55)"
              animate={{ r: [2.0, 2.5, 2.0], opacity: [0.5, 0.7, 0.5] }}
              transition={{ duration: 2.5, repeat: Infinity, ease: 'easeInOut', delay: 0.3 }}
            />
          </>
        )}
      </motion.svg>
    </div>
  )
}

// ─── Particle subcomponent ─────────────────────────────────────────────────
// A small darker speck that drifts in a Lissajous-like loop. Pulled out as a
// component so each particle gets its own animate/transition without bloating
// the parent JSX.

interface ParticleProps {
  baseX: number
  baseY: number
  rx: number  // horizontal drift radius
  ry: number  // vertical drift radius
  color: string
  duration: number
  size: number
  delay?: number
}

function Particle({ baseX, baseY, rx, ry, color, duration, size, delay = 0 }: ParticleProps) {
  // 4-point loop forms a soft figure-8-ish path. Repeat infinity.
  return (
    <motion.circle
      r={size}
      fill={color}
      animate={{
        cx: [baseX, baseX + rx, baseX, baseX - rx, baseX],
        cy: [baseY, baseY - ry, baseY + ry * 0.6, baseY - ry * 0.4, baseY],
        opacity: [0.55, 0.75, 0.45, 0.65, 0.55],
      }}
      transition={{
        duration,
        repeat: Infinity,
        ease: 'easeInOut',
        delay,
      }}
    />
  )
}

// ─── Eye subcomponent ──────────────────────────────────────────────────────
// Each eye is a <g> that drifts inside the blob and contains either a circle
// (or ellipse when squished) or a heart-shaped path (romantic mood). A small
// inner glint follows the eye for extra "alive" feel.

interface EyeProps {
  baseX: number
  baseY: number
  eyes: EyeConfig
  fillId: string
  driftRadius: number
  driftPeriod: number
  mood: AssistantMood
  /** Phase offset (0–1) so left and right eye don't drift in lockstep. */
  phase?: number
}

function Eye({ baseX, baseY, eyes, fillId, driftRadius, driftPeriod, mood, phase = 0 }: EyeProps) {
  // Drift loop — each eye traces a small ellipse offset by `phase` so the two
  // eyes don't move identically (would feel mechanical).
  const driftX = [
    0,
    driftRadius * 0.7,
    driftRadius * 0.3,
    -driftRadius * 0.5,
    -driftRadius * 0.6,
    0,
  ]
  const driftY = [
    0,
    -driftRadius * 0.4,
    driftRadius * 0.5,
    driftRadius * 0.3,
    -driftRadius * 0.5,
    0,
  ]

  // Apply phase shift by rotating the array.
  const shift = Math.floor(phase * driftX.length)
  const xs = [...driftX.slice(shift), ...driftX.slice(0, shift)]
  const ys = [...driftY.slice(shift), ...driftY.slice(0, shift)]

  // Total cycle duration — 6 keyframes over (driftPeriod * 6) seconds means
  // each retarget takes driftPeriod seconds, matching the timing config.
  const totalDuration = driftPeriod * 6

  return (
    <motion.g
      animate={{
        x: xs,
        y: ys,
        rotate: eyes.tilt,
      }}
      transition={{
        x: { duration: totalDuration, repeat: Infinity, ease: 'easeInOut' },
        y: { duration: totalDuration, repeat: Infinity, ease: 'easeInOut' },
        rotate: { duration: 0.6, ease: 'easeOut' },
      }}
    >
      {eyes.hearts ? (
        <motion.path
          d={heartPath(baseX, baseY, eyes.radius)}
          fill={`url(#${fillId})`}
          animate={{ scale: [1, 1.08, 1] }}
          transition={{ duration: 1.4, repeat: Infinity, ease: 'easeInOut' }}
          style={{ transformOrigin: `${baseX}px ${baseY}px` }}
        />
      ) : (
        <motion.ellipse
          cx={baseX}
          cy={baseY}
          fill={`url(#${fillId})`}
          animate={{
            rx: eyes.radius * eyes.scaleX,
            ry: eyes.radius * eyes.scaleY,
          }}
          transition={{ type: 'spring', stiffness: 220, damping: 18 }}
        />
      )}

      {/* Eye glint — small light cyan reflection inside the void. Only render
          when the eye is "open" enough to have visible interior. */}
      {!eyes.hearts && eyes.scaleY > 0.3 && (
        <motion.ellipse
          cx={baseX - eyes.radius * 0.35}
          cy={baseY - eyes.radius * eyes.scaleY * 0.4}
          rx={eyes.radius * 0.18}
          ry={eyes.radius * eyes.scaleY * 0.18}
          fill="rgba(180, 220, 255, 0.55)"
        />
      )}

      {/* Playful wink — only on the right eye (phase=0.5) when mood is playful.
          Briefly squashes scaleY at intervals. */}
      {mood === 'playful' && phase > 0.3 && !eyes.hearts && (
        <motion.ellipse
          cx={baseX}
          cy={baseY}
          rx={eyes.radius * 1.05}
          ry={0}
          fill={`url(#${fillId})`}
          animate={{
            ry: [0, 0, 0, eyes.radius * 0.9, 0, 0],
          }}
          transition={{
            duration: 4,
            repeat: Infinity,
            times: [0, 0.7, 0.78, 0.82, 0.88, 1],
            ease: 'easeInOut',
          }}
          style={{ mixBlendMode: 'normal' }}
        />
      )}
    </motion.g>
  )
}
