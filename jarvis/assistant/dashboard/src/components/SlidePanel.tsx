/**
 * Generic sliding overlay panel.
 *
 * Slides in from a specified edge with frosted glass styling.
 * Small drag handle bar at the top/side for visual affordance.
 * Click outside to dismiss.
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

function DragHandle({ direction }: { direction: 'left' | 'right' | 'bottom' }) {
  const isBottom = direction === 'bottom'
  return (
    <div style={{
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      padding: isBottom ? '12px 0 4px' : '0 4px 0 12px',
      ...(isBottom ? {} : {
        position: 'absolute' as const,
        top: 0,
        bottom: 0,
        [direction === 'left' ? 'right' : 'left']: 0,
        width: 20,
        flexDirection: 'column' as const,
      }),
    }}>
      <div style={{
        width: isBottom ? 40 : 4,
        height: isBottom ? 4 : 40,
        borderRadius: 2,
        background: 'rgba(255,255,255,0.2)',
      }} />
    </div>
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
    backdropFilter: 'blur(24px)',
    WebkitBackdropFilter: 'blur(24px)',
    background: isLight ? 'rgba(245, 240, 235, 0.92)' : 'rgba(20, 18, 25, 0.85)',
    border: isLight ? '1px solid rgba(0,0,0,0.06)' : '1px solid rgba(255,255,255,0.08)',
    transition: 'background 0.6s ease, border 0.6s ease',
    overflowY: 'auto',
    ...(isBottom
      ? { bottom: 0, left: 0, right: 0, height: '70%', borderRadius: '16px 16px 0 0' }
      : {
          top: 0,
          bottom: 0,
          [direction]: 0,
          width: 'min(60%, 100%)',
          borderRadius: direction === 'left' ? '0 16px 16px 0' : '16px 0 0 16px',
        }),
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop — fades during brightness adjustment */}
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: panelOpacity < 1 ? panelOpacity * 0.3 : 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={onClose}
            style={{
              position: 'fixed', inset: 0,
              background: isLight ? 'rgba(0,0,0,0.15)' : 'rgba(0,0,0,0.4)',
              zIndex: 199,
            }}
          />

          {/* Panel — becomes semi-transparent during brightness adjustment */}
          <motion.div
            key="panel"
            data-panel="true"
            initial={variants[direction].hidden}
            animate={{ ...variants[direction].visible, opacity: panelOpacity }}
            exit={variants[direction].hidden}
            transition={{ type: 'spring', stiffness: 320, damping: 34 }}
            style={panelStyle}
          >
            <DragHandle direction={direction} />
            {children}
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
