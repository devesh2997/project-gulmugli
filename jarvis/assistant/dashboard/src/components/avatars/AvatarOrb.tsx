/**
 * AvatarOrb — Jarvis personality avatar.
 *
 * A pure energy sphere with no facial features. State is expressed entirely
 * through scale, opacity, glow intensity, and breathing rhythm — the orb's
 * animation IS the state indicator.
 *
 * Colors and timing come from CSS custom properties set by TokenProvider:
 *   --personality-accent      primary orb color
 *   --personality-glow_color  outer glow color
 *   --animation-orb-breathe-duration  base breathe cycle in seconds (e.g. "4s")
 *
 * Mood is accepted but intentionally ignored — the orb has no face to
 * express emotion. Mood-driven visuals belong to other avatar types.
 */

import { useMemo } from 'react'
import { motion } from 'framer-motion'
import { useLightMode } from '../../hooks/useLightMode'
import type { AssistantState, AssistantMood } from '../../types/assistant'

export interface AvatarOrbProps {
  size: number
  state: AssistantState
  mood: AssistantMood  // accepted, unused — orb has no face
}

interface StateConfig {
  scale: number
  opacity: number
  glowOpacity: number
  glowScale: number
  /** Multiplier applied to the CSS var base breathe duration */
  breatheMultiplier: number
  /** Border glow intensity (box-shadow spread) — multiplied by size */
  borderGlow: number
  /** Optional warm color shift (0 = accent color, 1 = full warm/orange) */
  warmShift: number
}

const STATE_CONFIGS: Record<AssistantState, StateConfig> = {
  idle: {
    scale: 1,
    opacity: 0.6,
    glowOpacity: 0.2,
    glowScale: 1,
    breatheMultiplier: 1,
    borderGlow: 0.12,
    warmShift: 0,
  },
  listening: {
    scale: 1.15,
    opacity: 0.95,
    glowOpacity: 0.65,
    glowScale: 1.5,
    breatheMultiplier: 0.35,
    borderGlow: 0.35,
    warmShift: 0,
  },
  thinking: {
    scale: 0.92,
    opacity: 0.8,
    glowOpacity: 0.45,
    glowScale: 1.3,
    breatheMultiplier: 0.25,
    borderGlow: 0.2,
    warmShift: 0.6,
  },
  speaking: {
    scale: 1.12,
    opacity: 1,
    glowOpacity: 0.7,
    glowScale: 1.6,
    breatheMultiplier: 0.12,
    borderGlow: 0.4,
    warmShift: 0,
  },
  sleeping: {
    scale: 0.85,
    opacity: 0.15,
    glowOpacity: 0.03,
    glowScale: 0.8,
    breatheMultiplier: 2.5,
    borderGlow: 0.02,
    warmShift: 0,
  },
}

/**
 * Resolve the base breathe duration from the CSS custom property.
 * The token is a string like "4s" — strip the "s" and parse as float.
 * Falls back to 4s if the property is missing or unparseable.
 */
function getBaseDuration(): number {
  if (typeof window === 'undefined') return 4
  const raw = getComputedStyle(document.documentElement)
    .getPropertyValue('--animation-orb-breathe-duration')
    .trim()
  const parsed = parseFloat(raw)
  return isNaN(parsed) ? 4 : parsed
}

/**
 * Resolve the current time-of-day brightness multiplier from the CSS custom
 * property written by useTimeOfDay. Ranges from 0.35 (deep night) to 1.0
 * (full brightness, afternoon). Falls back to 1.0 if missing.
 */
function getTimeBrightness(): number {
  if (typeof window === 'undefined') return 1
  const raw = getComputedStyle(document.documentElement)
    .getPropertyValue('--time-current-brightness')
    .trim()
  const parsed = parseFloat(raw)
  return isNaN(parsed) ? 1 : parsed
}

