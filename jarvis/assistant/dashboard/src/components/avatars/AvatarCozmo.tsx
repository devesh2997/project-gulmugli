/**
 * AvatarCozmo — A Cozmo/WALL-E inspired pixel face with expressive eyes.
 *
 * Parameterized eye shapes drive ~12 expressions. Five animation layers run
 * independently: expression, blink, gaze, breathing, and speaking. Everything
 * is SVG rects animated with framer-motion springs for a chunky-but-smooth
 * pixel-art feel.
 *
 * Colors come from CSS custom properties set by TokenProvider:
 *   --personality-accent      eye/brow/mouth fill
 *   --personality-glow_color  background radial glow
 */

import { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import { motion, useSpring, useTransform } from 'framer-motion'
import { useLightMode } from '../../hooks/useLightMode'
import type { AssistantState, AssistantMood } from '../../types/assistant'

// ─── Expression parameters ──────────────────────────────────────────────────

interface CozmoExpression {
  // Eye shape
  eyeWidth: number        // 8-14 pixels
  eyeHeight: number       // 4-12 pixels
  eyeRadiusX: number      // corner rounding 0-6
  eyeRadiusY: number      // corner rounding 0-6
  eyeSpacing: number      // gap between eyes 4-10

  // Eyelid closure (0=open, 1=closed)
  lidTop: number
  lidBottom: number

  // Pupil
  pupilX: number          // -1 to 1 (left-right gaze)
  pupilY: number          // -1 to 1 (up-down gaze)
  pupilSize: number       // 2-5 pixels

  // Eyebrow position (Y offset from eye top, negative = raised)
  browLeftY: number
  browRightY: number
  browLeftAngle: number   // rotation degrees
  browRightAngle: number

  // Mouth
  mouthWidth: number      // 3-10 pixels
  mouthHeight: number     // 1-4 pixels
  mouthCurve: number      // -1 (sad) to +1 (happy), 0 = flat
  mouthOpen: number       // 0-1 (for speaking/surprised)

  // Blush
  blush: number           // 0-1 opacity
}

// ─── State presets ──────────────────────────────────────────────────────────

const BASE: CozmoExpression = {
  eyeWidth: 10,
  eyeHeight: 8,
  eyeRadiusX: 3,
  eyeRadiusY: 3,
  eyeSpacing: 6,
  lidTop: 0,
  lidBottom: 0,
  pupilX: 0,
  pupilY: 0,
  pupilSize: 3,
  browLeftY: -3,
  browRightY: -3,
  browLeftAngle: 0,
  browRightAngle: 0,
  mouthWidth: 6,
  mouthHeight: 2,
  mouthCurve: 0.15,
  mouthOpen: 0,
  blush: 0,
}

const STATE_PRESETS: Record<AssistantState, Partial<CozmoExpression>> = {
  idle: {},
  listening: {
    eyeHeight: 10,
    pupilSize: 4,
    browLeftY: -4.5,
    browRightY: -4.5,
    mouthCurve: 0.2,
    mouthOpen: 0.15,
  },
  thinking: {
    eyeHeight: 6,
    browLeftY: -2,
    browRightY: -4,
    browLeftAngle: -8,
    browRightAngle: 5,
    pupilX: -0.4,
    pupilY: -0.5,
    mouthWidth: 4,
    mouthCurve: 0,
    mouthHeight: 1,
  },
  speaking: {
    eyeHeight: 8,
    mouthOpen: 0.6,
    mouthCurve: 0.1,
    mouthWidth: 7,
    mouthHeight: 3,
  },
  sleeping: {
    eyeHeight: 2,
    lidTop: 0.85,
    pupilSize: 2,
    browLeftY: -1,
    browRightY: -1,
    mouthWidth: 4,
    mouthHeight: 1,
    mouthCurve: 0.1,
  },
}

const MOOD_OVERLAYS: Record<AssistantMood, Partial<CozmoExpression>> = {
  neutral: {},
  happy: {
    eyeHeight: 7,
    eyeRadiusY: 4,
    mouthCurve: 0.8,
    mouthWidth: 8,
    mouthHeight: 2,
    blush: 0.3,
    browLeftY: -4,
    browRightY: -4,
  },
  sad: {
    eyeHeight: 7,
    browLeftAngle: 12,
    browRightAngle: -12,
    browLeftY: -2,
    browRightY: -2,
    mouthCurve: -0.7,
    mouthWidth: 5,
    pupilY: 0.4,
    blush: 0,
  },
  shy: {
    pupilX: 0.6,
    pupilY: 0.2,
    blush: 0.6,
    mouthCurve: 0.3,
    mouthWidth: 4,
    eyeHeight: 7,
    browLeftY: -2.5,
    browRightY: -2.5,
  },
  playful: {
    eyeHeight: 7,
    eyeRadiusY: 4,
    mouthCurve: 0.9,
    mouthWidth: 9,
    mouthHeight: 3,
    blush: 0.2,
    browLeftY: -5,
    browRightY: -3.5,
    browLeftAngle: -5,
  },
  sarcastic: {
    eyeHeight: 6,
    browLeftY: -2,
    browRightY: -5,
    browLeftAngle: -10,
    browRightAngle: 8,
    mouthCurve: 0.3,
    mouthWidth: 5,
    mouthHeight: 1,
    pupilX: 0.3,
  },
  surprised: {
    eyeHeight: 12,
    eyeWidth: 12,
    pupilSize: 4,
    browLeftY: -6,
    browRightY: -6,
    mouthOpen: 0.8,
    mouthCurve: 0,
    mouthWidth: 5,
    mouthHeight: 4,
  },
  romantic: {
    eyeHeight: 7,
    eyeRadiusY: 4,
    pupilSize: 4,
    mouthCurve: 0.5,
    blush: 0.5,
    browLeftY: -3.5,
    browRightY: -3.5,
  },
  gotcha: {
    eyeHeight: 6,
    browLeftY: -4,
    browRightY: -2,
    browLeftAngle: -6,
    browRightAngle: 3,
    mouthCurve: 0.6,
    mouthWidth: 8,
    pupilX: 0.2,
    blush: 0.15,
  },
}

// ─── Helpers ────────────────────────────────────────────────────────────────

/** Merge base + state + mood into a resolved expression. */
function resolveExpression(
  state: AssistantState,
  mood: AssistantMood,
): CozmoExpression {
  return {
    ...BASE,
    ...STATE_PRESETS[state],
    ...MOOD_OVERLAYS[mood],
  }
}

/** Clamp a value between min and max. */
function clamp(v: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, v))
}

