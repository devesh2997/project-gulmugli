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
  const absX = useTransform(offsetX, v => center.x + v - 22) // center the ~44px thought
  const absY = useTransform(offsetY, v => center.y + v - 22)

  const isDone = badge.status === 'done'
  const isFailed = badge.status === 'failed'
  const isProcessing = badge.status === 'processing'
  const thoughtSize = 44

  // Resolved state: expand to show detail, then fade
  const resolvedSize = isDone ? 56 : isFailed ? 48 : thoughtSize
  const hasDetail = isDone && badge.detail

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
      {/* Resolve: expand + glow for done, shake for failed, float for processing */}
      <motion.div
        animate={
          isDone ? {
            scale: [1, 1.3, 1.2],
            filter: ['brightness(1)', 'brightness(1.8)', 'brightness(1.3)'],
          }
          : isFailed ? { x: [0, -4, 4, -3, 3, 0], scale: [1, 0.9, 1] }
          : isProcessing ? { y: [0, -2, 0, 2, 0] }
          : {}
        }
        transition={
          isDone ? { duration: 0.6, ease: 'easeOut' }
          : isFailed ? { duration: 0.4 }
          : isProcessing ? { duration: 3, repeat: Infinity, ease: 'easeInOut' }
          : {}
        }
        style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}
      >
        <ThoughtRenderer
          avatarType={avatarType}
          icon={badge.icon}
          status={badge.status}
          size={isDone ? resolvedSize : thoughtSize}
        />
        {/* Detail text fades in on done — shows what happened */}
        {hasDetail && (
          <motion.div
            initial={{ opacity: 0, y: 4, scale: 0.8 }}
            animate={{ opacity: 0.7, y: 0, scale: 1 }}
            transition={{ delay: 0.2, duration: 0.4 }}
            style={{
              fontSize: 9,
              fontWeight: 500,
              color: 'var(--personality-accent)',
              textAlign: 'center',
              maxWidth: 100,
              lineHeight: 1.2,
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              textShadow: '0 0 8px rgba(var(--personality-accent-rgb), 0.4)',
            }}
          >
            {badge.detail}
          </motion.div>
        )}
        {/* Failed indicator */}
        {isFailed && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.6 }}
            style={{
              fontSize: 9,
              fontWeight: 600,
              color: '#ff6b6b',
              textShadow: '0 0 6px rgba(255, 107, 107, 0.3)',
            }}
          >
            {badge.detail || 'Failed'}
          </motion.div>
        )}
      </motion.div>
    </motion.div>
  )
}
