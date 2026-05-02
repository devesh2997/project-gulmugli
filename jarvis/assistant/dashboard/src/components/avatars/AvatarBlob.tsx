/**
 * AvatarBlob — a soft, 3D-feeling pebble face.
 *
 * Think Animoji + BMO + EVE from WALL-E. The whole rounded shape IS the
 * character — eyes, mouth, and eyebrows live ON the surface of the body,
 * rather than inside a frame. Depth comes from a directional radial
 * gradient (lighter at top-left, darker at bottom-right), a soft inner
 * shadow at the bottom, a subtle specular highlight, and an outer drop
 * shadow.
 *
 * Five animation layers run independently:
 *   - Body (breathing, tilt, droop, bounce, wobble)
 *   - Gaze (idle drift, listening up, thinking dart, sleeping closed)
 *   - Blink (random while awake)
 *   - Mouth (sine-wave open/close while speaking, mood-shaped otherwise)
 *   - Eyebrows (rotation/translation per mood)
 *
 * Colors come from CSS custom properties set by TokenProvider:
 *   --personality-accent       base body color (used directly + via mix)
 *   --personality-accent-rgb   for rgba() composition (gradients, glow)
 *   --personality-glow_color   outer ambient glow tint
 */

import { useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { useLightMode } from '../../hooks/useLightMode'
import type { AssistantState, AssistantMood } from '../../types/assistant'

// ─── Expression parameters ──────────────────────────────────────────────────

interface BlobExpression {
  // Eye geometry
  eyeScaleY: number       // 0..1.4, vertical squash for happy/sleeping
  eyeScaleX: number       // 0.8..1.3
  eyeGazeX: number        // -1..1 horizontal pupil offset
  eyeGazeY: number        // -1..1 vertical pupil offset
  eyeWink: number         // 0=open, 1=fully closed (right eye only)

  // Eyebrow position + tilt
  browLeftY: number       // px in viewBox (negative = raised above base)
  browRightY: number
  browLeftAngle: number   // degrees
  browRightAngle: number
  browOpacity: number

  // Mouth — described as a quadratic curve plus optional opening
  mouthCurve: number      // -1 (frown) to +1 (smile)
  mouthWidth: number      // px in viewBox
  mouthOpen: number       // 0..1, drives ellipse height
  mouthOffsetX: number    // for asymmetric smiles (-3..3)
  mouthAsymmetryY: number // raises one corner relative to the other

  // Cheeks
  blush: number           // 0..1 opacity

  // Special features
  heartEyes: boolean      // romantic mood
  zParticle: boolean      // sleeping mood

  // Body posture
  bodyTilt: number        // degrees rotation
  bodyDroopY: number      // px translate down
}

// ─── Base + state presets ──────────────────────────────────────────────────

const BASE: BlobExpression = {
  eyeScaleY: 1,
  eyeScaleX: 1,
  eyeGazeX: 0,
  eyeGazeY: 0,
  eyeWink: 0,
  browLeftY: 0,
  browRightY: 0,
  browLeftAngle: 0,
  browRightAngle: 0,
  browOpacity: 0,
  mouthCurve: 0.25,
  mouthWidth: 14,
  mouthOpen: 0,
  mouthOffsetX: 0,
  mouthAsymmetryY: 0,
  blush: 0,
  heartEyes: false,
  zParticle: false,
  bodyTilt: 0,
  bodyDroopY: 0,
}

const STATE_PRESETS: Record<AssistantState, Partial<BlobExpression>> = {
  idle: {},
  listening: {
    bodyTilt: 2,
    eyeGazeY: -0.35,
    eyeScaleY: 1.05,
  },
  thinking: {
    eyeGazeY: -0.2,
    mouthCurve: -0.05,
    mouthWidth: 9,
    browLeftY: -1,
    browRightY: -1.5,
    browLeftAngle: -6,
    browRightAngle: 4,
    browOpacity: 0.7,
  },
  speaking: {
    mouthOpen: 0.45,
    mouthCurve: 0.15,
    mouthWidth: 13,
  },
  sleeping: {
    eyeScaleY: 0.05,
    bodyDroopY: 2,
    mouthCurve: 0.05,
    mouthWidth: 8,
    browOpacity: 0,
  },
}

const MOOD_OVERLAYS: Record<AssistantMood, Partial<BlobExpression>> = {
  neutral: {},
  happy: {
    mouthCurve: 0.85,
    mouthWidth: 18,
    eyeScaleY: 0.7,
    blush: 0.35,
    browLeftY: -1.2,
    browRightY: -1.2,
    browOpacity: 0.55,
  },
  sad: {
    mouthCurve: -0.7,
    mouthWidth: 12,
    eyeGazeY: 0.35,
    browLeftAngle: 14,
    browRightAngle: -14,
    browLeftY: -0.5,
    browRightY: -0.5,
    browOpacity: 0.75,
  },
  shy: {
    mouthCurve: 0.35,
    mouthWidth: 9,
    eyeGazeX: -0.5,
    eyeGazeY: 0.3,
    blush: 0.7,
    browLeftY: -0.5,
    browRightY: -0.5,
    browOpacity: 0.45,
  },
  playful: {
    mouthCurve: 0.95,
    mouthWidth: 17,
    mouthAsymmetryY: -1.2,
    eyeWink: 1,
    eyeScaleY: 0.85,
    blush: 0.3,
    browLeftY: -1.5,
    browRightY: -1,
    browLeftAngle: -4,
    browOpacity: 0.6,
  },
  sarcastic: {
    mouthCurve: 0.4,
    mouthWidth: 12,
    mouthOffsetX: 1.5,
    mouthAsymmetryY: -0.6,
    eyeGazeX: 0.55,
    browLeftY: -2.5,
    browRightY: -0.2,
    browLeftAngle: -10,
    browRightAngle: 6,
    browOpacity: 0.8,
  },
  surprised: {
    mouthOpen: 0.85,
    mouthCurve: 0,
    mouthWidth: 8,
    eyeScaleY: 1.25,
    eyeScaleX: 1.2,
    browLeftY: -3,
    browRightY: -3,
    browOpacity: 0.85,
  },
  romantic: {
    mouthCurve: 0.55,
    mouthWidth: 12,
    blush: 0.6,
    heartEyes: true,
    browLeftY: -1,
    browRightY: -1,
    browOpacity: 0.4,
  },
  gotcha: {
    mouthCurve: 0.65,
    mouthWidth: 15,
    mouthOffsetX: 1,
    mouthAsymmetryY: -1,
    eyeScaleY: 0.5,
    browLeftY: -2,
    browRightY: -0.5,
    browLeftAngle: -7,
    browRightAngle: 3,
    browOpacity: 0.8,
    blush: 0.15,
  },
}

function resolveExpression(state: AssistantState, mood: AssistantMood): BlobExpression {
  return {
    ...BASE,
    ...STATE_PRESETS[state],
    ...MOOD_OVERLAYS[mood],
  }
}

// ─── Geometry constants (viewBox 100×100) ──────────────────────────────────

const VB = 100
// Body bounding box — large pebble centered in viewBox with breathing room
const BODY_W = 74
const BODY_H = 80
const BODY_X = (VB - BODY_W) / 2          // 13
const BODY_Y = (VB - BODY_H) / 2 + 1      // 11 — tiny nudge down for visual balance
const BODY_RX = 28                         // rounded square corner radius
const BODY_CX = VB / 2                     // 50
const BODY_CY = BODY_Y + BODY_H / 2        // 51

// Eye anchors (relative to body center)
const EYE_OFFSET_X = 11                    // distance from center to each eye
const EYE_OFFSET_Y = -7                    // eyes sit slightly above body center
const EYE_BASE_R = 5.2                     // base eye radius
const PUPIL_INNER_R = 4.4                  // dark pupil radius

// Mouth anchor
const MOUTH_BASE_Y = BODY_CY + 9

// Eyebrow anchor
const BROW_BASE_Y = BODY_CY + EYE_OFFSET_Y - EYE_BASE_R - 3.5
const BROW_LEN = 8
const BROW_THICKNESS = 1.6

// Cheek anchors
const CHEEK_OFFSET_X = 15
const CHEEK_OFFSET_Y = 4

// ─── Mouth path builder ────────────────────────────────────────────────────

interface MouthPathInput {
  curve: number
  width: number
  open: number
  offsetX: number
  asymmetryY: number
  cx: number
  cy: number
}

/**
 * Build the SVG path for the mouth.
 *
 * - When `open > 0.25`: render an ellipse-ish open mouth.
 * - Otherwise: a single quadratic curve from left corner to right corner,
 *   with the control point pulled up (smile) or down (frown). Asymmetry
 *   raises one corner for sarcastic / playful / gotcha smirks.
 */
function buildMouthPath({ curve, width, open, offsetX, asymmetryY, cx, cy }: MouthPathInput): string {
  const half = width / 2
  const leftX = cx - half + offsetX
  const rightX = cx + half + offsetX
  const leftY = cy + asymmetryY
  const rightY = cy

  if (open > 0.25) {
    // Open mouth — squashed ellipse, taller as `open` grows
    const rx = width / 2
    const ry = 1.5 + open * 5
    const ecx = cx + offsetX
    const ecy = cy + ry * 0.25
    return [
      `M ${ecx - rx} ${ecy}`,
      `Q ${ecx - rx} ${ecy + ry} ${ecx} ${ecy + ry}`,
      `Q ${ecx + rx} ${ecy + ry} ${ecx + rx} ${ecy}`,
      `Q ${ecx + rx} ${ecy - ry * 0.55} ${ecx} ${ecy - ry * 0.55}`,
      `Q ${ecx - rx} ${ecy - ry * 0.55} ${ecx - rx} ${ecy}`,
      'Z',
    ].join(' ')
  }

  // Closed/curved mouth — control point governs smile vs frown
  const cpY = (leftY + rightY) / 2 + curve * 6
  return `M ${leftX} ${leftY} Q ${cx + offsetX} ${cpY} ${rightX} ${rightY}`
}

// ─── Component ──────────────────────────────────────────────────────────────

export interface AvatarBlobProps {
  size: number
  state: AssistantState
  mood: AssistantMood
}

export function AvatarBlob({ size, state, mood }: AvatarBlobProps) {
  const isLight = useLightMode()
  const expr = useMemo(() => resolveExpression(state, mood), [state, mood])

  // ── Layer: idle gaze drift ──────────────────────────────────────────────
  const [driftX, setDriftX] = useState(0)
  const [driftY, setDriftY] = useState(0)

  useEffect(() => {
    if (state !== 'idle') {
      setDriftX(0)
      setDriftY(0)
      return
    }
    const drift = () => {
      setDriftX((Math.random() - 0.5) * 0.5)
      setDriftY((Math.random() - 0.5) * 0.3)
    }
    drift()
    const id = setInterval(drift, 2500 + Math.random() * 2500)
    return () => clearInterval(id)
  }, [state])

  // ── Layer: thinking eye dart ────────────────────────────────────────────
  const [thinkDart, setThinkDart] = useState(0)

  useEffect(() => {
    if (state !== 'thinking') {
      setThinkDart(0)
      return
    }
    let timerId: ReturnType<typeof setTimeout>
    const dart = () => {
      setThinkDart(prev => (prev > 0 ? -0.55 : 0.55))
      timerId = setTimeout(dart, 600 + Math.random() * 500)
    }
    setThinkDart(-0.55)
    timerId = setTimeout(dart, 700)
    return () => clearTimeout(timerId)
  }, [state])

  // ── Layer: blink ────────────────────────────────────────────────────────
  const [isBlinking, setIsBlinking] = useState(false)

  useEffect(() => {
    if (state === 'sleeping') return
    let timerId: ReturnType<typeof setTimeout>
    const scheduleBlink = () => {
      const delay = 2800 + Math.random() * 3500
      timerId = setTimeout(() => {
        setIsBlinking(true)
        setTimeout(() => setIsBlinking(false), 130)
        scheduleBlink()
      }, delay)
    }
    scheduleBlink()
    return () => clearTimeout(timerId)
  }, [state])

  // ── Layer: speaking mouth open/close ────────────────────────────────────
  const [speakOpen, setSpeakOpen] = useState(0)

  useEffect(() => {
    if (state !== 'speaking') {
      setSpeakOpen(0)
      return
    }
    let timerId: ReturnType<typeof setTimeout>
    const cycle = () => {
      // Sine-ish jitter — random target between 0.15 and 0.85
      setSpeakOpen(0.15 + Math.random() * 0.7)
      timerId = setTimeout(cycle, 110 + Math.random() * 160)
    }
    timerId = setTimeout(cycle, 80)
    return () => clearTimeout(timerId)
  }, [state])

  // ── Resolved animation values ───────────────────────────────────────────
  const gazeX = state === 'idle'
    ? expr.eyeGazeX + driftX
    : state === 'thinking'
      ? expr.eyeGazeX + thinkDart
      : expr.eyeGazeX

  const gazeY = state === 'idle' ? expr.eyeGazeY + driftY : expr.eyeGazeY

  const eyeScaleYFinal = isBlinking ? 0.05 : expr.eyeScaleY
  const mouthOpenFinal = state === 'speaking' ? speakOpen : expr.mouthOpen

  // Pupil offset within eye (in viewBox units)
  const pupilRangeX = (EYE_BASE_R - PUPIL_INNER_R / 2) * 0.55
  const pupilRangeY = (EYE_BASE_R - PUPIL_INNER_R / 2) * 0.5
  const pupilDx = gazeX * pupilRangeX
  const pupilDy = gazeY * pupilRangeY

  // ── Color helpers ───────────────────────────────────────────────────────
  // Use --personality-accent-rgb for rgba() composition (gradients/glow).
  // On light mode we shift to a warmer dark-brown palette so the body still
  // reads as a friendly creature against bright backgrounds.
  const accentRgb = 'var(--personality-accent-rgb)'
  const lightDarkRgb = '50, 32, 18'
  const baseRgb = isLight ? lightDarkRgb : accentRgb
  const a = (op: number) => `rgba(${baseRgb}, ${op})`

  // Eye / pupil colors. Eyes are dark with a subtle accent tint.
  const eyeFill = isLight ? '#1a1208' : '#0d0d12'
  const eyeHighlight = '#ffffff'
  const blushColor = '#ff7eb6'
  const browFill = isLight ? '#1a1208' : 'rgba(20, 20, 28, 0.85)'

  // Mouth fill for closed (stroke) vs open (filled) states
  const mouthStroke = isLight ? '#1a1208' : 'rgba(20, 20, 28, 0.9)'
  const mouthOpenFill = isLight ? '#3a1f10' : '#1a1320'

  // ── Body posture animation ──────────────────────────────────────────────
  // Breathing scale + rotation/translation per state. We ONLY animate
  // transform properties on the body group so we don't trigger layout.
  const breatheScaleAnim = state === 'sleeping'
    ? [1, 1.04, 1]
    : state === 'idle'
      ? [1, 1.02, 1]
      : state === 'speaking'
        ? [1, 1.025, 0.99, 1]
        : state === 'thinking'
          ? [1, 1.005, 0.998, 1.005, 1]
          : [1, 1.015, 1]

  const breatheDuration = state === 'sleeping'
    ? 5.5
    : state === 'speaking'
      ? 1.1
      : state === 'thinking'
        ? 2.4
        : 4

  const bodyRotateAnim = state === 'listening'
    ? expr.bodyTilt
    : state === 'thinking'
      ? [0, -0.8, 0.6, 0]
      : 0

  const bodyTranslateY = expr.bodyDroopY

  // ── Outer glow intensity per state ──────────────────────────────────────
  const glowOpacity = state === 'sleeping'
    ? 0.06
    : state === 'idle'
      ? 0.18
      : state === 'listening'
        ? 0.4
        : state === 'speaking'
          ? 0.45
          : state === 'thinking'
            ? 0.28
            : 0.18

  const glowScale = state === 'listening'
    ? 1.18
    : state === 'speaking'
      ? 1.22
      : state === 'sleeping'
        ? 0.85
        : 1

  // ── Mouth path (memoized on every value that affects shape) ─────────────
  const mouthPath = useMemo(() => buildMouthPath({
    curve: expr.mouthCurve,
    width: expr.mouthWidth,
    open: mouthOpenFinal,
    offsetX: expr.mouthOffsetX,
    asymmetryY: expr.mouthAsymmetryY,
    cx: BODY_CX,
    cy: MOUTH_BASE_Y,
  }), [expr.mouthCurve, expr.mouthWidth, mouthOpenFinal, expr.mouthOffsetX, expr.mouthAsymmetryY])

  // Spring config for mood/state transitions on facial features
  const springConfig = { stiffness: 280, damping: 22, mass: 0.85 }
  const slowSpring = { stiffness: 120, damping: 20, mass: 1 }

  // Heart shape path for romantic eyes (centered at 0,0, fits in radius ~5)
  const heartPath = 'M 0 -1.2 C -1.5 -3.8 -4.6 -3.2 -4.6 -0.6 C -4.6 1.8 -1.6 3.4 0 5.2 C 1.6 3.4 4.6 1.8 4.6 -0.6 C 4.6 -3.2 1.5 -3.8 0 -1.2 Z'

  // Container size — match Cozmo's pattern (visual breathing room around the SVG)
  const containerSize = size * 1.6

  return (
    <div
      className="relative flex items-center justify-center"
      style={{ width: containerSize, height: containerSize }}
    >
      {/* ── Outer ambient glow ─────────────────────────────────────────── */}
      <motion.div
        className="absolute rounded-full"
        style={{
          width: size * 1.35,
          height: size * 1.35,
          background: isLight
            ? `radial-gradient(circle, rgba(0,0,0,0.08) 0%, transparent 70%)`
            : `radial-gradient(circle, var(--personality-glow_color) 0%, transparent 70%)`,
          filter: `blur(${size * 0.22}px)`,
        }}
        animate={{
          opacity: [glowOpacity, glowOpacity * 0.55, glowOpacity],
          scale: [glowScale, glowScale * 1.08, glowScale],
        }}
        transition={{
          duration: breatheDuration * 1.1,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
      />

      {/* ── Listening pulse ring ───────────────────────────────────────── */}
      {state === 'listening' && (
        <motion.div
          className="absolute"
          style={{
            width: size * 0.95,
            height: size * 1.0,
            borderRadius: '42%',
            border: `1.5px solid ${a(0.4)}`,
          }}
          animate={{ scale: [1, 1.35], opacity: [0.5, 0] }}
          transition={{ duration: 1.6, repeat: Infinity, ease: 'easeOut' }}
        />
      )}

      {/* ── Body group with breathing/posture ──────────────────────────── */}
      <motion.div
        style={{ width: size, height: size, position: 'absolute' }}
        animate={{
          scale: breatheScaleAnim,
          rotate: bodyRotateAnim,
          y: bodyTranslateY,
        }}
        transition={{
          scale: { duration: breatheDuration, repeat: Infinity, ease: 'easeInOut' },
          rotate: state === 'thinking'
            ? { duration: 3, repeat: Infinity, ease: 'easeInOut' }
            : { type: 'spring' as const, stiffness: 150, damping: 18 },
          y: { type: 'spring' as const, stiffness: 100, damping: 15 },
        }}
      >
        <svg
          viewBox={`0 0 ${VB} ${VB}`}
          width={size}
          height={size}
          style={{
            overflow: 'visible',
            filter: isLight
              ? 'drop-shadow(0 4px 8px rgba(0,0,0,0.18)) drop-shadow(0 1px 2px rgba(0,0,0,0.12))'
              : `drop-shadow(0 4px 14px rgba(0,0,0,0.45)) drop-shadow(0 0 18px ${a(0.25)})`,
          }}
        >
          <defs>
            {/* Body radial gradient — light at top-left, deeper at bottom-right */}
            <radialGradient id="blob-body-grad" cx="32%" cy="28%" r="85%">
              <stop offset="0%" stopColor={isLight ? `rgba(${baseRgb}, 0.55)` : `rgba(${accentRgb}, 1)`} />
              <stop offset="45%" stopColor={isLight ? `rgba(${baseRgb}, 0.42)` : `rgba(${accentRgb}, 0.78)`} />
              <stop offset="100%" stopColor={isLight ? `rgba(${baseRgb}, 0.62)` : `rgba(${accentRgb}, 0.45)`} />
            </radialGradient>

            {/* Inner shadow — soft dark glow at the bottom of the body */}
            <radialGradient id="blob-inner-shadow" cx="55%" cy="100%" r="70%">
              <stop offset="0%" stopColor="rgba(0,0,0,0.35)" />
              <stop offset="60%" stopColor="rgba(0,0,0,0.08)" />
              <stop offset="100%" stopColor="rgba(0,0,0,0)" />
            </radialGradient>

            {/* Specular highlight gradient */}
            <radialGradient id="blob-specular" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="rgba(255,255,255,0.85)" />
              <stop offset="60%" stopColor="rgba(255,255,255,0.18)" />
              <stop offset="100%" stopColor="rgba(255,255,255,0)" />
            </radialGradient>

            {/* Clip body interior so face features can never bleed past edges */}
            <clipPath id="blob-body-clip">
              <rect
                x={BODY_X}
                y={BODY_Y}
                width={BODY_W}
                height={BODY_H}
                rx={BODY_RX}
                ry={BODY_RX}
              />
            </clipPath>
          </defs>

          {/* ── Body fill ─────────────────────────────────────────────── */}
          <rect
            x={BODY_X}
            y={BODY_Y}
            width={BODY_W}
            height={BODY_H}
            rx={BODY_RX}
            ry={BODY_RX}
            fill="url(#blob-body-grad)"
          />

          {/* ── Inner shadow at bottom (gives 3D weight) ──────────────── */}
          <rect
            x={BODY_X}
            y={BODY_Y}
            width={BODY_W}
            height={BODY_H}
            rx={BODY_RX}
            ry={BODY_RX}
            fill="url(#blob-inner-shadow)"
            opacity={isLight ? 0.7 : 0.85}
            clipPath="url(#blob-body-clip)"
          />

          {/* ── Specular highlight (top-left soft white blob) ─────────── */}
          <ellipse
            cx={BODY_X + 18}
            cy={BODY_Y + 14}
            rx={14}
            ry={9}
            fill="url(#blob-specular)"
            opacity={isLight ? 0.4 : 0.55}
            clipPath="url(#blob-body-clip)"
          />

          {/* Subtle rim highlight — 1px lighter line near top edge */}
          <rect
            x={BODY_X + 0.6}
            y={BODY_Y + 0.6}
            width={BODY_W - 1.2}
            height={BODY_H - 1.2}
            rx={BODY_RX - 0.6}
            ry={BODY_RX - 0.6}
            fill="none"
            stroke={isLight ? 'rgba(255,255,255,0.35)' : 'rgba(255,255,255,0.18)'}
            strokeWidth={0.6}
          />

          {/* ── Cheek blush (left + right) ────────────────────────────── */}
          {expr.blush > 0 && (
            <>
              <motion.ellipse
                cx={BODY_CX - CHEEK_OFFSET_X}
                cy={BODY_CY + CHEEK_OFFSET_Y}
                rx={5}
                ry={3.2}
                fill={blushColor}
                clipPath="url(#blob-body-clip)"
                animate={{ opacity: expr.blush * 0.55 }}
                transition={slowSpring}
              />
              <motion.ellipse
                cx={BODY_CX + CHEEK_OFFSET_X}
                cy={BODY_CY + CHEEK_OFFSET_Y}
                rx={5}
                ry={3.2}
                fill={blushColor}
                clipPath="url(#blob-body-clip)"
                animate={{ opacity: expr.blush * 0.55 }}
                transition={slowSpring}
              />
            </>
          )}

          {/* ── Left eyebrow ─────────────────────────────────────────── */}
          <motion.rect
            x={-BROW_LEN / 2}
            y={-BROW_THICKNESS / 2}
            width={BROW_LEN}
            height={BROW_THICKNESS}
            rx={BROW_THICKNESS / 2}
            ry={BROW_THICKNESS / 2}
            fill={browFill}
            initial={false}
            animate={{
              x: BODY_CX - EYE_OFFSET_X - BROW_LEN / 2,
              y: BROW_BASE_Y + expr.browLeftY - BROW_THICKNESS / 2,
              rotate: expr.browLeftAngle,
              opacity: expr.browOpacity,
            }}
            style={{ transformOrigin: 'center', transformBox: 'fill-box' }}
            transition={springConfig}
          />

          {/* ── Right eyebrow ────────────────────────────────────────── */}
          <motion.rect
            x={-BROW_LEN / 2}
            y={-BROW_THICKNESS / 2}
            width={BROW_LEN}
            height={BROW_THICKNESS}
            rx={BROW_THICKNESS / 2}
            ry={BROW_THICKNESS / 2}
            fill={browFill}
            initial={false}
            animate={{
              x: BODY_CX + EYE_OFFSET_X - BROW_LEN / 2,
              y: BROW_BASE_Y + expr.browRightY - BROW_THICKNESS / 2,
              rotate: expr.browRightAngle,
              opacity: expr.browOpacity,
            }}
            style={{ transformOrigin: 'center', transformBox: 'fill-box' }}
            transition={springConfig}
          />

          {/* ── Left eye ─────────────────────────────────────────────── */}
          <motion.g
            animate={{
              scaleX: expr.eyeScaleX,
              scaleY: eyeScaleYFinal,
            }}
            style={{
              transformOrigin: `${BODY_CX - EYE_OFFSET_X}px ${BODY_CY + EYE_OFFSET_Y}px`,
            }}
            transition={isBlinking
              ? { duration: 0.07, ease: 'easeOut' }
              : springConfig}
          >
            {/* Sclera (subtle background ring — gives the eye dimension) */}
            <ellipse
              cx={BODY_CX - EYE_OFFSET_X}
              cy={BODY_CY + EYE_OFFSET_Y}
              rx={EYE_BASE_R}
              ry={EYE_BASE_R}
              fill={isLight ? 'rgba(255, 250, 240, 0.92)' : 'rgba(245, 240, 250, 0.88)'}
            />

            {/* Pupil — heart shape for romantic mood, otherwise circle */}
            {expr.heartEyes ? (
              <motion.path
                d={heartPath}
                fill={blushColor}
                animate={{
                  x: BODY_CX - EYE_OFFSET_X + pupilDx,
                  y: BODY_CY + EYE_OFFSET_Y + pupilDy,
                }}
                style={{ transformOrigin: '0 0' }}
                transition={springConfig}
              />
            ) : (
              <motion.circle
                r={PUPIL_INNER_R}
                fill={eyeFill}
                animate={{
                  cx: BODY_CX - EYE_OFFSET_X + pupilDx,
                  cy: BODY_CY + EYE_OFFSET_Y + pupilDy,
                }}
                transition={springConfig}
              />
            )}

            {/* Specular highlight in pupil */}
            {!expr.heartEyes && (
              <motion.circle
                r={1.3}
                fill={eyeHighlight}
                opacity={0.95}
                animate={{
                  cx: BODY_CX - EYE_OFFSET_X + pupilDx + 1.4,
                  cy: BODY_CY + EYE_OFFSET_Y + pupilDy - 1.4,
                }}
                transition={springConfig}
              />
            )}
            {/* Tiny secondary highlight */}
            {!expr.heartEyes && (
              <motion.circle
                r={0.55}
                fill={eyeHighlight}
                opacity={0.8}
                animate={{
                  cx: BODY_CX - EYE_OFFSET_X + pupilDx - 1.6,
                  cy: BODY_CY + EYE_OFFSET_Y + pupilDy + 1.3,
                }}
                transition={springConfig}
              />
            )}
          </motion.g>

          {/* ── Right eye ────────────────────────────────────────────── */}
          <motion.g
            animate={{
              scaleX: expr.eyeScaleX,
              scaleY: expr.eyeWink > 0.5 ? 0.05 : eyeScaleYFinal,
            }}
            style={{
              transformOrigin: `${BODY_CX + EYE_OFFSET_X}px ${BODY_CY + EYE_OFFSET_Y}px`,
            }}
            transition={isBlinking
              ? { duration: 0.07, ease: 'easeOut' }
              : springConfig}
          >
            <ellipse
              cx={BODY_CX + EYE_OFFSET_X}
              cy={BODY_CY + EYE_OFFSET_Y}
              rx={EYE_BASE_R}
              ry={EYE_BASE_R}
              fill={isLight ? 'rgba(255, 250, 240, 0.92)' : 'rgba(245, 240, 250, 0.88)'}
            />

            {expr.heartEyes ? (
              <motion.path
                d={heartPath}
                fill={blushColor}
                animate={{
                  x: BODY_CX + EYE_OFFSET_X + pupilDx,
                  y: BODY_CY + EYE_OFFSET_Y + pupilDy,
                }}
                style={{ transformOrigin: '0 0' }}
                transition={springConfig}
              />
            ) : (
              <motion.circle
                r={PUPIL_INNER_R}
                fill={eyeFill}
                animate={{
                  cx: BODY_CX + EYE_OFFSET_X + pupilDx,
                  cy: BODY_CY + EYE_OFFSET_Y + pupilDy,
                }}
                transition={springConfig}
              />
            )}

            {!expr.heartEyes && (
              <motion.circle
                r={1.3}
                fill={eyeHighlight}
                opacity={0.95}
                animate={{
                  cx: BODY_CX + EYE_OFFSET_X + pupilDx + 1.4,
                  cy: BODY_CY + EYE_OFFSET_Y + pupilDy - 1.4,
                }}
                transition={springConfig}
              />
            )}
            {!expr.heartEyes && (
              <motion.circle
                r={0.55}
                fill={eyeHighlight}
                opacity={0.8}
                animate={{
                  cx: BODY_CX + EYE_OFFSET_X + pupilDx - 1.6,
                  cy: BODY_CY + EYE_OFFSET_Y + pupilDy + 1.3,
                }}
                transition={springConfig}
              />
            )}
          </motion.g>

          {/* ── Mouth ─────────────────────────────────────────────────── */}
          <motion.path
            d={mouthPath}
            fill={mouthOpenFinal > 0.25 ? mouthOpenFill : 'none'}
            stroke={mouthOpenFinal > 0.25 ? 'none' : mouthStroke}
            strokeWidth={1.6}
            strokeLinecap="round"
            strokeLinejoin="round"
            transition={springConfig}
          />

          {/* ── Sleeping "Z" particle (animated upward) ──────────────── */}
          {state === 'sleeping' && (
            <motion.text
              x={BODY_X + BODY_W - 8}
              y={BODY_Y + 10}
              fontFamily="ui-rounded, system-ui, sans-serif"
              fontSize="9"
              fontWeight="700"
              fill={a(0.6)}
              animate={{
                y: [BODY_Y + 10, BODY_Y - 6],
                opacity: [0, 0.85, 0],
                x: [BODY_X + BODY_W - 8, BODY_X + BODY_W - 2],
              }}
              transition={{
                duration: 3.2,
                repeat: Infinity,
                ease: 'easeOut',
                times: [0, 0.5, 1],
              }}
            >
              z
            </motion.text>
          )}
        </svg>
      </motion.div>
    </div>
  )
}
