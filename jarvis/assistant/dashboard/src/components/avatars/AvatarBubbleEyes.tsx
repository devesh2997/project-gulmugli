/**
 * AvatarBubbleEyes — Cozmo/Vector/Eilik-inspired premium bubble eyes.
 *
 * Two large gradient-filled rounded squares with depth, soft shadows,
 * glass-like specular highlights, and rich state-driven shape changes.
 * Eyes-only — no mouth, no other features. The eyes ARE the avatar.
 *
 * Layered rendering (back to front):
 *   1. Outer glow halo (radial blur, personality accent)
 *   2. Soft shadow underneath (gives weight)
 *   3. Eye body (vertical linear gradient, bright top → darker bottom)
 *   4. Inner radial overlay (ambient light from upper-left)
 *   5. Pupil (dark vertical gradient ellipse)
 *   6. Specular highlights (two: big upper-left, small bottom-right)
 *   7. Top reflection arc (polished glass feel)
 *
 * Animation layers:
 *   - Breathing scale (idle/sleeping)
 *   - Random saccades (pupil micro-shifts)
 *   - Random blinks (eyelid pass)
 *   - State-driven scale, pupil dilation, gaze direction
 *   - Mood-driven shape squints, blush, heart pupils
 *
 * Colors come from CSS custom properties set by TokenProvider:
 *   --personality-accent      eye fill (top of gradient)
 *   --personality-accent-rgb  same as RGB triplet for alpha math
 *   --personality-glow_color  outer glow halo
 */

import { useState, useEffect, useId, useMemo } from 'react'
import { motion } from 'framer-motion'
import { useLightMode } from '../../hooks/useLightMode'
import type { AssistantState, AssistantMood } from '../../types/assistant'

export interface AvatarBubbleEyesProps {
  size: number
  state: AssistantState
  mood: AssistantMood
}

// ─── Geometry constants (in 100×100 viewBox units) ──────────────────────────

const VB = 100
const EYE_W = 36
const EYE_H = 36
const EYE_RADIUS = 8
const EYE_GAP = 12
const EYE_CY = 50
// Pupil base size
const PUPIL_W = 14
const PUPIL_H = 16

// Centers
const LEFT_EYE_CX = VB / 2 - EYE_GAP / 2 - EYE_W / 2
const RIGHT_EYE_CX = VB / 2 + EYE_GAP / 2 + EYE_W / 2

// Blush
const BLUSH_COLOR = '#ff7eb6'

// ─── State configurations ────────────────────────────────────────────────────

interface StateConfig {
  eyeScale: number          // overall eye scale
  eyeScaleY: number         // independent y-axis squish
  pupilScale: number        // pupil size multiplier
  pupilGazeX: number        // -1 to 1 (left to right) within eye
  pupilGazeY: number        // -1 to 1 (up to down) within eye
  glowAlpha: number         // outer halo intensity
  bodyAlpha: number         // eye body alpha multiplier
  warmShift: number         // 0..1, blends accent toward warm orange
  translateY: number        // vertical lean offset (in viewBox units)
  breatheDuration: number   // seconds
  breatheAmount: number     // scale variation
  saccadeIntervalMs: number // how often pupils micro-shift
  saccadeRange: number      // size of saccade in viewBox units
}

