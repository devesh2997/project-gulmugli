/**
 * StatusDot — tiny connection indicator.
 *
 * 6px circle positioned absolute top-right.
 * Color: --ui-status_dot-connected when connected, --ui-status_dot-disconnected otherwise.
 * Pulses gently via Framer Motion when connected.
 */

import { motion } from 'framer-motion'

interface StatusDotProps {
  connected: boolean
}

export function StatusDot({ connected }: StatusDotProps) {
  return (
    <motion.div
      title={connected ? 'Connected' : 'Disconnected'}
      animate={
        connected
          ? { opacity: [0.6, 1, 0.6], scale: [0.9, 1.05, 0.9] }
          : { opacity: 1, scale: 1 }
      }
      transition={
        connected
          ? { duration: 2.5, repeat: Infinity, ease: 'easeInOut' }
          : {}
      }
      style={{
        position: 'absolute',
        top: 8,
        right: 8,
        width:  'var(--ui-status_dot-size)',
        height: 'var(--ui-status_dot-size)',
        borderRadius: '50%',
        background: connected
          ? 'var(--ui-status_dot-connected)'
          : 'var(--ui-status_dot-disconnected)',
      }}
    />
  )
}
