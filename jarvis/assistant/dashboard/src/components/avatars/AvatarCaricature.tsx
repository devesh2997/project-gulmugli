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

import { useMemo } from 'react'
import { motion } from 'framer-motion'
import type { AssistantState, AssistantMood } from '../../types/assistant'
import type { StrokeFeature, GlowFeature } from './lightFaces'
import {
  chandlerFaces,
  chandlerMoodOverlays,
  type ChandlerFaceState,
} from './chandlerFaces'

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
function StrokeElement({ name, feature }: { name: string; feature: StrokeFeature }) {
  const accent = 'var(--personality-accent)'
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
function GlowElement({ name, glow }: { name: string; glow: GlowFeature }) {
  const color = glow.color ?? 'var(--personality-accent)'

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

  const { features, glows } = useMemo(
    () => mergeFace(state, mood),
    [state, mood],
  )

  const glow = 'var(--personality-glow_color)'

  return (
    <div
      className="relative flex items-center justify-center"
      style={{ width: size * 2, height: size * 2 }}
    >
      {/* Background glow — warm orange, slightly more saturated than Girlfriend's */}
      <motion.div
        className="absolute rounded-full"
        style={{
          width: size * 1.3,
          height: size * 1.3,
          background: `radial-gradient(circle, ${glow} 0%, transparent 70%)`,
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

      {/* Face SVG */}
      <svg
        viewBox="0 0 120 120"
        width={size}
        height={size}
        style={{ overflow: 'visible' }}
      >
        {/* Glow halos (render behind strokes) */}
        {Object.entries(glows).map(([name, g]) => (
          <GlowElement key={name} name={name} glow={g} />
        ))}

        {/* Stroke features */}
        {Object.entries(features).map(([name, f]) => (
          <StrokeElement key={name} name={name} feature={f} />
        ))}

        {/* Sleeping: slow breathing pulse on the mouth */}
        {isSleeping && (
          <motion.path
            d={features.mouth?.d ?? 'M44 80 Q60 82, 76 80'}
            stroke="var(--personality-accent)"
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
      </svg>
    </div>
  )
}