// ─── Grid constants ─────────────────────────────────────────────────────────

const GRID_W = 48
const GRID_H = 32
const BLUSH_COLOR = '#ff6b9d'

// ─── Component ──────────────────────────────────────────────────────────────

export interface AvatarCozmoProps {
  size: number
  state: AssistantState
  mood: AssistantMood
}

export function AvatarCozmo({ size, state, mood }: AvatarCozmoProps) {
  const isLight = useLightMode()
  const expr = resolveExpression(state, mood)

  // ── Animation layer: Gaze drift (idle only) ────────────────────────────
  const [gazeX, setGazeX] = useState(0)
  const [gazeY, setGazeY] = useState(0)

  useEffect(() => {
    if (state !== 'idle') {
      setGazeX(0)
      setGazeY(0)
      return
    }
    const drift = () => {
      setGazeX((Math.random() - 0.5) * 0.6)
      setGazeY((Math.random() - 0.5) * 0.4)
    }
    drift()
    const id = setInterval(drift, 2000 + Math.random() * 2000)
    return () => clearInterval(id)
  }, [state])

  // ── Animation layer: Blink ─────────────────────────────────────────────
  const [isBlinking, setIsBlinking] = useState(false)

  useEffect(() => {
    if (state === 'sleeping') return
    let timerId: ReturnType<typeof setTimeout>
    const scheduleBlink = () => {
      const delay = 2500 + Math.random() * 3500
      timerId = setTimeout(() => {
        setIsBlinking(true)
        setTimeout(() => setIsBlinking(false), 120)
        scheduleBlink()
      }, delay)
    }
    scheduleBlink()
    return () => clearTimeout(timerId)
  }, [state])

  // ── Animation layer: Speaking mouth ────────────────────────────────────
  const [speakOpen, setSpeakOpen] = useState(false)

  useEffect(() => {
    if (state !== 'speaking') {
      setSpeakOpen(false)
      return
    }
    let timerId: ReturnType<typeof setTimeout>
    const cycle = () => {
      setSpeakOpen(prev => !prev)
      timerId = setTimeout(cycle, 120 + Math.random() * 180)
    }
    timerId = setTimeout(cycle, 100)
    return () => clearTimeout(timerId)
  }, [state])

  // ── Animation layer: Breathing scale ───────────────────────────────────
  // (handled via framer-motion animate on the SVG wrapper)

  // ── Resolve final animated params ──────────────────────────────────────
  const lidTopFinal = isBlinking ? 0.95 : expr.lidTop
  const mouthOpenFinal = state === 'speaking'
    ? (speakOpen ? 0.8 : 0.1)
    : expr.mouthOpen

  const pupilXFinal = state === 'idle'
    ? expr.pupilX + gazeX
    : expr.pupilX

  const pupilYFinal = state === 'idle'
    ? expr.pupilY + gazeY
    : expr.pupilY

  // ── Compute geometry (all in grid coordinates) ─────────────────────────
  const centerX = GRID_W / 2
  const centerY = GRID_H / 2 - 2 // eyes sit slightly above center

  const eyeW = expr.eyeWidth
  const eyeH = expr.eyeHeight
  const spacing = expr.eyeSpacing

  // Eye positions (top-left corners)
  const leftEyeX = centerX - spacing / 2 - eyeW
  const rightEyeX = centerX + spacing / 2
  const eyeY = centerY - eyeH / 2

  // Pupil positions within each eye
  const pSize = expr.pupilSize
  const pRangeX = (eyeW - pSize) / 2
  const pRangeY = (eyeH - pSize) / 2

  const leftPupilX = leftEyeX + eyeW / 2 - pSize / 2 + pupilXFinal * pRangeX
  const leftPupilY = eyeY + eyeH / 2 - pSize / 2 + pupilYFinal * pRangeY
  const rightPupilX = rightEyeX + eyeW / 2 - pSize / 2 + pupilXFinal * pRangeX
  const rightPupilY = eyeY + eyeH / 2 - pSize / 2 + pupilYFinal * pRangeY

  // Eyelid clip rects (top lid closes downward, bottom lid closes upward)
  const lidTopH = lidTopFinal * eyeH
  const lidBottomH = expr.lidBottom * eyeH

  // Eyebrow geometry
  const browWidth = eyeW * 0.8
  const browThickness = 1.5
  const leftBrowX = leftEyeX + (eyeW - browWidth) / 2
  const rightBrowX = rightEyeX + (eyeW - browWidth) / 2
  const leftBrowY = eyeY + expr.browLeftY
  const rightBrowY = eyeY + expr.browRightY

  // Mouth geometry
  const mouthY = centerY + eyeH / 2 + 4
  const mouthX = centerX - expr.mouthWidth / 2
  const mH = expr.mouthHeight + mouthOpenFinal * 3

  // Blush positions (below-outside each eye)
  const blushSize = 3
  const leftBlushX = leftEyeX - 1
  const leftBlushY = eyeY + eyeH + 1
  const rightBlushX = rightEyeX + eyeW - blushSize + 1
  const rightBlushY = leftBlushY

  // ── Pixel scale ────────────────────────────────────────────────────────
  // The viewBox is GRID_W x GRID_H. The SVG is rendered at `size` px wide.
  // This means each grid unit = size / GRID_W actual pixels.

  const accent = isLight ? '#2a1a0a' : 'var(--personality-accent)'
  const accentDim = isLight ? '#5a4a3a' : 'var(--personality-accent)'
  const pupilColor = isLight ? '#4a3a2a' : 'var(--personality-accent)'
  const glow = 'var(--personality-glow_color)'

  // Spring config for expression transitions
  const springConfig = { stiffness: 300, damping: 22, mass: 0.8 }
  const slowSpring = { stiffness: 120, damping: 20, mass: 1 }

  // Breathing animation values
  const breatheScale = state === 'sleeping'
    ? { scale: [1, 1.015, 1] }
    : state === 'idle'
      ? { scale: [1, 1.02, 1] }
      : {}
  const breatheDuration = state === 'sleeping' ? 5 : 4

  // Glow configs per state
  const glowOpacity = state === 'sleeping' ? 0.05
    : state === 'idle' ? 0.15
    : state === 'listening' ? 0.35
    : state === 'speaking' ? 0.4
    : state === 'thinking' ? 0.25
    : 0.15
  const glowScale = state === 'listening' ? 1.15
    : state === 'speaking' ? 1.2
    : state === 'sleeping' ? 0.85
    : 1

  // Mouth path for curved shapes
  const mouthPath = useMemo(() => {
    const mw = expr.mouthWidth
    const curve = expr.mouthCurve
    const openH = mH

    const mx = centerX - mw / 2
    const my = mouthY

    if (mouthOpenFinal > 0.3) {
      // Open mouth: ellipse-ish
      const rx = mw / 2
      const ry = openH / 2
      const cx = centerX
      const cy = my + ry * 0.3
      return `M ${cx - rx} ${cy} Q ${cx - rx} ${cy + ry} ${cx} ${cy + ry} Q ${cx + rx} ${cy + ry} ${cx + rx} ${cy} Q ${cx + rx} ${cy - ry * 0.5} ${cx} ${cy - ry * 0.5} Q ${cx - rx} ${cy - ry * 0.5} ${cx - rx} ${cy} Z`
    }

    // Curved line mouth
    const startX = mx
    const startY = my
    const endX = mx + mw
    const endY = my
    const cpY = my + curve * 4
    return `M ${startX} ${startY} Q ${centerX} ${cpY} ${endX} ${endY}`
  }, [expr.mouthWidth, expr.mouthCurve, mH, mouthOpenFinal, centerX, mouthY])

  // ── SVG movement per state ─────────────────────────────────────────────
  const svgAnimate = state === 'idle'
    ? { y: [0, -1.5, 0, 0.8, 0] }
    : state === 'speaking'
      ? { y: [0, -1, 0.5, -0.5, 0] }
      : state === 'listening'
        ? { y: -1 }
        : state === 'thinking'
          ? { y: [0, 0.5, 0] }
          : { y: 0 }

  const svgTransition = state === 'idle'
    ? { duration: 4, repeat: Infinity, ease: 'easeInOut' as const }
    : state === 'speaking'
      ? { duration: 1, repeat: Infinity, ease: 'easeInOut' as const }
      : state === 'listening'
        ? { type: 'spring' as const, stiffness: 400, damping: 15 }
        : state === 'thinking'
          ? { duration: 2.5, repeat: Infinity, ease: 'easeInOut' as const }
          : { duration: 0.3 }

  return (
    <div
      className="relative flex items-center justify-center"
      style={{ width: size * 2, height: size * 2 }}
    >
      {/* Background glow */}
      <motion.div
        className="absolute rounded-full"
        style={{
          width: size * 1.4,
          height: size * 1.4,
          background: isLight
            ? 'radial-gradient(circle, rgba(0,0,0,0.06) 0%, transparent 70%)'
            : `radial-gradient(circle, ${glow} 0%, transparent 70%)`,
          filter: `blur(${size * 0.25}px)`,
        }}
        animate={{
          opacity: [glowOpacity, glowOpacity * 0.5, glowOpacity],
          scale: [glowScale, glowScale * 1.08, glowScale],
        }}
        transition={{
          duration: breatheDuration,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
      />

      {/* Face SVG */}
      <motion.div
        animate={breatheScale}
        transition={{
          duration: breatheDuration,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
      >
        <motion.svg
          viewBox={`0 0 ${GRID_W} ${GRID_H}`}
          width={size}
          height={size * (GRID_H / GRID_W)}
          shapeRendering="crispEdges"
          style={{
            filter: isLight ? 'drop-shadow(0 0 0.8px rgba(0,0,0,0.25))' : 'none',
          }}
          animate={svgAnimate}
          transition={svgTransition}
        >
          <defs>
            {/* Clip paths for eyelids — one per eye */}
            <clipPath id="cozmo-left-eye-clip">
              <rect
                x={leftEyeX - 1}
                y={eyeY + lidTopH}
                width={eyeW + 2}
                height={eyeH - lidTopH - lidBottomH}
              />
            </clipPath>
            <clipPath id="cozmo-right-eye-clip">
              <rect
                x={rightEyeX - 1}
                y={eyeY + lidTopH}
                width={eyeW + 2}
                height={eyeH - lidTopH - lidBottomH}
              />
            </clipPath>
          </defs>

          {/* ── Left eyebrow ──────────────────────────────────────── */}
          <motion.rect
            x={leftBrowX}
            width={browWidth}
            height={browThickness}
            rx={0.5}
            fill={accentDim}
            style={{ opacity: 0.6 }}
            animate={{
              y: leftBrowY,
              rotate: expr.browLeftAngle,
            }}
            transition={springConfig}
          />

          {/* ── Right eyebrow ─────────────────────────────────────── */}
          <motion.rect
            x={rightBrowX}
            width={browWidth}
            height={browThickness}
            rx={0.5}
            fill={accentDim}
            style={{ opacity: 0.6 }}
            animate={{
              y: rightBrowY,
              rotate: expr.browRightAngle,
            }}
            transition={springConfig}
          />

          {/* ── Left eye (sclera) ─────────────────────────────────── */}
          <motion.rect
            x={leftEyeX}
            fill={accent}
            style={{ opacity: 0.15 }}
            clipPath="url(#cozmo-left-eye-clip)"
            animate={{
              y: eyeY,
              width: eyeW,
              height: eyeH,
              rx: expr.eyeRadiusX,
              ry: expr.eyeRadiusY,
            }}
            transition={springConfig}
          />

          {/* ── Left pupil ────────────────────────────────────────── */}
          <motion.rect
            fill={accent}
            clipPath="url(#cozmo-left-eye-clip)"
            animate={{
              x: leftPupilX,
              y: leftPupilY,
              width: pSize,
              height: pSize,
              rx: pSize * 0.3,
              ry: pSize * 0.3,
            }}
            transition={springConfig}
          />

          {/* ── Left eye highlight (specular) ─────────────────────── */}
          <motion.rect
            fill={isLight ? '#ffffff' : '#ffffff'}
            style={{ opacity: isLight ? 0.5 : 0.35 }}
            clipPath="url(#cozmo-left-eye-clip)"
            animate={{
              x: leftPupilX + pSize * 0.5,
              y: leftPupilY - pSize * 0.15,
              width: pSize * 0.35,
              height: pSize * 0.35,
              rx: pSize * 0.15,
              ry: pSize * 0.15,
            }}
            transition={springConfig}
          />

          {/* ── Right eye (sclera) ────────────────────────────────── */}
          <motion.rect
            x={rightEyeX}
            fill={accent}
            style={{ opacity: 0.15 }}
            clipPath="url(#cozmo-right-eye-clip)"
            animate={{
              y: eyeY,
              width: eyeW,
              height: eyeH,
              rx: expr.eyeRadiusX,
              ry: expr.eyeRadiusY,
            }}
            transition={springConfig}
          />

          {/* ── Right pupil ───────────────────────────────────────── */}
          <motion.rect
            fill={accent}
            clipPath="url(#cozmo-right-eye-clip)"
            animate={{
              x: rightPupilX,
              y: rightPupilY,
              width: pSize,
              height: pSize,
              rx: pSize * 0.3,
              ry: pSize * 0.3,
            }}
            transition={springConfig}
          />

          {/* ── Right eye highlight (specular) ────────────────────── */}
          <motion.rect
            fill="#ffffff"
            style={{ opacity: isLight ? 0.5 : 0.35 }}
            clipPath="url(#cozmo-right-eye-clip)"
            animate={{
              x: rightPupilX + pSize * 0.5,
              y: rightPupilY - pSize * 0.15,
              width: pSize * 0.35,
              height: pSize * 0.35,
              rx: pSize * 0.15,
              ry: pSize * 0.15,
            }}
            transition={springConfig}
          />

          {/* ── Left eyelid (top) ─────────────────────────────────── */}
          <motion.rect
            x={leftEyeX - 0.5}
            width={eyeW + 1}
            fill={isLight ? '#f5f0e8' : '#0d0d0d'}
            animate={{
              y: eyeY - 0.5,
              height: lidTopH + 0.5,
            }}
            transition={{ stiffness: 500, damping: 25, mass: 0.5 }}
          />

          {/* ── Right eyelid (top) ────────────────────────────────── */}
          <motion.rect
            x={rightEyeX - 0.5}
            width={eyeW + 1}
            fill={isLight ? '#f5f0e8' : '#0d0d0d'}
            animate={{
              y: eyeY - 0.5,
              height: lidTopH + 0.5,
            }}
            transition={{ stiffness: 500, damping: 25, mass: 0.5 }}
          />

          {/* ── Mouth ─────────────────────────────────────────────── */}
          <motion.path
            d={mouthPath}
            fill={mouthOpenFinal > 0.3 ? accent : 'none'}
            stroke={accent}
            strokeWidth={mouthOpenFinal > 0.3 ? 0 : 1.2}
            strokeLinecap="round"
            style={{ opacity: 0.7 }}
            transition={springConfig}
          />

          {/* ── Blush (left cheek) ────────────────────────────────── */}
          {expr.blush > 0 && (
            <>
              <motion.rect
                x={leftBlushX}
                y={leftBlushY}
                width={blushSize}
                height={blushSize * 0.6}
                rx={1}
                ry={1}
                fill={BLUSH_COLOR}
                animate={{ opacity: expr.blush * 0.4 }}
                transition={slowSpring}
              />
              <motion.rect
                x={leftBlushX + 0.5}
                y={leftBlushY + 0.8}
                width={blushSize - 1}
                height={blushSize * 0.4}
                rx={0.5}
                ry={0.5}
                fill={BLUSH_COLOR}
                animate={{ opacity: expr.blush * 0.25 }}
                transition={slowSpring}
              />
            </>
          )}

          {/* ── Blush (right cheek) ───────────────────────────────── */}
          {expr.blush > 0 && (
            <>
              <motion.rect
                x={rightBlushX}
                y={rightBlushY}
                width={blushSize}
                height={blushSize * 0.6}
                rx={1}
                ry={1}
                fill={BLUSH_COLOR}
                animate={{ opacity: expr.blush * 0.4 }}
                transition={slowSpring}
              />
              <motion.rect
                x={rightBlushX + 0.5}
                y={rightBlushY + 0.8}
                width={blushSize - 1}
                height={blushSize * 0.4}
                rx={0.5}
                ry={0.5}
                fill={BLUSH_COLOR}
                animate={{ opacity: expr.blush * 0.25 }}
                transition={slowSpring}
              />
            </>
          )}
        </motion.svg>
      </motion.div>
    </div>
  )
}
