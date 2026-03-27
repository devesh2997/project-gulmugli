/**
 * AvatarPixel — Devesh personality avatar.
 *
 * A 32x32 pixel grid face rendered as SVG rects. Chunky, deliberate, clearly
 * digital. State changes animate each pixel to its new position with a
 * staggered cascade effect.
 *
 * Colors come from CSS custom properties set by TokenProvider:
 *   --personality-accent      pixel fill color
 *   --personality-glow_color  background glow color
 */

import { useMemo, useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { AssistantState, AssistantMood } from '../../types/assistant'
import {
  pixelFaces,
  pixelMoodOverlays,
  speakingMouthClosed,
  type PixelData,
  type FaceFeature,
  type MoodFeature,
} from './pixelFaces'

export interface AvatarPixelProps {
  size: number
  state: AssistantState
  mood: AssistantMood
}

/** Stable key for a pixel so Framer Motion can track it across states. */
function pixelKey(feature: string, index: number): string {
  return `${feature}-${index}`
}

/** Blush features use hardcoded pink, everything else uses accent. */
const BLUSH_COLOR = '#ff6b8a'

function isBlush(feature: string): boolean {
  return feature === 'blush_left' || feature === 'blush_right'
}

/** State-dependent glow config for the background effect. */
interface GlowConfig {
  opacity: number
  scale: number
  pulseDuration: number
  /** Warm color shift (0 = glow color, 1 = warm orange) */
  warmShift: number
}

const GLOW_CONFIGS: Record<AssistantState, GlowConfig> = {
  idle: { opacity: 0.12, scale: 1, pulseDuration: 4, warmShift: 0 },
  listening: { opacity: 0.4, scale: 1.15, pulseDuration: 1.5, warmShift: 0 },
  thinking: { opacity: 0.3, scale: 1.1, pulseDuration: 1.2, warmShift: 0.5 },
  speaking: { opacity: 0.45, scale: 1.2, pulseDuration: 0.6, warmShift: 0 },
  sleeping: { opacity: 0.03, scale: 0.8, pulseDuration: 6, warmShift: 0 },
}

/**
 * Merge state pixels with mood overlay pixels.
 * - For face features present in both state and mood, the mood REPLACES
 *   the state data (e.g. happy squint eyes replace normal eyes).
 * - Blush features are purely additive (no state equivalent).
 */
function mergePixels(
  state: AssistantState,
  mood: AssistantMood,
  mouthFrame?: PixelData,
): { feature: string; pixels: PixelData }[] {
  const face = pixelFaces[state] ?? pixelFaces.idle
  const overlay = mood !== 'neutral' ? pixelMoodOverlays[mood] : undefined

  const features: Record<string, PixelData> = {}

  // Start with state pixels
  for (const [key, data] of Object.entries(face)) {
    features[key] = data
  }

  // Override mouth with animation frame if provided (speaking)
  if (mouthFrame) {
    features.mouth = mouthFrame
  }

  // Apply mood overrides/additions
  if (overlay) {
    for (const [key, data] of Object.entries(overlay) as [MoodFeature, PixelData][]) {
      if (isBlush(key)) {
        // Additive — blush only exists in mood
        features[key] = data
      } else {
        // Replace the state feature with mood version
        features[key as FaceFeature] = data
      }
    }
  }

  return Object.entries(features).map(([feature, pixels]) => ({
    feature,
    pixels,
  }))
}

export function AvatarPixel({ size, state, mood }: AvatarPixelProps) {
  const isSleeping = state === 'sleeping'
  const isSpeaking = state === 'speaking'
  const isThinking = state === 'thinking'
  const isListening = state === 'listening'
  const glowConfig = GLOW_CONFIGS[state] ?? GLOW_CONFIGS.idle

  // Speaking mouth animation: alternate between open/closed every 300ms
  const [mouthOpen, setMouthOpen] = useState(true)
  useEffect(() => {
    if (!isSpeaking) {
      setMouthOpen(true)
      return
    }
    const interval = setInterval(() => setMouthOpen(prev => !prev), 300)
    return () => clearInterval(interval)
  }, [isSpeaking])

  // Idle blink: eyes close briefly every 3-5 seconds
  const isIdle = state === 'idle'
  const [isBlinking, setIsBlinking] = useState(false)
  useEffect(() => {
    if (!isIdle) { setIsBlinking(false); return }
    const scheduleBlink = () => {
      const delay = 3000 + Math.random() * 2000 // 3-5s random interval
      return setTimeout(() => {
        setIsBlinking(true)
        setTimeout(() => setIsBlinking(false), 150) // blink lasts 150ms
        timerId = scheduleBlink()
      }, delay)
    }
    let timerId = scheduleBlink()
    return () => clearTimeout(timerId)
  }, [isIdle])

  const mouthFrame = isSpeaking
    ? (mouthOpen ? pixelFaces.speaking.mouth : speakingMouthClosed)
    : undefined

  // Closed eyes for blink — single row, dimmer
  const blinkEyes: PixelData = [
    { x: 8, y: 13, opacity: 0.3 }, { x: 9, y: 13, opacity: 0.35 },
    { x: 10, y: 13, opacity: 0.35 }, { x: 11, y: 13, opacity: 0.3 },
  ]
  const blinkEyesR: PixelData = [
    { x: 20, y: 13, opacity: 0.3 }, { x: 21, y: 13, opacity: 0.35 },
    { x: 22, y: 13, opacity: 0.35 }, { x: 23, y: 13, opacity: 0.3 },
  ]

  const featureGroups = useMemo(() => {
    const base = mergePixels(state, mood, mouthFrame)
    if (!isBlinking) return base
    // Override eyes with closed variant during blink
    return base.map(g =>
      g.feature === 'left_eye' ? { ...g, pixels: blinkEyes }
      : g.feature === 'right_eye' ? { ...g, pixels: blinkEyesR }
      : g
    )
  }, [state, mood, mouthFrame, isBlinking])

  // Flatten all pixels with their keys and colors for rendering
  const allPixels = useMemo(() => {
    const result: {
      key: string
      x: number
      y: number
      opacity: number
      color: string
    }[] = []

    for (const { feature, pixels } of featureGroups) {
      for (let i = 0; i < pixels.length; i++) {
        const p = pixels[i]
        result.push({
          key: pixelKey(feature, i),
          x: p.x,
          y: p.y,
          opacity: p.opacity,
          color: isBlush(feature) ? BLUSH_COLOR : 'var(--personality-accent)',
        })
      }
    }

    return result
  }, [featureGroups])

  // Animate pixels: thinking = fast shimmer, idle/listening = gentle breathing
  const needsBreathing = isIdle || isListening
  const shimmerDelay = isThinking

  const accent = 'var(--personality-accent)'
  const glow = 'var(--personality-glow_color)'
  const warmGlow = '#ff9030'

  const glowColor = glowConfig.warmShift > 0
    ? `color-mix(in srgb, ${glow} ${Math.round((1 - glowConfig.warmShift) * 100)}%, ${warmGlow})`
    : glow

  return (
    <div
      className="relative flex items-center justify-center"
      style={{ width: size * 2, height: size * 2 }}
    >
      {/* Background glow — state-dependent intensity and color */}
      <motion.div
        className="absolute rounded-full"
        style={{
          width: size * 1.4,
          height: size * 1.4,
          background: `radial-gradient(circle, ${glowColor} 0%, transparent 70%)`,
          filter: `blur(${size * 0.25}px)`,
        }}
        animate={{
          opacity: [glowConfig.opacity, glowConfig.opacity * 0.5, glowConfig.opacity],
          scale: [glowConfig.scale, glowConfig.scale * 1.1, glowConfig.scale],
        }}
        transition={{
          duration: glowConfig.pulseDuration,
          repeat: Infinity,
          ease: 'easeInOut' as const,
        }}
      />

      {/* Pixel grid SVG — facial expressions ARE the state indicator */}
      {/* Gentle vertical float in idle — the face "breathes" spatially */}
      <motion.svg
        viewBox="0 0 32 32"
        width={size}
        height={size}
        style={{ imageRendering: 'pixelated' }}
        animate={isIdle ? { y: [0, -2, 0, 1, 0] } : { y: 0 }}
        transition={isIdle ? { duration: 4, repeat: Infinity, ease: 'easeInOut' } : { duration: 0.3 }}
      >
        <AnimatePresence mode="popLayout">
          {allPixels.map((pixel, index) => (
            <motion.rect
              key={pixel.key}
              width={1}
              height={1}
              fill={pixel.color}
              initial={{ x: 16, y: 16, opacity: 0 }}
              animate={{
                x: pixel.x,
                y: pixel.y,
                opacity: shimmerDelay
                  ? [pixel.opacity, pixel.opacity * 0.4, pixel.opacity]
                  : needsBreathing
                    ? [pixel.opacity, pixel.opacity * 0.65, pixel.opacity]
                    : pixel.opacity,
              }}
              exit={{ opacity: 0, scale: 0 }}
              transition={shimmerDelay
                ? {
                    x: { type: 'spring', stiffness: 200, damping: 20, delay: index * 0.015 },
                    y: { type: 'spring', stiffness: 200, damping: 20, delay: index * 0.015 },
                    opacity: {
                      duration: 1.2,
                      repeat: Infinity,
                      ease: 'easeInOut' as const,
                      delay: (index % 8) * 0.15,
                    },
                  }
                : needsBreathing
                  ? {
                      x: { type: 'spring', stiffness: 200, damping: 20, delay: index * 0.02 },
                      y: { type: 'spring', stiffness: 200, damping: 20, delay: index * 0.02 },
                      opacity: {
                        duration: 3,
                        repeat: Infinity,
                        ease: 'easeInOut' as const,
                        delay: (index % 6) * 0.3,
                      },
                    }
                  : {
                      x: { type: 'spring', stiffness: 200, damping: 20, delay: index * 0.02 },
                      y: { type: 'spring', stiffness: 200, damping: 20, delay: index * 0.02 },
                      opacity: { duration: 0.3, delay: index * 0.02 },
                    }}
            />
          ))}
        </AnimatePresence>

        {/* Sleeping pulse — 2-3 status pixels with slow fade */}
        {isSleeping && (
          <>
            {(pixelFaces.sleeping.mouth).map((p, i) => (
              <motion.rect
                key={`sleep-pulse-${i}`}
                width={1}
                height={1}
                x={p.x}
                y={p.y}
                fill={accent}
                animate={{
                  opacity: [p.opacity, p.opacity * 0.4, p.opacity],
                }}
                transition={{
                  duration: 3,
                  repeat: Infinity,
                  ease: 'easeInOut',
                  delay: i * 0.3,
                }}
              />
            ))}
          </>
        )}
      </motion.svg>
    </div>
  )
}
