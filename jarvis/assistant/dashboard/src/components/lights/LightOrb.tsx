/**
 * LightOrb — stylized desk lamp / room silhouette for light control.
 *
 * When on: the lamp shade fills with the current color at current brightness,
 * with a warm glow cone beneath. When off: dim outline only.
 * Tapping toggles on/off with a smooth "light fills" animation.
 */

import { motion } from 'framer-motion'

interface Props {
  on: boolean
  color: string
  brightness: number
  onToggle: () => void
}

export function LightOrb({ on, color, brightness, onToggle }: Props) {
  const fillOpacity = on ? Math.max(0.3, brightness / 100) : 0
  const glowOpacity = on ? Math.max(0.1, (brightness / 100) * 0.5) : 0

  return (
    <div style={{ display: 'flex', justifyContent: 'center', padding: '8px 0' }}>
      <motion.button
        onClick={onToggle}
        whileHover={{ scale: 1.04 }}
        whileTap={{ scale: 0.96 }}
        style={{
          width: 140, height: 140,
          background: 'transparent',
          border: 'none', cursor: 'pointer',
          position: 'relative',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}
      >
        <svg width="140" height="140" viewBox="0 0 140 140" fill="none">
          {/* Light cone / glow below shade */}
          <motion.path
            d="M48 58 L32 120 L108 120 L92 58 Z"
            animate={{
              fill: on ? color : 'transparent',
              fillOpacity: glowOpacity,
            }}
            transition={{ type: 'spring', stiffness: 200, damping: 25 }}
          />

          {/* Outer glow halo when on */}
          <motion.ellipse
            cx="70" cy="90" rx="50" ry="30"
            animate={{
              fill: on ? color : 'transparent',
              fillOpacity: on ? glowOpacity * 0.4 : 0,
            }}
            transition={{ type: 'spring', stiffness: 200, damping: 25 }}
            style={{ filter: 'blur(8px)' }}
          />

          {/* Lamp shade */}
          <motion.path
            d="M45 56 L50 28 L90 28 L95 56 Z"
            animate={{
              fill: on ? color : 'rgba(255,255,255,0.03)',
              fillOpacity: on ? fillOpacity : 1,
              stroke: on ? color : 'rgba(255,255,255,0.12)',
            }}
            transition={{ type: 'spring', stiffness: 200, damping: 25 }}
            strokeWidth="1.5"
            strokeLinejoin="round"
          />

          {/* Shade rim */}
          <motion.line
            x1="43" y1="57" x2="97" y2="57"
            animate={{
              stroke: on ? color : 'rgba(255,255,255,0.15)',
            }}
            transition={{ duration: 0.3 }}
            strokeWidth="2"
            strokeLinecap="round"
          />

          {/* Lamp neck */}
          <motion.rect
            x="66" y="57" width="8" height="22" rx="2"
            animate={{
              fill: on ? 'rgba(255,255,255,0.15)' : 'rgba(255,255,255,0.06)',
            }}
            transition={{ duration: 0.3 }}
          />

          {/* Lamp base */}
          <motion.ellipse
            cx="70" cy="82" rx="18" ry="4"
            animate={{
              fill: on ? 'rgba(255,255,255,0.12)' : 'rgba(255,255,255,0.06)',
              stroke: on ? 'rgba(255,255,255,0.15)' : 'rgba(255,255,255,0.08)',
            }}
            transition={{ duration: 0.3 }}
            strokeWidth="1"
          />

          {/* Table / surface line */}
          <motion.line
            x1="25" y1="120" x2="115" y2="120"
            animate={{
              stroke: on ? `${color}33` : 'rgba(255,255,255,0.06)',
            }}
            transition={{ duration: 0.3 }}
            strokeWidth="1"
            strokeLinecap="round"
          />

          {/* Small items on the table for context */}
          {/* Book */}
          <motion.rect
            x="100" y="114" width="10" height="5" rx="1"
            animate={{
              fill: on ? `${color}22` : 'rgba(255,255,255,0.03)',
              stroke: on ? `${color}33` : 'rgba(255,255,255,0.06)',
            }}
            transition={{ duration: 0.3 }}
            strokeWidth="0.5"
          />

          {/* Cup */}
          <motion.path
            d="M32 113 L32 119 L38 119 L38 113 Z"
            animate={{
              fill: on ? `${color}18` : 'rgba(255,255,255,0.02)',
              stroke: on ? `${color}28` : 'rgba(255,255,255,0.05)',
            }}
            transition={{ duration: 0.3 }}
            strokeWidth="0.5"
          />
        </svg>

        {/* Animated outer glow */}
        <motion.div
          animate={{
            boxShadow: on
              ? `0 20px 60px ${color}30, 0 0 100px ${color}15`
              : '0 0 0px transparent',
          }}
          transition={{ type: 'spring', stiffness: 200, damping: 25 }}
          style={{
            position: 'absolute', inset: 0, borderRadius: 20,
            pointerEvents: 'none',
          }}
        />
      </motion.button>
    </div>
  )
}