const STATE_CONFIGS: Record<AssistantState, StateConfig> = {
  idle: {
    eyeScale: 1,
    eyeScaleY: 1,
    pupilScale: 1,
    pupilGazeX: 0,
    pupilGazeY: 0,
    glowAlpha: 0.6,
    bodyAlpha: 1,
    warmShift: 0,
    translateY: 0,
    breatheDuration: 4,
    breatheAmount: 0.03,
    saccadeIntervalMs: 2500,
    saccadeRange: 2.5,
  },
  listening: {
    eyeScale: 1.1,
    eyeScaleY: 1.1,
    pupilScale: 1.15,
    pupilGazeX: 0,
    pupilGazeY: -0.3,
    glowAlpha: 0.85,
    bodyAlpha: 1,
    warmShift: 0,
    translateY: -2,
    breatheDuration: 2.5,
    breatheAmount: 0.025,
    saccadeIntervalMs: 4000,
    saccadeRange: 1.2,
  },
  thinking: {
    eyeScale: 0.95,
    eyeScaleY: 0.9,
    pupilScale: 1,
    pupilGazeX: 0.55,
    pupilGazeY: -0.55,
    glowAlpha: 0.5,
    bodyAlpha: 0.95,
    warmShift: 0.35,
    translateY: 0,
    breatheDuration: 3.5,
    breatheAmount: 0.02,
    saccadeIntervalMs: 1500,
    saccadeRange: 5,
  },
  speaking: {
    eyeScale: 1.02,
    eyeScaleY: 1,
    pupilScale: 1,
    pupilGazeX: 0,
    pupilGazeY: 0,
    glowAlpha: 1.0,
    bodyAlpha: 1,
    warmShift: 0,
    translateY: 0,
    breatheDuration: 0.4,
    breatheAmount: 0.03,
    saccadeIntervalMs: 5000,
    saccadeRange: 0.8,
  },
  sleeping: {
    eyeScale: 1,
    eyeScaleY: 1,
    pupilScale: 0,
    pupilGazeX: 0,
    pupilGazeY: 0,
    glowAlpha: 0.15,
    bodyAlpha: 0.7,
    warmShift: 0,
    translateY: 0,
    breatheDuration: 6,
    breatheAmount: 0.018,
    saccadeIntervalMs: 99999,
    saccadeRange: 0,
  },
}

// ─── Mood configurations ─────────────────────────────────────────────────────

interface MoodConfig {
  squintY: number           // multiplied with eyeScaleY (e.g. 0.75 = squint)
  pupilOffsetX: number      // additional viewBox offset for pupil (left+right symmetric)
  pupilOffsetXAsym: number  // asymmetric — only applied to one eye for "shy" or "gotcha"
  pupilOffsetY: number      // additional viewBox offset for pupil
  pupilSizeMod: number      // multiplier on pupil size (1 = unchanged)
  blushAlpha: number        // 0..1
  glowMultiplier: number    // multiplies state glowAlpha
  asymmetricScale: boolean  // one eye 105%, other 95%
  heartPupil: boolean       // replace pupil with heart
  pinkGlow: boolean         // pink halo instead of accent
  raisedBrow: 'left' | 'right' | null  // small wedge above one eye
  squintOneEye: 'left' | 'right' | null  // narrow only one eye
  saccadeMultiplier: number // multiplier on saccade frequency (smaller = faster)
  saccadeRangeMultiplier: number
  winkEnabled: boolean      // occasional one-eye blink
  rollEyes: boolean         // periodic upward eye-roll
}

const BASE_MOOD: MoodConfig = {
  squintY: 1,
  pupilOffsetX: 0,
  pupilOffsetXAsym: 0,
  pupilOffsetY: 0,
  pupilSizeMod: 1,
  blushAlpha: 0,
  glowMultiplier: 1,
  asymmetricScale: false,
  heartPupil: false,
  pinkGlow: false,
  raisedBrow: null,
  squintOneEye: null,
  saccadeMultiplier: 1,
  saccadeRangeMultiplier: 1,
  winkEnabled: false,
  rollEyes: false,
}

const MOOD_CONFIGS: Record<AssistantMood, MoodConfig> = {
  neutral: { ...BASE_MOOD },
  happy: {
    ...BASE_MOOD,
    squintY: 0.75,
    pupilSizeMod: 0.9,
    blushAlpha: 0.3,
  },
  sad: {
    ...BASE_MOOD,
    pupilOffsetY: 4.5,
    glowMultiplier: 0.5,
  },
  shy: {
    ...BASE_MOOD,
    squintY: 0.8,
    pupilOffsetXAsym: 9,
    blushAlpha: 0.45,
  },
  playful: {
    ...BASE_MOOD,
    pupilSizeMod: 1.05,
    asymmetricScale: true,
    saccadeMultiplier: 0.4,
    saccadeRangeMultiplier: 1.6,
    winkEnabled: true,
  },
  sarcastic: {
    ...BASE_MOOD,
    asymmetricScale: true,
    rollEyes: true,
    squintOneEye: 'right',
  },
  surprised: {
    ...BASE_MOOD,
    squintY: 1.2,
    pupilSizeMod: 1.6,
  },
  romantic: {
    ...BASE_MOOD,
    heartPupil: true,
    pinkGlow: true,
    blushAlpha: 0.3,
  },
  gotcha: {
    ...BASE_MOOD,
    squintOneEye: 'left',
    raisedBrow: 'left',
    pupilOffsetXAsym: 5,
  },
}

