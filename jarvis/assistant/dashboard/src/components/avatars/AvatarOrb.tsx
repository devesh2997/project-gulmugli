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
}

const STATE_CONFIGS: Record<AssistantState, StateConfig> = {
  idle: {
    scale: 1,
    opacity: 0.6,
    glowOpacity: 0.2,
    glowScale: 1,
    breatheMultiplier: 1,
  },
  listening: {
    scale: 1.08,
    opacity: 0.85,
    glowOpacity: 0.4,
    glowScale: 1.2,
    breatheMultiplier: 0.5,
  },
  thinking: {
    scale: 0.95,
    opacity: 0.7,
    glowOpacity: 0.3,
    glowScale: 1.1,
    breatheMultiplier: 0.3,
  },
  speaking: {
    scale: 1.05,
    opacity: 0.9,
    glowOpacity: 0.5,
    glowScale: 1.3,
    breatheMultiplier: 0.15,
  },
  sleeping: {
    scale: 0.9,
    opacity: 0.2,
    glowOpacity: 0.05,
    glowScale: 0.85,
    breatheMultiplier: 2,
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

export function AvatarOrb({ size, state }: AvatarOrbProps) {
  const config = STATE_CONFIGS[state] ?? STATE_CONFIGS.idle

  // Read base duration once per render. TokenProvider updates the CSS var
  // reactively, so the next re-render picks up the new personality's timing.
  const baseDuration = getBaseDuration()
  const breatheDuration = baseDuration * config.breatheMultiplier

  const orbVariants = useMemo(() => ({
    animate: {
      scale: [config.scale, config.scale * 1.04, config.scale],
      opacity: [config.opacity, config.opacity * 0.9, config.opacity],
      transition: {
        duration: breatheDuration,
        repeat: Infinity,
        ease: 'easeInOut' as const,
      },
    },
  }), [config, breatheDuration])

  const glowVariants = useMemo(() => ({
    animate: {
      scale: [config.glowScale, config.glowScale * 1.15, config.glowScale],
      opacity: [config.glowOpacity, config.glowOpacity * 0.6, config.glowOpacity],
      transition: {
        duration: breatheDuration * 1.2,
        repeat: Infinity,
        ease: 'easeInOut' as const,
      },
    },
  }), [config, breatheDuration])

  // Thinking state: slow rotation to convey processing
  const thinkingRotation = state === 'thinking'
    ? {
        rotate: [0, 360],
        transition: {
          duration: 3,
          repeat: Infinity,
          ease: 'linear' as const,
        },
      }
    : {}

  const accent = 'var(--personality-accent)'
  const glow = 'var(--personality-glow_color)'

  return (
    <div
      className="relative flex items-center justify-center"
      style={{ width: size * 2, height: size * 2 }}
    >
      {/* Outer glow */}
      <motion.div
        className="absolute rounded-full"
        style={{
          width: size * 1.8,
          height: size * 1.8,
          background: `radial-gradient(circle, ${glow} 0%, transparent 70%)`,
          opacity: config.glowOpacity,
          filter: `blur(${size * 0.3}px)`,
        }}
        variants={glowVariants}
        animate="animate"
      />

      {/* Mid glow ring */}
      <motion.div
        className="absolute rounded-full"
        style={{
          width: size * 1.2,
          height: size * 1.2,
          background: `radial-gradient(circle, ${glow} 0%, transparent 60%)`,
          filter: `blur(${size * 0.15}px)`,
        }}
        animate={{
          scale: [1, 1.08, 1],
          opacity: [config.glowOpacity * 0.5, config.glowOpacity * 0.3, config.glowOpacity * 0.5],
          transition: {
            duration: breatheDuration * 0.8,
            repeat: Infinity,
            ease: 'easeInOut' as const,
            delay: 0.3,
          },
        }}
      />

      {/* Core orb */}
      <motion.div
        className="absolute rounded-full"
        style={{
          width: size,
          height: size,
          background: `radial-gradient(circle at 35% 35%,
            ${accent}40 0%,
            ${accent}20 40%,
            ${accent}08 70%,
            transparent 100%)`,
          border: `1px solid ${accent}30`,
          boxShadow: `
            inset 0 0 ${size * 0.3}px ${accent}15,
            0 0 ${size * 0.2}px ${accent}20
          `,
        }}
        variants={orbVariants}
        animate={state === 'thinking'
          ? { ...orbVariants.animate, ...thinkingRotation }
          : 'animate'}
      />

      {/* Inner highlight — gives depth */}
      <motion.div
        className="absolute rounded-full"
        style={{
          width: size * 0.4,
          height: size * 0.4,
          top: `calc(50% - ${size * 0.28}px)`,
          left: `calc(50% - ${size * 0.12}px)`,
          background: `radial-gradient(circle, ${accent}25 0%, transparent 70%)`,
          filter: `blur(${size * 0.08}px)`,
        }}
        animate={{
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
