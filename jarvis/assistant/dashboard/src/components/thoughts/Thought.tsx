/**
 * Thought — a single thought element orbiting the avatar.
 *
 * Handles the full lifecycle: spawn (from avatar center) -> orbit (float) ->
 * resolve (glow + dissolve back or shake + dissolve outward).
 *
 * Position is computed from polar coordinates (angle + distance) relative
 * to the avatar center. Uses Framer Motion spring physics for the orbit
 * animation and keyframes for the processing float.
 */

import { useEffect, useState } from 'react'
import { motion, useSpring, useTransform } from 'framer-motion'
import type { AvatarType, IntentBadge } from '../../types/assistant'
import { ThoughtRenderer } from './ThoughtRenderer'

interface ThoughtProps {
  badge: IntentBadge
  angle: number           // radians, orbit position
  distance: number        // px, orbit radius
  center: { x: number; y: number }  // avatar center in viewport coords
  avatarType: AvatarType
}

/** Slight curve offset so the path from center to orbit isn't a straight line. */
function curvedPath(angle: number, distance: number): { x: number; y: number } {
  // Add a small perpendicular offset that fades as we approach the target
  const perpAngle = angle + Math.PI / 2
  const curve = Math.sin(angle * 3) * distance * 0.08
  return {
    x: Math.cos(angle) * distance + Math.cos(perpAngle) * curve,
    y: Math.sin(angle) * distance + Math.sin(perpAngle) * curve,
  }
}

export function Thought({ badge, angle, distance, center, avatarType }: ThoughtProps) {
  const [phase, setPhase] = useState<'spawn' | 'orbit' | 'resolve'>('spawn')

  const target = curvedPath(angle, distance)

  // Spring-driven offset from center
  const springConfig = { stiffness: 120, damping: 18, mass: 0.8 }
  const offsetX = useSpring(0, springConfig)
  const offsetY = useSpring(0, springConfig)
  const thoughtScale = useSpring(0.3, springConfig)
  const thoughtOpacity = useSpring(0, { stiffness: 100, damping: 20 })

  // Spawn -> orbit
  useEffect(() => {
    // Small delay so the spawn is visible
    const t = setTimeout(() => {
      offsetX.set(target.x)
      offsetY.set(target.y)
      thoughtScale.set(1)
      thoughtOpacity.set(1)
      setPhase('orbit')
    }, 50)
    return () => clearTimeout(t)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Resolve when done/failed
  useEffect(() => {
    if (badge.status === 'done' || badge.status === 'failed') {
      setPhase('resolve')
      if (badge.status === 'done') {
        // Absorb back toward center
        const t = setTimeout(() => {
          offsetX.set(0)
          offsetY.set(0)
          thoughtScale.set(0.5)
          thoughtOpacity.set(0)
        }, 400) // brief glow hold
        return () => clearTimeout(t)
      } else {
        // Rejected: dissolve outward
        const t = setTimeout(() => {
          offsetX.set(target.x * 1.8)
          offsetY.set(target.y * 1.8)
          thoughtScale.set(0.3)
          thoughtOpacity.set(0)
        }, 300) // after shake
        return () => clearTimeout(t)
      }
    }
  }, [badge.status]) // eslint-disable-line react-hooks/exhaustive-deps

  // Compute absolute x/y
  const absX = useTransform(offsetX, v => center.x + v - 10) // center the ~20px thought
  const absY = useTransform(offsetY, v => center.y + v - 10)

  const isDone = badge.status === 'done'
  const isFailed = badge.status === 'failed'
  const isProcessing = badge.status === 'processing'
  const thoughtSize = 20

  return (
    <motion.div
      style={{
        position: 'fixed',
        left: absX,
        top: absY,
        scale: thoughtScale,
        opacity: thoughtOpacity,
        pointerEvents: 'none',
        zIndex: 40,
      }}
    >
      {/* Resolve glow/shake wrapper */}
      <motion.div
        animate={
          isDone ? { filter: ['brightness(1)', 'brightness(1.6)', 'brightness(1)'] }
          : isFailed ? { x: [0, -3, 3, -2, 2, 0] }
          : isProcessing ? { y: [0, -2, 0, 2, 0] }
          : {}
        }
        transition={
          isDone ? { duration: 0.4 }
          : isFailed ? { duration: 0.35 }
          : isProcessing ? { duration: 3, repeat: Infinity, ease: 'easeInOut' }
          : {}
        }
      >
        <ThoughtRenderer
          avatarType={avatarType}
          icon={badge.icon}
          status={badge.status}
          size={thoughtSize}
        />
      </motion.div>
    </motion.div>
  )
}
