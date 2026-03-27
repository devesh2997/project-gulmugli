/**
 * AvatarLight — Girlfriend personality avatar.
 *
 * A face made of thin SVG strokes (arcs, lines) with radial glow halos for
 * emotion. Ethereal, soft, bedroom-friendly. Features are drawn with actual
 * lines and curves, NOT dots — visually distinct from AvatarPixel's chunky grid.
 *
 * Colors come from CSS custom properties set by TokenProvider:
 *   --personality-accent      stroke color
 *   --personality-glow_color  background glow color
 */

import { useMemo, useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { useLightMode } from '../../hooks/useLightMode'
import type { AssistantState, AssistantMood } from '../../types/assistant'
import {
  lightFaces,
  lightMoodOverlays,
  type StrokeFeature,
  type GlowFeature,
  type LightFaceState,
} from './lightFaces'

/**
 * Speaking mouth path frames — cycles between open and closed shapes
 * for natural-feeling speech animation via path interpolation.
 */
const SPEAKING_MOUTH_PATHS = [
  'M40 77 Q60 94, 80 77',   // wide open
  'M44 79 Q60 86, 76 79',   // medium
  'M46 80 Q60 82, 74 80',   // nearly closed
  'M44 79 Q60 86, 76 79',   // medium
]

export interface AvatarLightProps {
  size: number
  state: AssistantState
  mood: AssistantMood
}

/** Merge base state with mood overlay. Mood features/glows override state ones by key. */
function mergeFace(state: AssistantState, mood: AssistantMood): {
  features: Record<string, StrokeFeature>
  glows: Record<string, GlowFeature>
} {
  const base: LightFaceState = lightFaces[state] ?? lightFaces.idle
  const overlay = mood !== 'neutral' ? lightMoodOverlays[mood] : undefined

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

export function AvatarLight({ size, state, mood }: AvatarLightProps) {
  const isSleeping = state === 'sleeping'
  const isSpeaking = state === 'speaking'
  const isListening = state === 'listening'
  const isThinking = state === 'thinking'
  const isIdle = state === 'idle'
  const isLight = useLightMode()

  // Speaking mouth animation — cycle through mouth shapes
  const [mouthFrame, setMouthFrame] = useState(0)
  useEffect(() => {
    if (!isSpeaking) { setMouthFrame(0); return }
    const cycle = () => {
      setMouthFrame(prev => (prev + 1) % SPEAKING_MOUTH_PATHS.length)
      const nextDelay = 180 + Math.random() * 180
      timerId = setTimeout(cycle, nextDelay)
    }
    let timerId = setTimeout(cycle, 200)
    return () => clearTimeout(timerId)
  }, [isSpeaking])

  const { features: baseFeatures, glows } = useMemo(
    () => mergeFace(state, mood),
    [state, mood],
  )

  // Override mouth path with animated frame when speaking
  const features = useMemo(() => {
    if (!isSpeaking) return baseFeatures
    const currentPath = SPEAKING_MOUTH_PATHS[mouthFrame % SPEAKING_MOUTH_PATHS.length]
    return {
      ...baseFeatures,
      mouth: { ...baseFeatures.mouth, d: currentPath },
    }
  }, [baseFeatures, isSpeaking, mouthFrame])

  const glow = 'var(--personality-glow_color)'

  return (
    <div
      className="relative flex items-center justify-center"
      style={{ width: size * 2, height: size * 2 }}
    >
      {/* Background glow — more subtle than AvatarOrb. Dark shadow on light bg. */}
      <motion.div
        className="absolute rounded-full"
        style={{
          width: size * 1.2,
          height: size * 1.2,
          background: isLight
            ? `radial-gradient(circle, rgba(0,0,0,0.05) 0%, transparent 70%)`
            : `radial-gradient(circle, ${glow} 0%, transparent 70%)`,
          filter: `blur(${size * 0.3}px)`,
        }}
        animate={{
          opacity: isSleeping ? 0.02 : 0.10,
          scale: isSleeping ? 0.85 : [1, 1.04, 1],
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
            ? { y: [0, -1.5, 0, 0.8, 0], rotate: 0 }
            : isListening
              ? { y: -2, rotate: 0 }
              : isSpeaking
                ? { y: [0, -1, 0.5, 0], rotate: [0, 0.3, 0, -0.3] }
                : isThinking
                  ? { y: [0, 0.5, 0], rotate: [0, -0.8, 0] }
                  : { y: 0, rotate: 0 }
        }
        transition={
          isIdle
            ? { duration: 4.5, repeat: Infinity, ease: 'easeInOut' }
            : isListening
              ? { type: 'spring', stiffness: 350, damping: 18 }
              : isSpeaking
                ? { duration: 0.7, repeat: Infinity, ease: 'easeInOut' }
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
            d={features.mouth?.d ?? 'M46 80 Q60 86, 74 80'}
            stroke={isLight ? '#2a1a0a' : 'var(--personality-accent)'}
            fill="none"
            strokeWidth={1.1}
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
