/**
 * Thought -- a single thought element orbiting the avatar.
 *
 * 3-phase lifecycle:
 *   Phase 1: SPAWN   -- personality-style element flies out from avatar center
 *   Phase 2: PROCESS -- icon becomes prominent, energetic animation, gentle orbit float
 *   Phase 3: RESOLVE -- personality wrapper morphs away, HD widget appears
 *
 * Position is computed from polar coordinates (angle + distance) relative
 * to the avatar center. Uses Framer Motion spring physics for the orbit
 * animation and keyframes for the processing float.
 */

import { useEffect, useState } from 'react'
import { motion, useSpring, useTransform, AnimatePresence } from 'framer-motion'
import type { AvatarType, IntentBadge } from '../../types/assistant'
import { ThoughtRenderer } from './ThoughtRenderer'
import { ResolvedWidget } from './ResolvedWidget'

type ThoughtPhase = 'spawn' | 'processing' | 'resolve'

interface ThoughtProps {
  badge: IntentBadge
  angle: number           // radians, orbit position
  distance: number        // px, orbit radius
  center: { x: number; y: number }  // avatar center in viewport coords
  avatarType: AvatarType
}

/** Slight curve offset so the path from center to orbit isn't a straight line. */
function curvedPath(angle: number, distance: number): { x: number; y: number } {
  const perpAngle = angle + Math.PI / 2
  const curve = Math.sin(angle * 3) * distance * 0.08
  return {
    x: Math.cos(angle) * distance + Math.cos(perpAngle) * curve,
    y: Math.sin(angle) * distance + Math.sin(perpAngle) * curve,
  }
}

export function Thought({ badge, angle, distance, center, avatarType }: ThoughtProps) {
  const [phase, setPhase] = useState<ThoughtPhase>('spawn')

  const target = curvedPath(angle, distance)
  const THOUGHT_SIZE = 44
  const RESOLVED_SIZE = 60

  // Spring-driven offset from center
  const springConfig = { stiffness: 120, damping: 18, mass: 0.8 }
  const offsetX = useSpring(0, springConfig)
  const offsetY = useSpring(0, springConfig)
  const thoughtScale = useSpring(0.3, springConfig)
  const thoughtOpacity = useSpring(0, { stiffness: 100, damping: 20 })

  // Phase 1 -> Phase 2: spawn to processing
  useEffect(() => {
    const t = setTimeout(() => {
      offsetX.set(target.x)
      offsetY.set(target.y)
      thoughtScale.set(1)
      thoughtOpacity.set(1)
      setPhase('processing')
    }, 50)
    return () => clearTimeout(t)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Phase 2 -> Phase 3: processing to resolve
  useEffect(() => {
    if (badge.status === 'done' || badge.status === 'failed') {
      setPhase('resolve')
    }
  }, [badge.status])

  // Phase 3 fade-out after resolve hold time
  useEffect(() => {
    if (phase !== 'resolve') return
    const holdTime = badge.status === 'done' ? 3200 : 2800
    const t = setTimeout(() => {
      thoughtOpacity.set(0)
      thoughtScale.set(0.6)
    }, holdTime)
    return () => clearTimeout(t)
  }, [phase, badge.status]) // eslint-disable-line react-hooks/exhaustive-deps

  // Compute absolute x/y (center the element)
  const halfSize = phase === 'resolve' ? RESOLVED_SIZE / 2 : THOUGHT_SIZE / 2
  const absX = useTransform(offsetX, v => center.x + v - halfSize)
  const absY = useTransform(offsetY, v => center.y + v - halfSize)

  const isProcessing = phase === 'processing' && badge.status === 'processing'

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
      {/* Orbital float animation during processing */}
      <motion.div
        animate={
          isProcessing
            ? { y: [0, -3, 0, 3, 0], x: [0, 1, 0, -1, 0] }
            : {}
        }
        transition={
          isProcessing
            ? { duration: 3.5, repeat: Infinity, ease: 'easeInOut' }
            : {}
        }
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 4,
        }}
      >
        <AnimatePresence mode="wait">
          {phase !== 'resolve' ? (
            /* Phase 1 + 2: personality-styled thought with icon */
            <motion.div
              key="thought-renderer"
              exit={{ scale: 0.7, opacity: 0, filter: 'blur(4px)' }}
              transition={{ duration: 0.35 }}
            >
              <ThoughtRenderer
                avatarType={avatarType}
                icon={badge.icon}
                status={badge.status}
                size={THOUGHT_SIZE}
                phase={phase === 'spawn' ? 'spawn' : 'processing'}
              />
            </motion.div>
          ) : (
            /* Phase 3: HD resolved widget */
            <motion.div
              key="resolved-widget"
              initial={{ scale: 0.7, opacity: 0, filter: 'blur(4px)' }}
              animate={{ scale: 1, opacity: 1, filter: 'blur(0px)' }}
              transition={{ duration: 0.4, ease: 'easeOut' }}
            >
              <ResolvedWidget badge={badge} size={RESOLVED_SIZE} />
            </motion.div>
          )}
        </AnimatePresence>

        {/* Detail text for non-resolve phases */}
        {phase !== 'resolve' && badge.detail && badge.status === 'processing' && (
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
      </motion.div>
    </motion.div>
  )
}