export function AvatarOrb({ size, state }: AvatarOrbProps) {
  const isLight = useLightMode()
  const config = STATE_CONFIGS[state] ?? STATE_CONFIGS.idle

  // Read base duration once per render. TokenProvider updates the CSS var
  // reactively, so the next re-render picks up the new personality's timing.
  const baseDuration = getBaseDuration()
  const breatheDuration = baseDuration * config.breatheMultiplier

  // Time-of-day brightness: dims the orb at night (0.35) vs afternoon (1.0).
  const brightness = getTimeBrightness()
  const opacity = config.opacity * brightness
  const glowOpacity = config.glowOpacity * brightness

  // Use rgb variant for rgba() — CSS vars can't have hex alpha appended
  const accentRgb = 'var(--personality-accent-rgb)'
  const a = (op: number) => `rgba(${accentRgb}, ${op})`

  // On light backgrounds, use dark brown tones instead of accent for the orb
  const darkRgb = '42, 26, 10'
  const d = (op: number) => `rgba(${darkRgb}, ${op})`

  // Warm color for thinking state (orange-shifted)
  const warmRgb = '255, 160, 60'
  const w = (op: number) => `rgba(${warmRgb}, ${op})`

  // Blend between accent and warm based on warmShift
  const shift = config.warmShift
  const c = (op: number) =>
    shift > 0
      ? `color-mix(in srgb, ${a(op)} ${Math.round((1 - shift) * 100)}%, ${w(op)})`
      : a(op)

  // Light-mode colour helper: more solid, darker tones
  const lc = (op: number) =>
    shift > 0
      ? `color-mix(in srgb, ${d(op)} ${Math.round((1 - shift) * 100)}%, ${w(op)})`
      : d(op)

  const orbVariants = useMemo(() => ({
    animate: {
      scale: [config.scale, config.scale * 1.06, config.scale],
      opacity: [opacity, opacity * 0.85, opacity],
      transition: {
        duration: breatheDuration,
        repeat: Infinity,
        ease: 'easeInOut' as const,
      },
    },
  }), [config.scale, breatheDuration, opacity])

  // Speaking: sharp rhythmic pulse (speech cadence) instead of smooth breathing
  const speakingVariants = useMemo(() => ({
    animate: {
      scale: [config.scale, config.scale * 1.1, config.scale * 0.97, config.scale],
      opacity: [opacity, opacity * 1.05, opacity * 0.8, opacity],
      transition: {
        duration: 0.6,
        repeat: Infinity,
        ease: 'easeInOut' as const,
        times: [0, 0.2, 0.5, 1],
      },
    },
  }), [config.scale, opacity])

  const glowVariants = useMemo(() => ({
    animate: {
      scale: [config.glowScale, config.glowScale * 1.25, config.glowScale],
      opacity: [glowOpacity, glowOpacity * 0.5, glowOpacity],
      transition: {
        duration: breatheDuration * 1.2,
        repeat: Infinity,
        ease: 'easeInOut' as const,
      },
    },
  }), [config.glowScale, breatheDuration, glowOpacity])

  // Thinking state: visible rotation to convey processing
  const thinkingRotation = state === 'thinking'
    ? {
        rotate: [0, 360],
        transition: {
          duration: 2,
          repeat: Infinity,
          ease: 'linear' as const,
        },
      }
    : {}

  // Thinking: pulsing glow that expands and contracts faster
  const thinkingGlowVariants = useMemo(() => ({
    animate: {
      scale: [config.glowScale, config.glowScale * 1.5, config.glowScale],
      opacity: [glowOpacity, glowOpacity * 0.3, glowOpacity],
      transition: {
        duration: 1.2,
        repeat: Infinity,
        ease: 'easeInOut' as const,
      },
    },
  }), [config.glowScale, glowOpacity])

  // Pick orb animation based on state
  const activeOrbVariants = state === 'speaking' ? speakingVariants : orbVariants
  const activeGlowVariants = state === 'thinking' ? thinkingGlowVariants : glowVariants

  // For thinking state, use warm-shifted gradient.
  // On light backgrounds, make the orb much more solid with darker fills.
  const orbBg = isLight
    ? (shift > 0
        ? `radial-gradient(circle at 35% 35%, ${w(0.5)} 0%, ${d(0.3)} 40%, ${d(0.15)} 70%, transparent 100%)`
        : `radial-gradient(circle at 35% 35%, ${d(0.5)} 0%, ${d(0.3)} 40%, ${d(0.12)} 70%, transparent 100%)`)
    : (shift > 0
        ? `radial-gradient(circle at 35% 35%, ${w(0.3)} 0%, ${a(0.12)} 40%, ${a(0.04)} 70%, transparent 100%)`
        : `radial-gradient(circle at 35% 35%, ${a(0.25)} 0%, ${a(0.12)} 40%, ${a(0.04)} 70%, transparent 100%)`)

  const borderColor = isLight
    ? (shift > 0 ? w(0.4) : d(0.3))
    : (shift > 0 ? w(0.3) : a(0.18))
  const shadowInner = isLight
    ? (shift > 0 ? w(0.2) : d(0.15))
    : (shift > 0 ? w(0.15) : a(0.08))
  const shadowOuter = isLight
    ? (shift > 0 ? w(0.25) : d(0.2))
    : (shift > 0 ? w(0.2) : a(0.12))

  return (
    <div
      className="relative flex items-center justify-center"
      style={{ width: size * 2, height: size * 2 }}
    >
      {/* Outer glow — subtle dark shadow on light backgrounds */}
      <motion.div
        className="absolute rounded-full"
        style={{
          width: size * 1.8,
          height: size * 1.8,
          background: isLight
            ? `radial-gradient(circle, rgba(0,0,0,0.06) 0%, transparent 70%)`
            : `radial-gradient(circle, ${c(0.18)} 0%, transparent 70%)`,
          filter: `blur(${size * 0.3}px)`,
        }}
        variants={activeGlowVariants}
        animate="animate"
      />

      {/* Mid glow ring */}
      <motion.div
        className="absolute rounded-full"
        style={{
          width: size * 1.2,
          height: size * 1.2,
          background: isLight
            ? `radial-gradient(circle, rgba(0,0,0,0.04) 0%, transparent 60%)`
            : `radial-gradient(circle, ${c(0.12)} 0%, transparent 60%)`,
          filter: `blur(${size * 0.15}px)`,
        }}
        animate={{
          scale: [1, 1.12, 1],
          opacity: [glowOpacity * 0.6, glowOpacity * 0.25, glowOpacity * 0.6],
          transition: {
            duration: breatheDuration * 0.8,
            repeat: Infinity,
            ease: 'easeInOut' as const,
            delay: 0.3,
          },
        }}
      />

      {/* Sonar ping ring — listening only */}
      {state === 'listening' && (
        <motion.div
          className="absolute rounded-full"
          style={{
            width: size,
            height: size,
            border: `2px solid ${isLight ? d(0.4) : a(0.4)}`,
          }}
          animate={{
            scale: [1, 2.2],
            opacity: [0.6, 0],
          }}
          transition={{
            duration: 1.5,
            repeat: Infinity,
            ease: 'easeOut',
          }}
        />
      )}

      {/* Second sonar ping (offset) — listening only */}
      {state === 'listening' && (
        <motion.div
          className="absolute rounded-full"
          style={{
            width: size,
            height: size,
            border: `2px solid ${isLight ? d(0.3) : a(0.3)}`,
          }}
          animate={{
            scale: [1, 2.2],
            opacity: [0.4, 0],
          }}
          transition={{
            duration: 1.5,
            repeat: Infinity,
            ease: 'easeOut',
            delay: 0.75,
          }}
        />
      )}

      {/* Core orb */}
      <motion.div
        className="absolute rounded-full"
        style={{
          width: size,
          height: size,
          background: orbBg,
          border: `1.5px solid ${borderColor}`,
          boxShadow: `
            inset 0 0 ${size * 0.3}px ${shadowInner},
            0 0 ${size * config.borderGlow * 3}px ${shadowOuter},
            0 0 ${size * config.borderGlow * 6}px ${c(config.borderGlow * 0.5)}
          `,
        }}
        variants={activeOrbVariants}
        animate={state === 'thinking'
          ? { ...(activeOrbVariants as any).animate, ...thinkingRotation }
          : 'animate'}
      />

      {/* Inner highlight — gives depth, orbits more visibly when thinking */}
      <motion.div
        className="absolute rounded-full"
        style={{
          width: size * 0.4,
          height: size * 0.4,
          background: isLight
            ? `radial-gradient(circle, ${shift > 0 ? w(0.35) : d(0.3)} 0%, transparent 70%)`
            : `radial-gradient(circle, ${shift > 0 ? w(0.25) : a(0.2)} 0%, transparent 70%)`,
          filter: `blur(${size * 0.08}px)`,
        }}
        animate={state === 'thinking'
          ? {
              // Orbit around center when thinking
              x: [0, size * 0.2, 0, -size * 0.2, 0],
              y: [-size * 0.15, 0, size * 0.15, 0, -size * 0.15],
              opacity: [0.7, 0.5, 0.7, 0.5, 0.7],
              transition: {
                duration: 2,
                repeat: Infinity,
                ease: 'linear' as const,
              },
            }
          : {
              x: 0,
              y: -size * 0.15,
              opacity: [0.6, 0.3, 0.6],
              transition: {
                duration: breatheDuration * 0.7,
                repeat: Infinity,
                ease: 'easeInOut' as const,
              },
            }}
      />
    </div>
  )
}