// ─── Component ───────────────────────────────────────────────────────────────

export function AvatarBubbleEyes({ size, state, mood }: AvatarBubbleEyesProps) {
  const isLight = useLightMode()
  const stateConfig = STATE_CONFIGS[state] ?? STATE_CONFIGS.idle
  const moodConfig = MOOD_CONFIGS[mood] ?? MOOD_CONFIGS.neutral

  // Unique id suffix to avoid <defs> collisions when multiple instances render
  const uid = useId().replace(/[:]/g, '')

  // ── Saccade (random pupil micro-shifts) ────────────────────────────────
  const [saccadeOffset, setSaccadeOffset] = useState({ x: 0, y: 0 })

  useEffect(() => {
    if (state === 'sleeping') {
      setSaccadeOffset({ x: 0, y: 0 })
      return
    }
    const interval = stateConfig.saccadeIntervalMs * moodConfig.saccadeMultiplier
    const range = stateConfig.saccadeRange * moodConfig.saccadeRangeMultiplier
    const tick = () => {
      setSaccadeOffset({
        x: (Math.random() - 0.5) * 2 * range,
        y: (Math.random() - 0.5) * 2 * range,
      })
    }
    tick()
    const id = setInterval(tick, interval + Math.random() * (interval * 0.5))
    return () => clearInterval(id)
  }, [state, stateConfig.saccadeIntervalMs, stateConfig.saccadeRange,
      moodConfig.saccadeMultiplier, moodConfig.saccadeRangeMultiplier])

  // ── Blink ──────────────────────────────────────────────────────────────
  const [blinkProgress, setBlinkProgress] = useState(0) // 0=open, 1=closed
  const [winkSide, setWinkSide] = useState<'none' | 'left' | 'right'>('none')

  useEffect(() => {
    if (state === 'sleeping') {
      setBlinkProgress(0)
      return
    }
    let timerId: ReturnType<typeof setTimeout>
    const scheduleBlink = () => {
      const delay = 4000 + Math.random() * 2500
      timerId = setTimeout(() => {
        // Possibly wink (one eye only) for playful mood
        if (moodConfig.winkEnabled && Math.random() < 0.4) {
          const side: 'left' | 'right' = Math.random() < 0.5 ? 'left' : 'right'
          setWinkSide(side)
          setBlinkProgress(1)
          setTimeout(() => {
            setBlinkProgress(0)
            setTimeout(() => setWinkSide('none'), 50)
          }, 180)
        } else {
          setWinkSide('none')
          setBlinkProgress(1)
          setTimeout(() => setBlinkProgress(0), 180)
        }
        scheduleBlink()
      }, delay)
    }
    scheduleBlink()
    return () => clearTimeout(timerId)
  }, [state, moodConfig.winkEnabled])

  // ── Sarcastic eye-roll ─────────────────────────────────────────────────
  const [rollOffset, setRollOffset] = useState(0) // 0..1 of upward roll

  useEffect(() => {
    if (!moodConfig.rollEyes || state === 'sleeping') {
      setRollOffset(0)
      return
    }
    let timerId: ReturnType<typeof setTimeout>
    const scheduleRoll = () => {
      const delay = 3000 + Math.random() * 2500
      timerId = setTimeout(() => {
        setRollOffset(1)
        setTimeout(() => setRollOffset(0), 600)
        scheduleRoll()
      }, delay)
    }
    scheduleRoll()
    return () => clearTimeout(timerId)
  }, [moodConfig.rollEyes, state])

  // ── Speaking pulse (alpha cycle) ───────────────────────────────────────
  // (handled via framer-motion animate prop on the body group)

  // ── Compute resolved values ────────────────────────────────────────────

  // Final pupil offsets from gaze + saccade + mood (left eye, right eye)
  const baseGazeX = stateConfig.pupilGazeX * (EYE_W / 2 - PUPIL_W / 2)
  const baseGazeY = stateConfig.pupilGazeY * (EYE_H / 2 - PUPIL_H / 2)
                   - rollOffset * 8 // rolling eyes upward

  const leftPupilDx = baseGazeX + saccadeOffset.x + moodConfig.pupilOffsetX
                    + moodConfig.pupilOffsetXAsym
  const rightPupilDx = baseGazeX + saccadeOffset.x + moodConfig.pupilOffsetX
                     + moodConfig.pupilOffsetXAsym
  const pupilDy = baseGazeY + saccadeOffset.y + moodConfig.pupilOffsetY

  const finalPupilScale = stateConfig.pupilScale * moodConfig.pupilSizeMod

  // Glow color
  const glowColor = moodConfig.pinkGlow
    ? `rgba(255, 126, 182, ${stateConfig.glowAlpha * moodConfig.glowMultiplier * 0.5})`
    : 'var(--personality-glow_color)'

  // Eye body fill: linear gradient from accent (top) to darker accent (bottom)
  // Use color-mix to incorporate warm shift for thinking state
  const accentVar = 'var(--personality-accent)'
  const accentRgb = 'var(--personality-accent-rgb)'

  // Helper for accent rgba
  const a = (op: number) => `rgba(${accentRgb}, ${op})`

  // Warm-shifted accent (used for thinking state)
  const warmShift = stateConfig.warmShift
  const eyeTopColor = warmShift > 0
    ? `color-mix(in srgb, ${accentVar} ${Math.round((1 - warmShift) * 100)}%, #ffa83c)`
    : accentVar
  const eyeBottomColor = warmShift > 0
    ? `color-mix(in srgb, ${a(0.6)} ${Math.round((1 - warmShift) * 100)}%, rgba(255, 168, 60, 0.55))`
    : a(0.55)

  // Light mode: slightly darker eyes for legibility on light backgrounds.
  // CSS vars still drive the personality color in both modes — we only adjust
  // the dim end of the gradient.
  const eyeBottomFinal = isLight ? a(0.7) : eyeBottomColor

  // ── Memoized heart pupil path (centered at 0,0; scale to PUPIL size) ───
  const heartPath = useMemo(() => {
    // Heart with width ~14, height ~14 — designed in local coords
    return 'M 0 -2 C -3 -5, -7 -3.5, -7 1 C -7 5, 0 9, 0 9 C 0 9, 7 5, 7 1 C 7 -3.5, 3 -5, 0 -2 Z'
  }, [])

  // Per-eye scale modifiers (asymmetry for playful/sarcastic)
  const leftAsymScale = moodConfig.asymmetricScale ? 1.05 : 1
  const rightAsymScale = moodConfig.asymmetricScale ? 0.95 : 1

  // Per-eye Y squint (one-eye squint for sarcastic/gotcha)
  const leftSquintY = moodConfig.squintOneEye === 'left'
    ? moodConfig.squintY * 0.65
    : moodConfig.squintY
  const rightSquintY = moodConfig.squintOneEye === 'right'
    ? moodConfig.squintY * 0.65
    : moodConfig.squintY

  // For wink: collapse one eye fully
  const leftBlinkAmount = winkSide === 'right' ? 0
    : winkSide === 'left' ? blinkProgress
    : blinkProgress
  const rightBlinkAmount = winkSide === 'left' ? 0
    : winkSide === 'right' ? blinkProgress
    : blinkProgress

  // Sleeping eyelid (covers ~85% of the eye from top)
  const sleepingLidHeight = state === 'sleeping' ? EYE_H * 0.85 : 0

  // Speaking pulse on body alpha
  const speakingPulse = state === 'speaking'
    ? { opacity: [stateConfig.bodyAlpha * 0.85, stateConfig.bodyAlpha, stateConfig.bodyAlpha * 0.85] }
    : { opacity: stateConfig.bodyAlpha }
  const speakingPulseTransition = state === 'speaking'
    ? { duration: 0.4, repeat: Infinity, ease: 'easeInOut' as const }
    : { duration: 0.3 }

  // Glow halo animation (breathe)
  const glowFinalAlpha = stateConfig.glowAlpha * moodConfig.glowMultiplier

  // ── Render helpers ─────────────────────────────────────────────────────

  /**
   * Renders one eye. The eye is positioned at (cx, cy) and scaled/squinted
   * via a transform. Includes all 7 layers from the design.
   */
  const renderEye = (
    eyeId: 'left' | 'right',
    cx: number,
    pupilDx: number,
    asymScale: number,
    squintY: number,
    blinkAmount: number,
  ) => {
    const eyeX = cx - EYE_W / 2
    const eyeY = EYE_CY - EYE_H / 2
    const lidHeight = blinkAmount * EYE_H + sleepingLidHeight

    return (
      <motion.g
        key={eyeId}
        animate={{
          scale: stateConfig.eyeScale * asymScale,
          y: stateConfig.translateY,
        }}
        transition={{ type: 'spring', stiffness: 200, damping: 22 }}
        style={{ transformOrigin: `${cx}px ${EYE_CY}px`, transformBox: 'fill-box' }}
      >
        <motion.g
          animate={{ scaleY: stateConfig.eyeScaleY * squintY }}
          transition={{ type: 'spring', stiffness: 200, damping: 22 }}
          style={{ transformOrigin: `${cx}px ${EYE_CY}px`, transformBox: 'fill-box' }}
        >
          {/* Layer 1: Outer glow halo (radial blur) */}
          <motion.ellipse
            cx={cx}
            cy={EYE_CY}
            rx={EYE_W / 2 + 10}
            ry={EYE_H / 2 + 10}
            fill={`url(#bubble-glow-${eyeId}-${uid})`}
            filter={`url(#bubble-blur-${uid})`}
            animate={{ opacity: [glowFinalAlpha * 0.7, glowFinalAlpha, glowFinalAlpha * 0.7] }}
            transition={{
              duration: stateConfig.breatheDuration * 1.2,
              repeat: Infinity,
              ease: 'easeInOut' as const,
            }}
          />

          {/* Layer 2: Soft shadow underneath */}
          <ellipse
            cx={cx}
            cy={EYE_CY + EYE_H / 2 - 1}
            rx={EYE_W / 2 - 1}
            ry={3.5}
            fill="rgba(0, 0, 0, 0.28)"
            filter={`url(#bubble-blur-${uid})`}
          />

          {/* Layer 3: Eye body — vertical linear gradient */}
          <motion.rect
            x={eyeX}
            y={eyeY}
            width={EYE_W}
            height={EYE_H}
            rx={EYE_RADIUS}
            ry={EYE_RADIUS}
            fill={`url(#bubble-body-${eyeId}-${uid})`}
            clipPath={`url(#bubble-clip-${eyeId}-${uid})`}
            animate={speakingPulse}
            transition={speakingPulseTransition}
          />

          {/* Layer 4: Inner radial overlay (ambient light from upper-left) */}
          <rect
            x={eyeX}
            y={eyeY}
            width={EYE_W}
            height={EYE_H}
            rx={EYE_RADIUS}
            ry={EYE_RADIUS}
            fill={`url(#bubble-ambient-${eyeId}-${uid})`}
            clipPath={`url(#bubble-clip-${eyeId}-${uid})`}
          />

          {/* Layer 5–6: Pupil + specular highlights, hidden when sleeping */}
          {state !== 'sleeping' && finalPupilScale > 0 && (
            <motion.g
              clipPath={`url(#bubble-clip-${eyeId}-${uid})`}
              animate={{
                x: pupilDx,
                y: pupilDy,
                scale: finalPupilScale,
              }}
              transition={{ type: 'spring', stiffness: 220, damping: 20 }}
              style={{ transformOrigin: `${cx}px ${EYE_CY}px`, transformBox: 'fill-box' }}
            >
              {moodConfig.heartPupil ? (
                // Heart-shaped pupil
                <g transform={`translate(${cx}, ${EYE_CY}) scale(0.95)`}>
                  <path
                    d={heartPath}
                    fill={`url(#bubble-heart-${uid})`}
                  />
                  {/* Heart highlight */}
                  <ellipse
                    cx={-2}
                    cy={-1}
                    rx={1.8}
                    ry={2.4}
                    fill="rgba(255, 255, 255, 0.7)"
                    filter={`url(#bubble-blur-tiny-${uid})`}
                  />
                </g>
              ) : (
                <>
                  {/* Pupil ellipse with vertical gradient */}
                  <ellipse
                    cx={cx}
                    cy={EYE_CY}
                    rx={PUPIL_W / 2}
                    ry={PUPIL_H / 2}
                    fill={`url(#bubble-pupil-${uid})`}
                  />
                  {/* Big specular highlight (top-left of pupil) */}
                  <ellipse
                    cx={cx - PUPIL_W * 0.25}
                    cy={EYE_CY - PUPIL_H * 0.28}
                    rx={2.5}
                    ry={3.5}
                    fill="rgba(255, 255, 255, 0.85)"
                    filter={`url(#bubble-blur-tiny-${uid})`}
                  />
                  {/* Small specular highlight (bottom-right) */}
                  <ellipse
                    cx={cx + PUPIL_W * 0.22}
                    cy={EYE_CY + PUPIL_H * 0.25}
                    rx={1}
                    ry={1.5}
                    fill="rgba(255, 255, 255, 0.6)"
                  />
                </>
              )}
            </motion.g>
          )}

          {/* Layer 7: Top reflection arc (polished glass) */}
          <path
            d={`M ${eyeX + 6} ${eyeY + 5}
                Q ${cx} ${eyeY + 1.5}
                  ${eyeX + EYE_W - 6} ${eyeY + 5}`}
            stroke="rgba(255, 255, 255, 0.55)"
            strokeWidth={1.6}
            strokeLinecap="round"
            fill="none"
            clipPath={`url(#bubble-clip-${eyeId}-${uid})`}
          />

          {/* Eyelid (animated downward sweep for blink/wink + sleeping cover) */}
          <motion.rect
            x={eyeX - 1}
            y={eyeY - 1}
            width={EYE_W + 2}
            height={lidHeight + 1}
            rx={EYE_RADIUS}
            ry={EYE_RADIUS}
            fill={isLight ? '#1a1208' : '#050507'}
            animate={{ height: lidHeight + 1 }}
            transition={{ type: 'spring', stiffness: 600, damping: 30 }}
            clipPath={`url(#bubble-clip-${eyeId}-${uid})`}
          />

          {/* Bottom-up "happy curve": a curved cover at the bottom that comes
              UP, making the eye look like a ^ shape when happy */}
          {mood === 'happy' && (
            <path
              d={`M ${eyeX} ${eyeY + EYE_H}
                  Q ${cx} ${eyeY + EYE_H - 14}
                    ${eyeX + EYE_W} ${eyeY + EYE_H}
                  L ${eyeX + EYE_W} ${eyeY + EYE_H + 1}
                  L ${eyeX} ${eyeY + EYE_H + 1} Z`}
              fill={isLight ? '#1a1208' : '#050507'}
              clipPath={`url(#bubble-clip-${eyeId}-${uid})`}
            />
          )}

          {/* Sad: top droops slightly */}
          {mood === 'sad' && (
            <path
              d={`M ${eyeX - 1} ${eyeY - 1}
                  L ${eyeX + EYE_W + 1} ${eyeY - 1}
                  L ${eyeX + EYE_W + 1} ${eyeY + 6}
                  Q ${cx} ${eyeY + 1}
                    ${eyeX - 1} ${eyeY + 4} Z`}
              fill={isLight ? '#1a1208' : '#050507'}
              clipPath={`url(#bubble-clip-${eyeId}-${uid})`}
            />
          )}
        </motion.g>

        {/* Raised eyebrow wedge (gotcha) — outside squint group, above eye */}
        {moodConfig.raisedBrow === eyeId && (
          <motion.path
            d={`M ${eyeX + 4} ${eyeY - 8}
                L ${eyeX + EYE_W - 4} ${eyeY - 12}
                L ${eyeX + EYE_W - 4} ${eyeY - 9}
                L ${eyeX + 4} ${eyeY - 5} Z`}
            fill={accentVar}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 0.85, y: 0 }}
            transition={{ type: 'spring', stiffness: 300, damping: 20 }}
          />
        )}

        {/* Blush (under eye) */}
        {moodConfig.blushAlpha > 0 && (
          <motion.ellipse
            cx={cx}
            cy={EYE_CY + EYE_H / 2 + 6}
            rx={EYE_W / 2 - 4}
            ry={3.5}
            fill={BLUSH_COLOR}
            filter={`url(#bubble-blur-${uid})`}
            initial={{ opacity: 0 }}
            animate={{ opacity: moodConfig.blushAlpha }}
            transition={{ duration: 0.6 }}
          />
        )}
      </motion.g>
    )
  }

  // ── SVG defs (gradients, filters, clips) ───────────────────────────────

  return (
    <div
      className="relative flex items-center justify-center"
      style={{ width: size, height: size }}
    >
      <motion.svg
        viewBox={`0 0 ${VB} ${VB}`}
        width={size}
        height={size}
        animate={{ scale: [1, 1 + stateConfig.breatheAmount, 1] }}
        transition={{
          duration: stateConfig.breatheDuration,
          repeat: Infinity,
          ease: 'easeInOut' as const,
        }}
      >
        <defs>
          {/* Filter: soft blur for halos and shadows */}
          <filter id={`bubble-blur-${uid}`} x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="3" />
          </filter>
          <filter id={`bubble-blur-tiny-${uid}`} x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="0.6" />
          </filter>

          {/* Clip paths — keep highlights inside the rounded eye shape */}
          <clipPath id={`bubble-clip-left-${uid}`}>
            <rect
              x={LEFT_EYE_CX - EYE_W / 2}
              y={EYE_CY - EYE_H / 2}
              width={EYE_W}
              height={EYE_H}
              rx={EYE_RADIUS}
              ry={EYE_RADIUS}
            />
          </clipPath>
          <clipPath id={`bubble-clip-right-${uid}`}>
            <rect
              x={RIGHT_EYE_CX - EYE_W / 2}
              y={EYE_CY - EYE_H / 2}
              width={EYE_W}
              height={EYE_H}
              rx={EYE_RADIUS}
              ry={EYE_RADIUS}
            />
          </clipPath>

          {/* Eye body: vertical linear gradient (bright top → darker bottom) */}
          <linearGradient
            id={`bubble-body-left-${uid}`}
            x1="0%" y1="0%" x2="0%" y2="100%"
          >
            <stop offset="0%" stopColor={eyeTopColor} stopOpacity={1} />
            <stop offset="60%" stopColor={eyeTopColor} stopOpacity={0.85} />
            <stop offset="100%" stopColor={eyeBottomFinal} stopOpacity={1} />
          </linearGradient>
          <linearGradient
            id={`bubble-body-right-${uid}`}
            x1="0%" y1="0%" x2="0%" y2="100%"
          >
            <stop offset="0%" stopColor={eyeTopColor} stopOpacity={1} />
            <stop offset="60%" stopColor={eyeTopColor} stopOpacity={0.85} />
            <stop offset="100%" stopColor={eyeBottomFinal} stopOpacity={1} />
          </linearGradient>

          {/* Ambient light overlay: radial from upper-left, fading out */}
          <radialGradient
            id={`bubble-ambient-left-${uid}`}
            cx="30%" cy="22%" r="70%"
          >
            <stop offset="0%" stopColor="rgba(255, 255, 255, 0.32)" />
            <stop offset="60%" stopColor="rgba(255, 255, 255, 0)" />
          </radialGradient>
          <radialGradient
            id={`bubble-ambient-right-${uid}`}
            cx="30%" cy="22%" r="70%"
          >
            <stop offset="0%" stopColor="rgba(255, 255, 255, 0.32)" />
            <stop offset="60%" stopColor="rgba(255, 255, 255, 0)" />
          </radialGradient>

          {/* Outer glow halo — radial gradient in accent color */}
          <radialGradient
            id={`bubble-glow-left-${uid}`}
            cx="50%" cy="50%" r="50%"
          >
            <stop offset="0%" stopColor={glowColor} stopOpacity={0.7} />
            <stop offset="100%" stopColor={glowColor} stopOpacity={0} />
          </radialGradient>
          <radialGradient
            id={`bubble-glow-right-${uid}`}
            cx="50%" cy="50%" r="50%"
          >
            <stop offset="0%" stopColor={glowColor} stopOpacity={0.7} />
            <stop offset="100%" stopColor={glowColor} stopOpacity={0} />
          </radialGradient>

          {/* Pupil: vertical gradient — near-black top, slightly lighter bottom */}
          <linearGradient
            id={`bubble-pupil-${uid}`}
            x1="0%" y1="0%" x2="0%" y2="100%"
          >
            <stop offset="0%" stopColor="rgba(20, 20, 30, 0.98)" />
            <stop offset="100%" stopColor="rgba(40, 40, 60, 0.95)" />
          </linearGradient>

          {/* Heart pupil gradient (romantic mood) */}
          <linearGradient
            id={`bubble-heart-${uid}`}
            x1="0%" y1="0%" x2="0%" y2="100%"
          >
            <stop offset="0%" stopColor="#ff5d8f" />
            <stop offset="100%" stopColor="#d63672" />
          </linearGradient>
        </defs>

        {/* Render both eyes */}
        {renderEye('left', LEFT_EYE_CX, leftPupilDx, leftAsymScale, leftSquintY, leftBlinkAmount)}
        {renderEye('right', RIGHT_EYE_CX, rightPupilDx, rightAsymScale, rightSquintY, rightBlinkAmount)}
      </motion.svg>
    </div>
  )
}
