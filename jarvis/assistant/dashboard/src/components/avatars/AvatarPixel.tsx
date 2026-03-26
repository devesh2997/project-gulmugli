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

import { useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { AssistantState, AssistantMood } from '../../types/assistant'
import {
  pixelFaces,
  pixelMoodOverlays,
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

/**
 * Merge state pixels with mood overlay pixels.
 * - For face features present in both state and mood, the mood REPLACES
 *   the state data (e.g. happy squint eyes replace normal eyes).
 * - Blush features are purely additive (no state equivalent).
 */
function mergePixels(
  state: AssistantState,
  mood: AssistantMood,
): { feature: string; pixels: PixelData }[] {
  const face = pixelFaces[state] ?? pixelFaces.idle
  const overlay = mood !== 'neutral' ? pixelMoodOverlays[mood] : undefined

  const features: Record<string, PixelData> = {}

  // Start with state pixels
  for (const [key, data] of Object.entries(face)) {
    features[key] = data
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

  const featureGroups = useMemo(
    () => mergePixels(state, mood),
    [state, mood],
  )

  // Flatten all pixels with their keys and colors for rendering
  const allPixels = useMemo(() => {
    const result: {
      key: string
      x: number
      y: number
      opacity: number
      color: string
    }[] = []

    let globalIndex = 0
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
        globalIndex++
      }
    }

    return result
  }, [featureGroups])

  const accent = 'var(--personality-accent)'
  const glow = 'var(--personality-glow_color)'

  return (
    <div
      className="relative flex items-center justify-center"
      style={{ width: size * 2, height: size * 2 }}
    >
      {/* Background glow — same as AvatarOrb but more subtle */}
      <motion.div
        className="absolute rounded-full"
        style={{
          width: size * 1.4,
          height: size * 1.4,
          background: `radial-gradient(circle, ${glow} 0%, transparent 70%)`,
          filter: `blur(${size * 0.25}px)`,
        }}
        animate={{
          opacity: isSleeping ? 0.03 : 0.15,
          scale: isSleeping ? 0.8 : [1, 1.06, 1],
          transition: isSleeping
            ? { duration: 1 }
            : { duration: 4, repeat: Infinity, ease: 'easeInOut' as const },
        }}
      />

      {/* Pixel grid SVG */}
      <svg
        viewBox="0 0 32 32"
        width={size}
        height={size}
        style={{ imageRendering: 'pixelated' }}
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
                opacity: pixel.opacity,
              }}
              exit={{ opacity: 0 }}
              transition={{
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
      </svg>
    </div>
  )
}
