/**
 * AvatarCaricature — Chandler personality avatar.
 *
 * A minimal line-art caricature rendered as SVG strokes. The MOST detailed of
 * all four avatar variants: messy side-parted hair, strong expressive brows,
 * sardonic narrow eyes, and the signature asymmetric half-smirk. Like a quick
 * artist's sketch, not a realistic portrait.
 *
 * Colors come from CSS custom properties set by TokenProvider:
 *   --personality-accent      stroke color
 *   --personality-glow_color  background glow color (warm orange for Chandler)
 */

import { useMemo, useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { useLightMode } from '../../hooks/useLightMode'
import type { AssistantState, AssistantMood } from '../../types/assistant'
import type { StrokeFeature, GlowFeature } from './lightFaces'
import {
  chandlerFaces,
  chandlerMoodOverlays,
  type ChandlerFaceState,
} from './chandlerFaces'

/**
 * Chandler speaking mouth frames — upper lip + lower lip path pairs.
 * Cycles to give natural Chandler-style animated talking.
 */
const CHANDLER_MOUTH_FRAMES: { mouth: string; mouth_lower: string }[] = [
  // Wide open
  { mouth: 'M40 78 Q50 74, 60 75 Q70 74, 80 78', mouth_lower: 'M42 82 Q52 90, 60 91 Q68 90, 78 82' },
  // Half open
  { mouth: 'M42 79 Q52 76, 60 77 Q68 76, 78 79', mouth_lower: 'M44 83 Q54 87, 60 88 Q66 87, 76 83' },
  // Nearly closed with smirk
  { mouth: 'M42 80 Q52 82, 60 81 Q70 79, 78 76', mouth_lower: 'M44 84 Q54 86, 66 84' },
  // Medium open
  { mouth: 'M40 79 Q50 75, 60 76 Q70 75, 80 79', mouth_lower: 'M42 83 Q52 89, 60 90 Q68 89, 78 83' },
  // Closed smirk
  { mouth: 'M40 80 Q50 84, 58 82 Q66 80, 74 76 Q78 74, 80 72', mouth_lower: 'M44 84 Q54 88, 64 85' },
]

export interface AvatarCaricatureProps {
  size: number
  state: AssistantState
  mood: AssistantMood
}

/** Merge base state with mood overlay. Mood features/glows override state ones by key. */
function mergeFace(state: AssistantState, mood: AssistantMood): {
  features: Record<string, StrokeFeature>
  glows: Record<string, GlowFeature>
} {
  const base: ChandlerFaceState = chandlerFaces[state] ?? chandlerFaces.idle
  const overlay = mood !== 'neutral' ? chandlerMoodOverlays[mood] : undefined

  const features = { ...base.features }
  const glows = { ...base.glows }

  if (overlay) {
    if (overlay.features) Object.assign(features, overlay.features)
    if (overlay.glows) Object.assign(glows, overlay.glows)
  }

  return { features, glows }
}

/** Render a single stroke feature as an SVG element with Framer Motion animation. */
function StrokeElement({ name, feature, isLight }: { name: string; feature: StrokeFeature; isLight?: boolean }) {
  const accent = isLight ? '#2a1a0a' : 'var(--personality-accent)'
  const common = {
    stroke: feature.fill ? 'none' : accent,
    fill: feature.fill ? accent : 'none',
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
  }

  const transition = {
    duration: 0.5,
    ease: 'easeInOut' as const,
  }

  switch (feature.type) {
    case 'path':
      return (
        <motion.path
          key={name}
          {...common}
          initial={false}
          animate={{
            d: feature.d!,
            strokeWidth: feature.strokeWidth,
            opacity: feature.opacity,
          }}
          transition={{ ...transition, d: { duration: 0.6, ease: 'easeInOut' } }}
        />
      )

    case 'line':
      return (
        <motion.line
          key={name}
          {...common}
          initial={false}
          animate={{
            x1: feature.x1!,
            y1: feature.y1!,
            x2: feature.x2!,
            y2: feature.y2!,
            strokeWidth: feature.strokeWidth,
            opacity: feature.opacity,
          }}
          transition={transition}
        />
      )

    case 'circle':
      return (
        <motion.circle
          key={name}
          {...common}
          initial={false}
          animate={{
            cx: feature.cx!,
            cy: feature.cy!,
            r: feature.r!,
            strokeWidth: feature.strokeWidth,
            opacity: feature.opacity,
          }}
          transition={transition}
        />
      )

    case 'ellipse':
      return (
        <motion.ellipse
          key={name}
          {...common}
          initial={false}
          animate={{
            cx: feature.cx!,
            cy: feature.cy!,
            rx: feature.rx ?? feature.r!,
            ry: feature.ry ?? feature.r!,
            strokeWidth: feature.strokeWidth,
            opacity: feature.opacity,
          }}
          transition={transition}
        />
      )

    default:
      return null
  }
}

/** Render a glow halo as an animated radial circle. */
function GlowElement({ name, glow, isLight }: { name: string; glow: GlowFeature; isLight?: boolean }) {
  const color = isLight ? 'rgba(42,26,10,0.4)' : (glow.color ?? 'var(--personality-accent)')

  return (
    <motion.circle
      key={name}
      cx={glow.cx}
      cy={glow.cy}
      fill={color}
      stroke="none"
      initial={false}
      animate={{
        r: glow.r,
        opacity: glow.opacity,
      }}
      transition={{
        duration: 0.6,
        ease: 'easeInOut',
      }}
      style={{ filter: `blur(${glow.r * 0.4}px)` }}
    />
  )
}

export function AvatarCaricature({ size, state, mood }: AvatarCaricatureProps) {
  const isSleeping = state === 'sleeping'
  const isSpeaking = state === 'speaking'
  const isListening = state === 'listening'
  const isThinking = state === 'thinking'
  const isIdle = state === 'idle'
  const isLight = useLightMode()

  // Speaking mouth animation — cycle through Chandler's mouth shapes
  const [mouthFrame, setMouthFrame] = useState(0)
  useEffect(() => {
    if (!isSpeaking) { setMouthFrame(0); return }
    const cycle = () => {
      setMouthFrame(prev => (prev + 1) % CHANDLER_MOUTH_FRAMES.length)
      const nextDelay = 160 + Math.random() * 200
      timerId = setTimeout(cycle, nextDelay)
    }
    let timerId = setTimeout(cycle, 180)
    return () => clearTimeout(timerId)
  }, [isSpeaking])

  const { features: baseFeatures, glows } = useMemo(
    () => mergeFace(state, mood),
    [state, mood],
  )

  // Override mouth paths with animated frame when speaking
  const features = useMemo(() => {
    if (!isSpeaking) return baseFeatures
    const frame = CHANDLER_MOUTH_FRAMES[mouthFrame % CHANDLER_MOUTH_FRAMES.length]
    return {
      ...baseFeatures,
      mouth: { ...baseFeatures.mouth, d: frame.mouth },
      mouth_lower: { ...baseFeatures.mouth_lower, d: frame.mouth_lower },
    }
  }, [baseFeatures, isSpeaking, mouthFrame])

  const glow = 'var(--personality-glow_color)'

  return (
    <div
      className="relative flex items-center justify-center"
      style={{ width: size * 2, height: size * 2 }}
    >
      {/* Background glow — warm orange, slightly more saturated than Girlfriend's.
          On light backgrounds, swap for a subtle dark shadow. */}
      <motion.div
        className="absolute rounded-full"
        style={{
          width: size * 1.3,
          height: size * 1.3,
          background: isLight
            ? `radial-gradient(circle, rgba(0,0,0,0.06) 0%, transparent 70%)`
            : `radial-gradient(circle, ${glow} 0%, transparent 70%)`,
          filter: `blur(${size * 0.28}px)`,
        }}
        animate={{
          opacity: isSleeping ? 0.02 : 0.12,
          scale: isSleeping ? 0.85 : [1, 1.05, 1],
          transition: isSleeping
            ? { duration: 1.5 }
            : { duration: 5, repeat: Infinity, ease: 'easeInOut' as const },
        }}
      />

      {/* Face SVG — spatial movement per state */}
      <motion.svg
        viewBox="0 0 120 120"
        width={size}
        height={size}
        style={{ overflow: 'visible' }}
        animate={
          isIdle
            ? { y: [0, -1.2, 0, 0.6, 0], rotate: 0 }
            : isListening
              ? { y: -1.5, rotate: 0.5 }
              : isSpeaking
                ? { y: [0, -1, 0.5, 0], rotate: [0, 0.4, 0, -0.4] }
                : isThinking
                  ? { y: [0, 0.3, 0], rotate: [0, -1.2, 0] }
                  : { y: 0, rotate: 0 }
        }
        transition={
          isIdle
            ? { duration: 5, repeat: Infinity, ease: 'easeInOut' }
            : isListening
              ? { type: 'spring', stiffness: 350, damping: 18 }
              : isSpeaking
                ? { duration: 0.8, repeat: Infinity, ease: 'easeInOut' }
                : isThinking
                  ? { duration: 3, repeat: Infinity, ease: 'easeInOut' }
                  : { duration: 0.4 }
        }
      >
        {/* Glow halos (render behind strokes) */}
        {Object.entries(glows).map(([name, g]) => (
          <GlowElement key={name} name={name} glow={g} isLight={isLight} />
        ))}

        {/* Stroke features */}
        {Object.entries(features).map(([name, f]) => (
          <StrokeElement key={name} name={name} feature={f} isLight={isLight} />
        ))}

        {/* Sleeping: slow breathing pulse on the mouth */}
        {isSleeping && (
          <motion.path
            d={features.mouth?.d ?? 'M44 80 Q60 82, 76 80'}
            stroke={isLight ? '#2a1a0a' : 'var(--personality-accent)'}
            fill="none"
            strokeWidth={1.2}
            strokeLinecap="round"
            animate={{
              opacity: [0.08, 0.03, 0.08],
            }}
            transition={{
              duration: 4,
              repeat: Infinity,
              ease: 'easeInOut',
            }}
          />
        )}
      </motion.svg>
    </div>
  )
}
