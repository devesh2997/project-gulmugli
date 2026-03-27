/**
 * StatusDot — connection indicator with visible pulse ring and hover label.
 *
 * Features:
 *   - Pulsing outer ring that radiates from the dot when connected
 *   - On hover/tap, a small label slides in showing connection state
 *   - Uses personality accent when connected, muted red when disconnected
 *   - More visible than a simple 6px dot
 */

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useLightMode } from '../hooks/useLightMode'

interface StatusDotProps {
  connected: boolean
}

export function StatusDot({ connected }: StatusDotProps) {
  const isLight = useLightMode()
  const [hovered, setHovered] = useState(false)

  const dotSize = 'var(--ui-status_dot-size)'
  const connectedColor = 'var(--ui-status_dot-connected)'
  const disconnectedColor = 'var(--ui-status_dot-disconnected)'
  const color = connected ? connectedColor : disconnectedColor

  return (
    <div
      onPointerEnter={() => setHovered(true)}
      onPointerLeave={() => setHovered(false)}
      onClick={() => setHovered(h => !h)}
      style={{
        position: 'absolute',
        top: 6,
        right: 6,
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        cursor: 'pointer',
        zIndex: 10,
      }}
    >
      {/* Label that appears on hover */}
      <AnimatePresence>
        {hovered && (
          <motion.span
            initial={{ opacity: 0, x: 6, scale: 0.9 }}
            animate={{ opacity: 1, x: 0, scale: 1 }}
            exit={{ opacity: 0, x: 6, scale: 0.9 }}
            transition={{ type: 'spring', stiffness: 400, damping: 25 }}
            style={{
              fontSize: 9,
              fontWeight: 600,
              letterSpacing: '0.06em',
              color: isLight ? 'rgba(0,0,0,0.5)' : 'rgba(255,255,255,0.5)',
              textTransform: 'uppercase',
              whiteSpace: 'nowrap',
              fontFamily: 'var(--font-mono)',
            }}
          >
            {connected ? 'Connected' : 'Offline'}
          </motion.span>
        )}
      </AnimatePresence>

      {/* Dot with pulse ring */}
      <div style={{ position: 'relative', width: dotSize, height: dotSize }}>
        {/* Pulse ring — only when connected */}
        {connected && (
          <motion.div
            animate={{
              scale: [1, 2.2, 1],
              opacity: [0.5, 0, 0.5],
            }}
            transition={{
              duration: 2.5,
              repeat: Infinity,
              ease: 'easeOut',
            }}
            style={{
              position: 'absolute',
              inset: 0,
              borderRadius: '50%',
              background: color,
            }}
          />
        )}

        {/* Core dot */}
        <motion.div
          animate={
            connected
              ? { opacity: [0.7, 1, 0.7], scale: [0.92, 1.08, 0.92] }
              : { opacity: 0.6, scale: 1 }
          }
          transition={
            connected
              ? { duration: 2.5, repeat: Infinity, ease: 'easeInOut' }
              : {}
          }
          style={{
            position: 'absolute',
            inset: 0,
            borderRadius: '50%',
            background: color,
            boxShadow: isLight
              ? `0 0 0 1.5px rgba(0,0,0,0.1), 0 0 6px ${connected ? 'rgba(var(--personality-accent-rgb), 0.3)' : 'rgba(255,80,80,0.2)'}`
              : `0 0 8px ${connected ? 'rgba(var(--personality-accent-rgb), 0.4)' : 'rgba(255,80,80,0.3)'}`,
            transition: 'box-shadow 0.6s ease',
          }}
        />
      </div>
    </div>
  )
}
