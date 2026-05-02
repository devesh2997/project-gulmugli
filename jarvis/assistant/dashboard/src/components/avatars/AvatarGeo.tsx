/**
 * AvatarGeo — bold geometric mascot.
 *
 * Composed entirely of basic geometric primitives (circles, half-circles,
 * rounded rectangles, triangles, stars, plus signs). Personality reads
 * through SHAPE LANGUAGE rather than detail. Spotify-Wrapped + Duolingo +
 * Memoji-geometric vibe — flat solid colors, no gradients on the main face,
 * clean morphs between expressions.
 *
 * Design rules:
 *   - Face: large rounded square in solid `--personality-accent`
 *   - Eyes: 2 primitives that morph per mood (circles, arcs, rings, hearts...)
 *   - Mouth: a small geometric primitive (line, rect, arc, ring) per state/mood
 *   - Accents (sparkles, droplets, notes, "?", "Z") fly in/out per state/mood
 *   - One subtle drop shadow under the face, never gradients on the face itself
 *
 * Colors come from CSS custom properties set by TokenProvider:
 *   --personality-accent      main face fill + accent color
 *   --personality-glow_color  background radial glow
 */

import { useEffect, useMemo, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useLightMode } from '../../hooks/useLightMode'
import type { AssistantState, AssistantMood } from '../../types/assistant'

// ─── Constants ─────────────────────────────────────────────────────────────

/** SVG viewBox is 100x100. The face is centered at (50, 52) — slightly low
 *  so accents above the head have room without clipping. */
const VB = 100
const FACE_CX = 50
const FACE_CY = 52
const FACE_SIZE = 74          // rounded square width/height
const FACE_RADIUS = 22        // corner rounding — chunky, not too round

// Eye geometry
const EYE_Y = FACE_CY - 6     // eyes sit slightly above face center
const EYE_GAP = 18            // distance between eye centers
const EYE_LX = FACE_CX - EYE_GAP / 2
const EYE_RX = FACE_CX + EYE_GAP / 2
const EYE_R = 5               // base eye radius

// Mouth geometry
const MOUTH_Y = FACE_CY + 14

// Spring presets
const SPRING_FAST = { type: 'spring' as const, stiffness: 320, damping: 22, mass: 0.7 }
const SPRING_SOFT = { type: 'spring' as const, stiffness: 180, damping: 20, mass: 1 }

// ─── Eye renderers ─────────────────────────────────────────────────────────
//
// Each renderer takes a center (cx, cy), a side ('L' or 'R'), and an "inverted"
// fill color (the face color, used for cutouts that read as "the face shape"),
// returns an SVG fragment. All eyes are drawn in white-on-face for max contrast
// — actual color is the face background showing through.

interface EyeProps {
  cx: number
  cy: number
  side: 'L' | 'R'
  /** Stroke/fill color for the eye shape (dark on light bg, white-ish on dark) */
  color: string
  /** Wink: only one eye per "playful" mood. Caller passes which eye should arc. */
  winkArc?: boolean
}

