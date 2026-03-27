/**
 * LightOrb — large glowing circle representing the current light state.
 *
 * Fill color matches lights.color, opacity tracks brightness.
 * When off: dark circle with faint outline. Tap to toggle.
 * Smooth color/opacity transitions via Framer Motion.
 */

import { motion } from 'framer-motion'

interface Props {
  on: boolean
  color: string
  brightness: number
  onToggle: () => void
}

export function LightOrb({ on, color, brightness, onToggle }: Props) {
  const opacity = on ? brightness / 100 : 0.08
  const displayColor = on ? color : 'rgba(255,255,255,0.15)'

  return (
    <div style={{ display: 'flex', justifyContent: 'center', padding: '8px 0' }}>
      <motion.button
        onClick={onToggle}
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        animate={{
          backgroundColor: on ? color : 'rgba(255,255,255,0.04)',
          opacity: on ? Math.max(0.3, opacity) : 1,
          boxShadow: on
            ? `0 0 40px ${color}4D, 0 0 80px ${color}1A`
            : '0 0 0px transparent',
        }}
        transition={{ type: 'spring', stiffness: 200, damping: 25 }}
        style={{
          width: 120, height: 120, borderRadius: 60,
          border: `2px solid ${on ? `${color}66` : 'rgba(255,255,255,0.1)'}`,
          cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}
      >
        {/* Power icon */}
        <svg
          width="28" height="28" viewBox="0 0 24 24"
          fill="none" stroke={on ? '#fff' : 'rgba(255,255,255,0.25)'}
          strokeWidth="2" strokeLinecap="round"
        >
          <path d="M12 2v6" />
          <path d="M16.24 7.76a6 6 0 1 1-8.49 0" />
        </svg>
      </motion.button>
    </div>
  )
}
