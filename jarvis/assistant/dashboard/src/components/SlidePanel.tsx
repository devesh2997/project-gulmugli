/**
 * SlidePanel — custom overlay panel with personality-themed edge glow.
 *
 * Features:
 *   - Slides in from left/right/bottom with organic spring physics
 *   - Personality accent glow along the opening edge
 *   - Organic pill-shaped drag handle with subtle pulse
 *   - Frosted glass background with warm tint
 *   - Backdrop dims smoothly; panel fades during brightness adjustment
 */

import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useLightMode } from '../hooks/useLightMode'
import type { ReactNode } from 'react'

interface SlidePanelProps {
  isOpen: boolean
  onClose: () => void
  direction: 'left' | 'right' | 'bottom'
  children: ReactNode
}

const variants = {
  left:   { hidden: { x: '-100%' }, visible: { x: 0 } },
  right:  { hidden: { x: '100%' },  visible: { x: 0 } },
  bottom: { hidden: { y: '100%' },  visible: { y: 0 } },
}

function DragHandle({ direction, isLight }: { direction: 'left' | 'right' | 'bottom'; isLight: boolean }) {
  const isBottom = direction === 'bottom'

  return (
    <div style={{
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      padding: isBottom ? '14px 0 6px' : '0 6px 0 14px',
      ...(isBottom ? {} : {
        position: 'absolute' as const,
        top: 0,
        bottom: 0,
        [direction === 'left' ? 'right' : 'left']: 0,
        width: 24,
        flexDirection: 'column' as const,
      }),
    }}>
      <motion.div
        animate={{
          opacity: [0.25, 0.45, 0.25],
          scaleX: isBottom ? [0.85, 1, 0.85] : [1, 1, 1],
          scaleY: isBottom ? [1, 1, 1] : [0.85, 1, 0.85],
        }}
        transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
        style={{
          width: isBottom ? 44 : 4,
          height: isBottom ? 4 : 44,
          borderRadius: 3,
          background: isLight
            ? 'rgba(0,0,0,0.15)'
            : 'rgba(var(--personality-accent-rgb), 0.5)',
        }}
      />
    </div>
  )
}

/** Personality-colored glow along the opening edge */
function EdgeGlow({ direction, isLight }: { direction: 'left' | 'right' | 'bottom'; isLight: boolean }) {
  if (isLight) return null

  const isBottom = direction === 'bottom'
  const gradientDir = isBottom ? 'to bottom' : direction === 'left' ? 'to right' : 'to left'

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.6, delay: 0.1 }}
      style={{
        position: 'absolute',
        pointerEvents: 'none',
        zIndex: 1,
        ...(isBottom
          ? { top: 0, left: 0, right: 0, height: 2 }
          : {
              top: 0,
              bottom: 0,
              [direction === 'left' ? 'right' : 'left']: 0,
              width: 2,
            }),
        background: `linear-gradient(${gradientDir}, rgba(var(--personality-accent-rgb), 0.6), transparent)`,
        boxShadow: '0 0 20px rgba(var(--personality-accent-rgb), 0.15), 0 0 60px rgba(var(--personality-accent-rgb), 0.08)',
      }}
    />
  )
}

export default function SlidePanel({ isOpen, onClose, direction, children }: SlidePanelProps) {
  const isBottom = direction === 'bottom'
  const isLight = useLightMode()

  // Listen for brightness adjustment — panel becomes semi-transparent
  const [panelOpacity, setPanelOpacity] = useState(1)
  useEffect(() => {
    const check = () => {
      const val = getComputedStyle(document.documentElement)
        .getPropertyValue('--panel-adjusting-opacity').trim()
      setPanelOpacity(val ? parseFloat(val) : 1)
    }
    const id = setInterval(check, 100)
    return () => clearInterval(id)
  }, [])

  const panelStyle: React.CSSProperties = {
    position: 'fixed',
    zIndex: 200,
    backdropFilter: 'blur(28px) saturate(1.3)',
    WebkitBackdropFilter: 'blur(28px) saturate(1.3)',
    background: isLight
      ? 'rgba(248, 244, 240, 0.94)'
      : 'rgba(16, 14, 22, 0.88)',
    borderColor: 'transparent',
    borderStyle: 'solid',
    borderWidth: 0,
    transition: 'background 0.6s ease',
    overflowY: 'auto',
    overflowX: 'hidden',
    ...(isBottom
      ? {
          bottom: 0, left: 0, right: 0,
          height: '70%',
          borderRadius: '24px 24px 0 0',
        }
      : {
          top: 0,
          bottom: 0,
          [direction]: 0,
          width: 'min(60%, 100%)',
          borderRadius: direction === 'left' ? '0 24px 24px 0' : '24px 0 0 24px',
        }),
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: panelOpacity < 1 ? panelOpacity * 0.3 : 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
            onClick={onClose}
            style={{
              position: 'fixed', inset: 0,
              background: isLight ? 'rgba(0,0,0,0.12)' : 'rgba(0,0,0,0.45)',
              zIndex: 199,
            }}
          />

          {/* Panel */}
          <motion.div
            key="panel"
            data-panel="true"
            initial={variants[direction].hidden}
            animate={{ ...variants[direction].visible, opacity: panelOpacity }}
            exit={variants[direction].hidden}
            transition={{
              type: 'spring',
              stiffness: 260,
              damping: 30,
              mass: 0.8,
            }}
            style={panelStyle}
          >
            {/* Personality edge glow */}
            <EdgeGlow direction={direction} isLight={isLight} />

            {/* Organic drag handle */}
            <DragHandle direction={direction} isLight={isLight} />

            {children}
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
