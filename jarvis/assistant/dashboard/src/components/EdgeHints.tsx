/**
 * EdgeHints -- barely visible swipe affordances on the home screen.
 *
 * Small personality-colored dots at left, right, and bottom edges
 * that glow very subtly when touched near them. So subtle that you
 * only notice them when looking for them.
 */

import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

interface Props {
  /** Hide hints when a panel is open */
  visible: boolean
}

interface HintDot {
  edge: 'left' | 'right' | 'bottom'
  style: React.CSSProperties
}

const DOTS: HintDot[] = [
  // Left edge -- settings/preferences
  {
    edge: 'left',
    style: {
      position: 'absolute',
      left: 6,
      top: '50%',
      transform: 'translateY(-50%)',
    },
  },
  // Right edge -- lights/controls
  {
    edge: 'right',
    style: {
      position: 'absolute',
      right: 6,
      top: '50%',
      transform: 'translateY(-50%)',
    },
  },
  // Bottom edge -- transcript
  {
    edge: 'bottom',
    style: {
      position: 'absolute',
      bottom: 6,
      left: '50%',
      transform: 'translateX(-50%)',
    },
  },
]

export function EdgeHints({ visible }: Props) {
  const [nearEdge, setNearEdge] = useState<string | null>(null)

  // Track pointer proximity to edges
  const handlePointerMove = useCallback((e: PointerEvent) => {
    const { clientX, clientY } = e
    const w = window.innerWidth
    const h = window.innerHeight
    const threshold = 40

    if (clientX < threshold) {
      setNearEdge('left')
    } else if (clientX > w - threshold) {
      setNearEdge('right')
    } else if (clientY > h - threshold) {
      setNearEdge('bottom')
    } else {
      setNearEdge(null)
    }
  }, [])

  useEffect(() => {
    window.addEventListener('pointermove', handlePointerMove, { passive: true })
    return () => window.removeEventListener('pointermove', handlePointerMove)
  }, [handlePointerMove])

  // Also clear on pointer leave (edge of screen)
  useEffect(() => {
    const onLeave = () => setNearEdge(null)
    document.addEventListener('pointerleave', onLeave)
    return () => document.removeEventListener('pointerleave', onLeave)
  }, [])

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.5, delay: 1 }}
          style={{
            position: 'absolute',
            inset: 0,
            pointerEvents: 'none',
            zIndex: 5,
          }}
        >
          {DOTS.map(dot => {
            const isNear = nearEdge === dot.edge
            const isVertical = dot.edge === 'left' || dot.edge === 'right'

            return (
              <motion.div
                key={dot.edge}
                animate={{
                  opacity: isNear ? 0.5 : 0.12,
                  scale: isNear ? 1.8 : 1,
                }}
                transition={{
                  type: 'spring',
                  stiffness: 300,
                  damping: 25,
                }}
                style={{
                  ...dot.style,
                  width: isVertical ? 3 : 16,
                  height: isVertical ? 16 : 3,
                  borderRadius: 2,
                  background: 'var(--personality-accent)',
                  boxShadow: isNear
                    ? '0 0 12px rgba(var(--personality-accent-rgb), 0.3)'
                    : 'none',
                }}
              />
            )
          })}
        </motion.div>
      )}
    </AnimatePresence>
  )
}
