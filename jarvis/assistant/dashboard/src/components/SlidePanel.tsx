/**
 * Generic sliding overlay panel.
 *
 * Slides in from a specified edge with glassmorphism styling.
 * Click outside to dismiss.
 */

import { motion, AnimatePresence } from 'framer-motion'
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

export default function SlidePanel({ isOpen, onClose, direction, children }: SlidePanelProps) {
  const isBottom = direction === 'bottom'

  const panelStyle: React.CSSProperties = {
    position: 'fixed',
    zIndex: 200,
    backdropFilter: 'blur(20px)',
    WebkitBackdropFilter: 'blur(20px)',
    background: 'rgba(10, 10, 18, 0.85)',
    border: '1px solid rgba(255,255,255,0.08)',
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
          {/* Backdrop */}
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={onClose}
            style={{
              position: 'fixed', inset: 0,
              background: 'rgba(0,0,0,0.4)',
              zIndex: 199,
            }}
          />

          {/* Panel */}
          <motion.div
            key="panel"
            initial={variants[direction].hidden}
            animate={variants[direction].visible}
            exit={variants[direction].hidden}
            transition={{ type: 'spring', stiffness: 320, damping: 34 }}
            style={panelStyle}
          >
            {children}
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