/** Filled circle eye — neutral / idle / default. */
function EyeCircle({ cx, cy, color }: EyeProps) {
  return (
    <motion.circle
      cx={cx}
      cy={cy}
      r={EYE_R}
      fill={color}
      initial={{ scale: 0.4, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      exit={{ scale: 0.4, opacity: 0 }}
      transition={SPRING_FAST}
    />
  )
}

/** Upturned arc — happy/playful smiling eye. `^` shape. */
function EyeArcUp({ cx, cy, color }: EyeProps) {
  // Path: arc from left to right, curving up
  const half = EYE_R + 1
  const path = `M ${cx - half} ${cy + 1.5} Q ${cx} ${cy - half - 0.5} ${cx + half} ${cy + 1.5}`
  return (
    <motion.path
      d={path}
      fill="none"
      stroke={color}
      strokeWidth={2.6}
      strokeLinecap="round"
      initial={{ pathLength: 0, opacity: 0 }}
      animate={{ pathLength: 1, opacity: 1 }}
      exit={{ pathLength: 0, opacity: 0 }}
      transition={SPRING_FAST}
    />
  )
}

/** Downturned arc — sad. `v` shape. */
function EyeArcDown({ cx, cy, color }: EyeProps) {
  const half = EYE_R + 1
  const path = `M ${cx - half} ${cy - 1.5} Q ${cx} ${cy + half + 0.5} ${cx + half} ${cy - 1.5}`
  return (
    <motion.path
      d={path}
      fill="none"
      stroke={color}
      strokeWidth={2.6}
      strokeLinecap="round"
      initial={{ pathLength: 0, opacity: 0 }}
      animate={{ pathLength: 1, opacity: 1 }}
      exit={{ pathLength: 0, opacity: 0 }}
      transition={SPRING_FAST}
    />
  )
}

/** Half-circle looking down — shy. `u` shape (closed semicircle, flat side up). */
function EyeHalfDown({ cx, cy, color }: EyeProps) {
  const r = EYE_R - 0.5
  const path = `M ${cx - r} ${cy - 0.5} A ${r} ${r} 0 0 0 ${cx + r} ${cy - 0.5} Z`
  return (
    <motion.path
      d={path}
      fill={color}
      initial={{ scale: 0.4, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      exit={{ scale: 0.4, opacity: 0 }}
      transition={SPRING_FAST}
      style={{ transformOrigin: `${cx}px ${cy}px` }}
    />
  )
}

/** Hollow ring eye — surprised. `O` shape. */
function EyeRing({ cx, cy, color }: EyeProps) {
  return (
    <motion.circle
      cx={cx}
      cy={cy}
      r={EYE_R + 0.8}
      fill="none"
      stroke={color}
      strokeWidth={2.4}
      initial={{ scale: 0.3, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      exit={{ scale: 0.3, opacity: 0 }}
      transition={SPRING_FAST}
    />
  )
}

/** Heart eye — romantic. */
function EyeHeart({ cx, cy, color }: EyeProps) {
  // Compact heart path centered roughly at (cx, cy)
  const s = 1.0
  const path = [
    `M ${cx} ${cy + 3.2 * s}`,
    `C ${cx - 6 * s} ${cy - 1.5 * s}, ${cx - 6 * s} ${cy - 6 * s}, ${cx - 2.5 * s} ${cy - 4.5 * s}`,
    `C ${cx - 0.8 * s} ${cy - 3.2 * s}, ${cx} ${cy - 1.5 * s}, ${cx} ${cy - 1.0 * s}`,
    `C ${cx} ${cy - 1.5 * s}, ${cx + 0.8 * s} ${cy - 3.2 * s}, ${cx + 2.5 * s} ${cy - 4.5 * s}`,
    `C ${cx + 6 * s} ${cy - 6 * s}, ${cx + 6 * s} ${cy - 1.5 * s}, ${cx} ${cy + 3.2 * s}`,
    `Z`,
  ].join(' ')
  return (
    <motion.path
      d={path}
      fill={color}
      initial={{ scale: 0.2, opacity: 0 }}
      animate={{ scale: [0.2, 1.15, 1], opacity: 1 }}
      exit={{ scale: 0.2, opacity: 0 }}
      transition={{ ...SPRING_FAST, scale: { duration: 0.45, times: [0, 0.6, 1] } }}
    />
  )
}

/** Narrow horizontal pill — gotcha (smug squint). `—` shape. */
function EyePill({ cx, cy, color }: EyeProps) {
  const w = (EYE_R + 1.2) * 2
  return (
    <motion.rect
      x={cx - w / 2}
      y={cy - 1.4}
      width={w}
      height={2.8}
      rx={1.4}
      fill={color}
      initial={{ scaleX: 0.2, opacity: 0 }}
      animate={{ scaleX: 1, opacity: 1 }}
      exit={{ scaleX: 0.2, opacity: 0 }}
      transition={SPRING_FAST}
      style={{ transformOrigin: `${cx}px ${cy}px` }}
    />
  )
}

/** Sleeping eye — single thin horizontal line. */
function EyeLine({ cx, cy, color }: EyeProps) {
  return (
    <motion.rect
      x={cx - EYE_R - 0.5}
      y={cy - 1}
      width={(EYE_R + 0.5) * 2}
      height={2}
      rx={1}
      fill={color}
      initial={{ scaleX: 0.2, opacity: 0 }}
      animate={{ scaleX: 1, opacity: 1 }}
      exit={{ scaleX: 0.2, opacity: 0 }}
      transition={SPRING_FAST}
      style={{ transformOrigin: `${cx}px ${cy}px` }}
    />
  )
}

/** Blinking eye — momentary horizontal line during idle blink. */
function EyeBlink({ cx, cy, color }: EyeProps) {
  return (
    <rect
      x={cx - EYE_R}
      y={cy - 0.9}
      width={EYE_R * 2}
      height={1.8}
      rx={0.9}
      fill={color}
    />
  )
}

// ─── Mouth renderers ───────────────────────────────────────────────────────

interface MouthProps {
  color: string
  /** Drives the speaking shape cycle: 0..3 */
  speakFrame: number
  state: AssistantState
  mood: AssistantMood
}

function Mouth({ color, speakFrame, state, mood }: MouthProps) {
  // Speaking: cycle through 4 shapes
  if (state === 'speaking') {
    const frame = speakFrame % 4
    if (frame === 0) {
      // small horizontal line
      return (
        <motion.rect
          key="speak-line"
          x={FACE_CX - 5}
          y={MOUTH_Y - 0.8}
          width={10}
          height={1.8}
          rx={0.9}
          fill={color}
          initial={{ scaleY: 0.3 }}
          animate={{ scaleY: 1 }}
          transition={{ duration: 0.08 }}
        />
      )
    }
    if (frame === 1) {
      // small open rectangle
      return (
        <motion.rect
          key="speak-rect"
          x={FACE_CX - 4}
          y={MOUTH_Y - 1.5}
          width={8}
          height={5}
          rx={2}
          fill={color}
          initial={{ scaleY: 0.4 }}
          animate={{ scaleY: 1 }}
          transition={{ duration: 0.09 }}
        />
      )
    }
    if (frame === 2) {
      // wider line
      return (
        <motion.rect
          key="speak-line2"
          x={FACE_CX - 6}
          y={MOUTH_Y - 0.7}
          width={12}
          height={1.6}
          rx={0.8}
          fill={color}
          initial={{ scaleY: 0.3 }}
          animate={{ scaleY: 1 }}
          transition={{ duration: 0.08 }}
        />
      )
    }
    // round "o" mouth
    return (
      <motion.circle
        key="speak-o"
        cx={FACE_CX}
        cy={MOUTH_Y + 1.5}
        r={3}
        fill={color}
        initial={{ scale: 0.4 }}
        animate={{ scale: 1 }}
        transition={{ duration: 0.09 }}
      />
    )
  }

  // Sleeping: tiny flat line, slightly off-center
  if (state === 'sleeping') {
    return (
      <motion.rect
        key="sleep"
        x={FACE_CX - 3.5}
        y={MOUTH_Y + 1}
        width={7}
        height={1.4}
        rx={0.7}
        fill={color}
        initial={{ scaleX: 0.2, opacity: 0 }}
        animate={{ scaleX: 1, opacity: 1 }}
        exit={{ scaleX: 0.2, opacity: 0 }}
        transition={SPRING_SOFT}
      />
    )
  }

  // Mood-driven mouth shape (when not speaking/sleeping)
  if (mood === 'happy' || mood === 'playful') {
    // upward arc smile
    const path = `M ${FACE_CX - 7} ${MOUTH_Y} Q ${FACE_CX} ${MOUTH_Y + 6} ${FACE_CX + 7} ${MOUTH_Y}`
    return (
      <motion.path
        key="smile"
        d={path}
        fill="none"
        stroke={color}
        strokeWidth={2.4}
        strokeLinecap="round"
        initial={{ pathLength: 0, opacity: 0 }}
        animate={{ pathLength: 1, opacity: 1 }}
        exit={{ pathLength: 0, opacity: 0 }}
        transition={SPRING_FAST}
      />
    )
  }

  if (mood === 'sad') {
    const path = `M ${FACE_CX - 6} ${MOUTH_Y + 3} Q ${FACE_CX} ${MOUTH_Y - 2.5} ${FACE_CX + 6} ${MOUTH_Y + 3}`
    return (
      <motion.path
        key="frown"
        d={path}
        fill="none"
        stroke={color}
        strokeWidth={2.4}
        strokeLinecap="round"
        initial={{ pathLength: 0, opacity: 0 }}
        animate={{ pathLength: 1, opacity: 1 }}
        exit={{ pathLength: 0, opacity: 0 }}
        transition={SPRING_FAST}
      />
    )
  }

  if (mood === 'shy') {
    // tiny rounded rect, slightly off-center for awkwardness
    return (
      <motion.rect
        key="shy"
        x={FACE_CX - 2.5}
        y={MOUTH_Y - 0.5}
        width={5}
        height={2}
        rx={1}
        fill={color}
        initial={{ scale: 0.3, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.3, opacity: 0 }}
        transition={SPRING_FAST}
      />
    )
  }

  if (mood === 'sarcastic') {
    // flat line tilted slightly
    return (
      <motion.rect
        key="sarcastic"
        x={FACE_CX - 6}
        y={MOUTH_Y - 0.7}
        width={12}
        height={1.7}
        rx={0.85}
        fill={color}
        initial={{ scaleX: 0, opacity: 0, rotate: -6 }}
        animate={{ scaleX: 1, opacity: 1, rotate: -6 }}
        exit={{ scaleX: 0, opacity: 0 }}
        transition={SPRING_FAST}
        style={{ transformOrigin: `${FACE_CX}px ${MOUTH_Y}px` }}
      />
    )
  }

  if (mood === 'surprised') {
    // hollow circle "O"
    return (
      <motion.circle
        key="o"
        cx={FACE_CX}
        cy={MOUTH_Y + 1}
        r={3.2}
        fill="none"
        stroke={color}
        strokeWidth={2}
        initial={{ scale: 0.2, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.2, opacity: 0 }}
        transition={SPRING_FAST}
      />
    )
  }

  if (mood === 'romantic') {
    // small smile, but rounder/sweeter
    const path = `M ${FACE_CX - 5} ${MOUTH_Y} Q ${FACE_CX} ${MOUTH_Y + 4.5} ${FACE_CX + 5} ${MOUTH_Y}`
    return (
      <motion.path
        key="romantic"
        d={path}
        fill="none"
        stroke={color}
        strokeWidth={2.4}
        strokeLinecap="round"
        initial={{ pathLength: 0, opacity: 0 }}
        animate={{ pathLength: 1, opacity: 1 }}
        exit={{ pathLength: 0, opacity: 0 }}
        transition={SPRING_FAST}
      />
    )
  }

  if (mood === 'gotcha') {
    // smug asymmetric smirk
    const path = `M ${FACE_CX - 6} ${MOUTH_Y + 1.5} Q ${FACE_CX - 1} ${MOUTH_Y - 2.5} ${FACE_CX + 6} ${MOUTH_Y - 1}`
    return (
      <motion.path
        key="smirk"
        d={path}
        fill="none"
        stroke={color}
        strokeWidth={2.4}
        strokeLinecap="round"
        initial={{ pathLength: 0, opacity: 0 }}
        animate={{ pathLength: 1, opacity: 1 }}
        exit={{ pathLength: 0, opacity: 0 }}
        transition={SPRING_FAST}
      />
    )
  }

  // State-only (neutral mood)
  if (state === 'thinking') {
    // small slanted line — concentration
    return (
      <motion.rect
        key="think"
        x={FACE_CX - 4}
        y={MOUTH_Y - 0.7}
        width={8}
        height={1.6}
        rx={0.8}
        fill={color}
        initial={{ scaleX: 0, opacity: 0 }}
        animate={{ scaleX: 1, opacity: 1, rotate: -4 }}
        exit={{ scaleX: 0, opacity: 0 }}
        transition={SPRING_FAST}
        style={{ transformOrigin: `${FACE_CX}px ${MOUTH_Y}px` }}
      />
    )
  }

  if (state === 'listening') {
    // gentle slight smile
    const path = `M ${FACE_CX - 5.5} ${MOUTH_Y + 0.3} Q ${FACE_CX} ${MOUTH_Y + 3} ${FACE_CX + 5.5} ${MOUTH_Y + 0.3}`
    return (
      <motion.path
        key="listen"
        d={path}
        fill="none"
        stroke={color}
        strokeWidth={2.2}
        strokeLinecap="round"
        initial={{ pathLength: 0, opacity: 0 }}
        animate={{ pathLength: 1, opacity: 1 }}
        exit={{ pathLength: 0, opacity: 0 }}
        transition={SPRING_FAST}
      />
    )
  }

  // Default neutral — short horizontal line
  return (
    <motion.rect
      key="neutral"
      x={FACE_CX - 4}
      y={MOUTH_Y - 0.7}
      width={8}
      height={1.6}
      rx={0.8}
      fill={color}
      initial={{ scaleX: 0, opacity: 0 }}
      animate={{ scaleX: 1, opacity: 1 }}
      exit={{ scaleX: 0, opacity: 0 }}
      transition={SPRING_FAST}
    />
  )
}

// ─── Eye dispatcher ────────────────────────────────────────────────────────
//
// Returns the right eye component for a given (state, mood, side).
// Special case: 'playful' mood = wink (one circle + one upward arc).

type EyeKind =
  | 'circle'
  | 'arcUp'
  | 'arcDown'
  | 'halfDown'
  | 'ring'
  | 'heart'
  | 'pill'
  | 'line'
  | 'blink'

function chooseEyeKind(
  state: AssistantState,
  mood: AssistantMood,
  side: 'L' | 'R',
): EyeKind {
  if (state === 'sleeping') return 'line'

  // Mood overrides for non-sleeping states
  switch (mood) {
    case 'happy':
      return 'arcUp'
    case 'sad':
      return 'arcDown'
    case 'shy':
      return 'halfDown'
    case 'playful':
      // wink: left eye = circle, right eye = arc up
      return side === 'L' ? 'circle' : 'arcUp'
    case 'sarcastic':
      // both circles — the brow line on one eye does the work
      return 'circle'
    case 'surprised':
      return 'ring'
    case 'romantic':
      return 'heart'
    case 'gotcha':
      return 'pill'
    case 'neutral':
    default:
      // State-only fallbacks
      if (state === 'listening') return 'circle'
      if (state === 'thinking') return 'circle'
      return 'circle'
  }
}

function renderEye(kind: EyeKind, props: EyeProps) {
  switch (kind) {
    case 'circle':
      return <EyeCircle {...props} />
    case 'arcUp':
      return <EyeArcUp {...props} />
    case 'arcDown':
      return <EyeArcDown {...props} />
    case 'halfDown':
      return <EyeHalfDown {...props} />
    case 'ring':
      return <EyeRing {...props} />
    case 'heart':
      return <EyeHeart {...props} />
    case 'pill':
      return <EyePill {...props} />
    case 'line':
      return <EyeLine {...props} />
    case 'blink':
      return <EyeBlink {...props} />
  }
}

// ─── Accent decorations ────────────────────────────────────────────────────
//
// Small geometric accents that fly in/out of the face periphery for moods
// and states. Wrapped in AnimatePresence so they animate cleanly.

interface AccentProps {
  color: string
  state: AssistantState
  mood: AssistantMood
}

/** A tiny 4-pointed sparkle. */
function Sparkle({
  cx, cy, size = 3, color, delay = 0,
}: { cx: number; cy: number; size?: number; color: string; delay?: number }) {
  const path = [
    `M ${cx} ${cy - size}`,
    `L ${cx + size * 0.4} ${cy - size * 0.4}`,
    `L ${cx + size} ${cy}`,
    `L ${cx + size * 0.4} ${cy + size * 0.4}`,
    `L ${cx} ${cy + size}`,
    `L ${cx - size * 0.4} ${cy + size * 0.4}`,
    `L ${cx - size} ${cy}`,
    `L ${cx - size * 0.4} ${cy - size * 0.4}`,
    `Z`,
  ].join(' ')
  return (
    <motion.path
      d={path}
      fill={color}
      initial={{ scale: 0, opacity: 0 }}
      animate={{
        scale: [0, 1.1, 0.9, 1],
        opacity: [0, 1, 1, 0.85],
        rotate: [0, 25, 0],
      }}
      exit={{ scale: 0, opacity: 0 }}
      transition={{
        duration: 1.6,
        delay,
        repeat: Infinity,
        repeatDelay: 0.4,
        ease: 'easeInOut',
      }}
      style={{ transformOrigin: `${cx}px ${cy}px` }}
    />
  )
}

/** A tiny teardrop shape pointing down. */
function Droplet({
  cx, cy, color, delay = 0,
}: { cx: number; cy: number; color: string; delay?: number }) {
  const path = `M ${cx} ${cy - 3.5} Q ${cx + 2.5} ${cy} ${cx} ${cy + 2.5} Q ${cx - 2.5} ${cy} ${cx} ${cy - 3.5} Z`
  return (
    <motion.path
      d={path}
      fill={color}
      initial={{ y: -2, opacity: 0 }}
      animate={{ y: [0, 6, 6], opacity: [0, 1, 0] }}
      transition={{
        duration: 2.2,
        delay,
        repeat: Infinity,
        repeatDelay: 0.3,
        ease: 'easeIn',
        times: [0, 0.6, 1],
      }}
    />
  )
}

/** A small musical note (head + flag). */
function Note({
  cx, cy, color, delay = 0, drift = 6,
}: { cx: number; cy: number; color: string; delay?: number; drift?: number }) {
  return (
    <motion.g
      initial={{ y: 4, opacity: 0 }}
      animate={{ y: -drift, opacity: [0, 1, 1, 0] }}
      transition={{
        duration: 2.4,
        delay,
        repeat: Infinity,
        repeatDelay: 0.2,
        ease: 'easeOut',
        times: [0, 0.15, 0.7, 1],
      }}
    >
      <ellipse cx={cx} cy={cy} rx={2} ry={1.6} fill={color} transform={`rotate(-18 ${cx} ${cy})`} />
      <rect x={cx + 1.4} y={cy - 6.5} width={1.1} height={6} fill={color} />
    </motion.g>
  )
}

/** A small heart shape. */
function MiniHeart({
  cx, cy, color, delay = 0,
}: { cx: number; cy: number; color: string; delay?: number }) {
  const s = 0.65
  const path = [
    `M ${cx} ${cy + 4 * s}`,
    `C ${cx - 6 * s} ${cy - 1.5 * s}, ${cx - 6 * s} ${cy - 6 * s}, ${cx - 2.5 * s} ${cy - 4.5 * s}`,
    `C ${cx - 0.8 * s} ${cy - 3.2 * s}, ${cx} ${cy - 1.5 * s}, ${cx} ${cy - 1.0 * s}`,
    `C ${cx} ${cy - 1.5 * s}, ${cx + 0.8 * s} ${cy - 3.2 * s}, ${cx + 2.5 * s} ${cy - 4.5 * s}`,
    `C ${cx + 6 * s} ${cy - 6 * s}, ${cx + 6 * s} ${cy - 1.5 * s}, ${cx} ${cy + 4 * s}`,
    `Z`,
  ].join(' ')
  return (
    <motion.path
      d={path}
      fill={color}
      initial={{ scale: 0.2, y: 3, opacity: 0 }}
      animate={{ scale: [0.2, 1.1, 1], y: [-2, -8, -12], opacity: [0, 1, 0] }}
      transition={{
        duration: 2.4,
        delay,
        repeat: Infinity,
        repeatDelay: 0.3,
        ease: 'easeOut',
        times: [0, 0.4, 1],
      }}
      style={{ transformOrigin: `${cx}px ${cy}px` }}
    />
  )
}

/** A "Z" letter for sleeping. */
function ZLetter({
  cx, cy, color, delay = 0, scale = 1,
}: { cx: number; cy: number; color: string; delay?: number; scale?: number }) {
  const s = 3 * scale
  const path = `M ${cx - s} ${cy - s} L ${cx + s} ${cy - s} L ${cx - s} ${cy + s} L ${cx + s} ${cy + s}`
  return (
    <motion.path
      d={path}
      fill="none"
      stroke={color}
      strokeWidth={1.4}
      strokeLinecap="round"
      strokeLinejoin="round"
      initial={{ y: 4, opacity: 0, scale: 0.5 }}
      animate={{ y: -10, opacity: [0, 1, 0], scale: [0.5, 1, 1.1] }}
      transition={{
        duration: 3,
        delay,
        repeat: Infinity,
        repeatDelay: 0.5,
        ease: 'easeOut',
        times: [0, 0.4, 1],
      }}
      style={{ transformOrigin: `${cx}px ${cy}px` }}
    />
  )
}

/** Listening soundwave dots above the head. */
function SoundwaveDots({ color }: { color: string }) {
  const baseY = FACE_CY - FACE_SIZE / 2 - 6
  const positions = [-12, -4, 4, 12]
  return (
    <>
      {positions.map((dx, i) => (
        <motion.circle
          key={`sw-${i}`}
          cx={FACE_CX + dx}
          cy={baseY}
          r={1.6}
          fill={color}
          initial={{ scale: 0, opacity: 0 }}
          animate={{ scale: [0.4, 1.3, 0.6, 1.3, 0.4], opacity: [0.4, 1, 0.7, 1, 0.4] }}
          transition={{
            duration: 1.2,
            repeat: Infinity,
            ease: 'easeInOut',
            delay: i * 0.12,
          }}
        />
      ))}
    </>
  )
}

/** Thinking question mark + dots above head. */
function ThinkingMark({ color }: { color: string }) {
  const cx = FACE_CX + FACE_SIZE / 2 - 6
  const cy = FACE_CY - FACE_SIZE / 2 - 4
  // Question mark: arc on top + dot
  const arc = `M ${cx - 2.4} ${cy - 2.6} Q ${cx} ${cy - 5.2} ${cx + 2.4} ${cy - 2.6} Q ${cx + 2.4} ${cy - 0.8} ${cx} ${cy + 0.8}`
  return (
    <motion.g
      initial={{ opacity: 0, scale: 0.5, y: 2 }}
      animate={{
        opacity: [0, 1, 1, 0],
        scale: [0.5, 1, 1.05, 0.9],
        y: [2, -2, -2, -4],
      }}
      transition={{
        duration: 2,
        repeat: Infinity,
        repeatDelay: 0.4,
        ease: 'easeInOut',
        times: [0, 0.25, 0.75, 1],
      }}
    >
      <path
        d={arc}
        fill="none"
        stroke={color}
        strokeWidth={1.6}
        strokeLinecap="round"
      />
      <circle cx={cx} cy={cy + 3} r={0.9} fill={color} />
    </motion.g>
  )
}

function Accents({ color, state, mood }: AccentProps) {
  const items: { id: string; node: React.ReactNode }[] = []

  // State-driven accents
  if (state === 'listening') {
    items.push({ id: 'soundwave', node: <SoundwaveDots color={color} /> })
  } else if (state === 'thinking') {
    items.push({ id: 'thinking-mark', node: <ThinkingMark color={color} /> })
  } else if (state === 'sleeping') {
    items.push({
      id: 'zzz',
      node: (
        <>
          <ZLetter cx={FACE_CX + FACE_SIZE / 2 - 8} cy={FACE_CY - FACE_SIZE / 2 - 2} color={color} delay={0} scale={0.8} />
          <ZLetter cx={FACE_CX + FACE_SIZE / 2 - 2} cy={FACE_CY - FACE_SIZE / 2 - 8} color={color} delay={1} scale={1} />
          <ZLetter cx={FACE_CX + FACE_SIZE / 2 + 4} cy={FACE_CY - FACE_SIZE / 2 - 14} color={color} delay={2} scale={1.2} />
        </>
      ),
    })
  }

  // Mood-driven accents (only when not sleeping)
  if (state !== 'sleeping') {
    if (mood === 'happy') {
      items.push({
        id: 'sparkles-happy',
        node: (
          <>
            <Sparkle cx={FACE_CX - FACE_SIZE / 2 - 2} cy={FACE_CY - 12} size={2.5} color={color} delay={0} />
            <Sparkle cx={FACE_CX + FACE_SIZE / 2 + 2} cy={FACE_CY - 4} size={3} color={color} delay={0.4} />
            <Sparkle cx={FACE_CX + FACE_SIZE / 2 - 4} cy={FACE_CY - FACE_SIZE / 2 - 4} size={2} color={color} delay={0.8} />
          </>
        ),
      })
    }
    if (mood === 'sad') {
      items.push({
        id: 'droplets-sad',
        node: (
          <>
            <Droplet cx={EYE_LX - 3} cy={EYE_Y + 8} color={color} delay={0} />
            <Droplet cx={EYE_RX + 3} cy={EYE_Y + 9} color={color} delay={0.6} />
          </>
        ),
      })
    }
    if (mood === 'playful') {
      items.push({
        id: 'notes-playful',
        node: (
          <>
            <Note cx={FACE_CX - FACE_SIZE / 2} cy={FACE_CY - 8} color={color} delay={0} drift={6} />
            <Note cx={FACE_CX + FACE_SIZE / 2} cy={FACE_CY - 12} color={color} delay={0.7} drift={8} />
          </>
        ),
      })
    }
    if (mood === 'romantic') {
      items.push({
        id: 'hearts-romantic',
        node: (
          <>
            <MiniHeart cx={FACE_CX - FACE_SIZE / 2 + 2} cy={FACE_CY - 14} color={color} delay={0} />
            <MiniHeart cx={FACE_CX + FACE_SIZE / 2 - 2} cy={FACE_CY - 18} color={color} delay={0.6} />
            <MiniHeart cx={FACE_CX + 4} cy={FACE_CY - FACE_SIZE / 2 - 4} color={color} delay={1.2} />
          </>
        ),
      })
    }
    if (mood === 'surprised') {
      items.push({
        id: 'lines-surprised',
        node: (
          <>
            {[-1, -0.5, 0, 0.5, 1].map((t, i) => {
              const angle = -Math.PI / 2 + t * 0.55
              const r1 = FACE_SIZE / 2 + 4
              const r2 = r1 + 5
              const x1 = FACE_CX + Math.cos(angle) * r1
              const y1 = FACE_CY + Math.sin(angle) * r1
              const x2 = FACE_CX + Math.cos(angle) * r2
              const y2 = FACE_CY + Math.sin(angle) * r2
              return (
                <motion.line
                  key={`burst-${i}`}
                  x1={x1}
                  y1={y1}
                  x2={x2}
                  y2={y2}
                  stroke={color}
                  strokeWidth={1.6}
                  strokeLinecap="round"
                  initial={{ pathLength: 0, opacity: 0 }}
                  animate={{ pathLength: [0, 1, 1], opacity: [0, 1, 0] }}
                  transition={{
                    duration: 0.9,
                    repeat: Infinity,
                    repeatDelay: 0.6,
                    delay: i * 0.05,
                    ease: 'easeOut',
                  }}
                />
              )
            })}
          </>
        ),
      })
    }
    if (mood === 'gotcha') {
      // smug brow above one eye — small line
      items.push({
        id: 'brow-gotcha',
        node: (
          <motion.rect
            x={EYE_LX - 4}
            y={EYE_Y - 8}
            width={6}
            height={1.5}
            rx={0.7}
            fill={color}
            initial={{ scaleX: 0, opacity: 0 }}
            animate={{ scaleX: 1, opacity: 1, rotate: -12 }}
            transition={SPRING_FAST}
            style={{ transformOrigin: `${EYE_LX - 1}px ${EYE_Y - 7}px` }}
          />
        ),
      })
    }
    if (mood === 'sarcastic') {
      // arched brow over right eye
      items.push({
        id: 'brow-sarcastic',
        node: (
          <motion.path
            d={`M ${EYE_RX - 4} ${EYE_Y - 7} Q ${EYE_RX} ${EYE_Y - 11} ${EYE_RX + 4} ${EYE_Y - 7}`}
            fill="none"
            stroke={color}
            strokeWidth={1.6}
            strokeLinecap="round"
            initial={{ pathLength: 0, opacity: 0 }}
            animate={{ pathLength: 1, opacity: 1 }}
            transition={SPRING_FAST}
          />
        ),
      })
    }
    if (mood === 'shy') {
      // small blush dots on cheeks
      items.push({
        id: 'blush-shy',
        node: (
          <>
            <motion.circle
              cx={EYE_LX - 4}
              cy={MOUTH_Y - 2}
              r={2.2}
              fill="#ff8aa6"
              initial={{ scale: 0, opacity: 0 }}
              animate={{ scale: 1, opacity: 0.7 }}
              transition={SPRING_FAST}
            />
            <motion.circle
              cx={EYE_RX + 4}
              cy={MOUTH_Y - 2}
              r={2.2}
              fill="#ff8aa6"
              initial={{ scale: 0, opacity: 0 }}
              animate={{ scale: 1, opacity: 0.7 }}
              transition={SPRING_FAST}
            />
          </>
        ),
      })
    }
  }

  return (
    <AnimatePresence mode="sync">
      {items.map(it => (
        <motion.g
          key={it.id}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          {it.node}
        </motion.g>
      ))}
    </AnimatePresence>
  )
}

// ─── Main component ────────────────────────────────────────────────────────

export interface AvatarGeoProps {
  size: number
  state: AssistantState
  mood: AssistantMood
}

export function AvatarGeo({ size, state, mood }: AvatarGeoProps) {
  const isLight = useLightMode()

  // Eye color: a clean color that contrasts with the face fill.
  // On dark UI: use cream/white eyes on accent face. On light UI: keep eyes
  // dark for readability (the face stays accent, which is usually saturated).
  const eyeColor = isLight ? '#1a120a' : '#fff8ee'
  const accentColor = 'var(--personality-accent)'
  const glow = 'var(--personality-glow_color)'

  // ── Speaking mouth cycle ─────────────────────────────────────────────
  const [speakFrame, setSpeakFrame] = useState(0)
  useEffect(() => {
    if (state !== 'speaking') {
      setSpeakFrame(0)
      return
    }
    let timerId: ReturnType<typeof setTimeout>
    const cycle = () => {
      setSpeakFrame(prev => (prev + 1) % 4)
      timerId = setTimeout(cycle, 130 + Math.random() * 110)
    }
    timerId = setTimeout(cycle, 100)
    return () => clearTimeout(timerId)
  }, [state])

  // ── Idle blink ───────────────────────────────────────────────────────
  const [isBlinking, setIsBlinking] = useState(false)
  useEffect(() => {
    // Blink for idle and listening (most "alive" states)
    if (state !== 'idle' && state !== 'listening') {
      setIsBlinking(false)
      return
    }
    let timerId: ReturnType<typeof setTimeout>
    const scheduleBlink = () => {
      const delay = 2800 + Math.random() * 3500
      timerId = setTimeout(() => {
        setIsBlinking(true)
        setTimeout(() => setIsBlinking(false), 110)
        scheduleBlink()
      }, delay)
    }
    scheduleBlink()
    return () => clearTimeout(timerId)
  }, [state])

  // ── Thinking eye dart ────────────────────────────────────────────────
  const [eyeDart, setEyeDart] = useState(0) // -1..1, x offset multiplier
  useEffect(() => {
    if (state !== 'thinking') {
      setEyeDart(0)
      return
    }
    let timerId: ReturnType<typeof setTimeout>
    const dart = () => {
      setEyeDart((Math.random() - 0.5) * 2)
      timerId = setTimeout(dart, 600 + Math.random() * 600)
    }
    dart()
    return () => clearTimeout(timerId)
  }, [state])

  // ── Eye kinds (per side) ─────────────────────────────────────────────
  const eyeLeftKind = useMemo(
    () => (isBlinking ? 'blink' as EyeKind : chooseEyeKind(state, mood, 'L')),
    [state, mood, isBlinking],
  )
  const eyeRightKind = useMemo(
    () => (isBlinking ? 'blink' as EyeKind : chooseEyeKind(state, mood, 'R')),
    [state, mood, isBlinking],
  )

  // ── Eye position offset (gaze + dart + listening scale) ──────────────
  const eyeOffsetX = state === 'thinking' ? eyeDart * 1.6 : 0
  const eyeScale = state === 'listening' ? 1.12 : 1

  // ── Body wrapper animations (float / tilt / wobble / bounce / droop) ─
  const bodyAnimate = useMemo(() => {
    switch (state) {
      case 'idle':
        return { y: [0, -1.5, 0, 1, 0], rotate: 0 }
      case 'listening':
        return { y: -2, rotate: -3 }
      case 'thinking':
        return { y: [0, 0.8, 0], rotate: [0, -1.5, 1.2, 0] }
      case 'speaking':
        return { y: [0, -1.5, 0.5, -0.8, 0], rotate: [0, 0.8, -0.6, 0] }
      case 'sleeping':
        return { y: 3, rotate: -2 }
      default:
        return { y: 0, rotate: 0 }
    }
  }, [state])

  const bodyTransition = useMemo(() => {
    switch (state) {
      case 'idle':
        return { duration: 4, repeat: Infinity, ease: 'easeInOut' as const }
      case 'speaking':
        return { duration: 0.85, repeat: Infinity, ease: 'easeInOut' as const }
      case 'thinking':
        return { duration: 2.2, repeat: Infinity, ease: 'easeInOut' as const }
      case 'listening':
        return { type: 'spring' as const, stiffness: 380, damping: 18 }
      case 'sleeping':
        return { type: 'spring' as const, stiffness: 80, damping: 20 }
      default:
        return { duration: 0.4 }
    }
  }, [state])

  // ── Glow intensity per state ─────────────────────────────────────────
  const glowOpacity =
    state === 'sleeping' ? 0.04
    : state === 'idle' ? 0.18
    : state === 'listening' ? 0.42
    : state === 'speaking' ? 0.42
    : state === 'thinking' ? 0.28
    : 0.18
  const glowScale =
    state === 'listening' ? 1.18
    : state === 'speaking' ? 1.22
    : state === 'sleeping' ? 0.85
    : 1
  const glowDuration = state === 'sleeping' ? 5 : state === 'speaking' ? 1.2 : 4

  // ── Face shape props ─────────────────────────────────────────────────
  const faceX = FACE_CX - FACE_SIZE / 2
  const faceY = FACE_CY - FACE_SIZE / 2

  // Subtle drop shadow under face (no gradient on face itself)
  const faceShadow = isLight
    ? 'drop-shadow(0 3px 0 rgba(0,0,0,0.10)) drop-shadow(0 8px 14px rgba(0,0,0,0.08))'
    : 'drop-shadow(0 4px 0 rgba(0,0,0,0.18)) drop-shadow(0 10px 18px rgba(0,0,0,0.25))'

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
          opacity: [glowOpacity, glowOpacity * 0.55, glowOpacity],
          scale: [glowScale, glowScale * 1.08, glowScale],
        }}
        transition={{
          duration: glowDuration,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
      />

      {/* Body wrapper — handles per-state float / tilt / bounce */}
      <motion.svg
        viewBox={`0 0 ${VB} ${VB}`}
        width={size}
        height={size}
        style={{
          filter: faceShadow,
          overflow: 'visible',
        }}
        animate={bodyAnimate}
        transition={bodyTransition}
      >
        {/* ── Main face shape ─────────────────────────────────────── */}
        <motion.rect
          x={faceX}
          y={faceY}
          width={FACE_SIZE}
          height={FACE_SIZE}
          rx={FACE_RADIUS}
          ry={FACE_RADIUS}
          fill={accentColor}
          initial={{ scale: 0.85, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ ...SPRING_SOFT, delay: 0.05 }}
          style={{ transformOrigin: `${FACE_CX}px ${FACE_CY}px` }}
        />

        {/* Tiny corner accent (top-right plus sign) — subtle brand mark */}
        <motion.g
          initial={{ scale: 0, opacity: 0 }}
          animate={{ scale: 1, opacity: 0.55 }}
          transition={{ ...SPRING_FAST, delay: 0.25 }}
          style={{ transformOrigin: `${FACE_CX + FACE_SIZE / 2 - 9}px ${FACE_CY - FACE_SIZE / 2 + 9}px` }}
        >
          <rect
            x={FACE_CX + FACE_SIZE / 2 - 11}
            y={FACE_CY - FACE_SIZE / 2 + 8.5}
            width={4}
            height={1.2}
            rx={0.6}
            fill={eyeColor}
            opacity={0.45}
          />
          <rect
            x={FACE_CX + FACE_SIZE / 2 - 9.6}
            y={FACE_CY - FACE_SIZE / 2 + 7.1}
            width={1.2}
            height={4}
            rx={0.6}
            fill={eyeColor}
            opacity={0.45}
          />
        </motion.g>

        {/* ── Eyes group (with listening scale + thinking dart) ───── */}
        <motion.g
          animate={{
            x: eyeOffsetX,
            scale: eyeScale,
          }}
          transition={SPRING_FAST}
          style={{ transformOrigin: `${FACE_CX}px ${EYE_Y}px` }}
        >
          {/* Left eye */}
          <AnimatePresence mode="wait">
            <motion.g key={`L-${eyeLeftKind}`}>
              {renderEye(eyeLeftKind, { cx: EYE_LX, cy: EYE_Y, side: 'L', color: eyeColor })}
            </motion.g>
          </AnimatePresence>

          {/* Right eye */}
          <AnimatePresence mode="wait">
            <motion.g key={`R-${eyeRightKind}`}>
              {renderEye(eyeRightKind, { cx: EYE_RX, cy: EYE_Y, side: 'R', color: eyeColor })}
            </motion.g>
          </AnimatePresence>
        </motion.g>

        {/* ── Mouth ───────────────────────────────────────────────── */}
        <AnimatePresence mode="wait">
          <Mouth
            key={state === 'speaking' ? `speak-${speakFrame}` : `${state}-${mood}`}
            color={eyeColor}
            speakFrame={speakFrame}
            state={state}
            mood={mood}
          />
        </AnimatePresence>

        {/* ── Mood/state accents (sparkles, droplets, notes, Z, ?) ─ */}
        <Accents color={accentColor} state={state} mood={mood} />
      </motion.svg>
    </div>
  )
}
