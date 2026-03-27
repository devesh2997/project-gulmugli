/**
 * Clock — custom time display with animated digit transitions.
 *
 * Features:
 *   - Individual digit slots with smooth vertical slide on change
 *   - Personality-colored colon separator with gentle breathing pulse
 *   - Monospace font for perfect digit alignment
 *   - Day name rendered in spaced-out small caps
 *   - Integrates visually with the avatar above it
 */

import { useEffect, useState, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useLightMode } from '../hooks/useLightMode'

const DAY_NAMES = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

const SIZE_MAP = {
  compact: 'var(--layout-clock_size-compact)',
  medium:  'var(--layout-clock_size-medium)',
  large:   'var(--layout-clock_size-large)',
}

interface ClockProps {
  size?: 'compact' | 'medium' | 'large'
}

/** Single digit that slides up when changing */
function AnimatedDigit({ digit, fontSize }: { digit: string; fontSize: string }) {
  const prevDigit = useRef(digit)
  const changed = prevDigit.current !== digit
  prevDigit.current = digit

  return (
    <span
      style={{
        display: 'inline-block',
        width: '0.62em',
        textAlign: 'center',
        overflow: 'hidden',
        position: 'relative',
        height: '1.1em',
        verticalAlign: 'top',
        fontSize,
      }}
    >
      <AnimatePresence mode="popLayout" initial={false}>
        <motion.span
          key={digit}
          initial={changed ? { y: '0.5em', opacity: 0, filter: 'blur(2px)' } : false}
          animate={{ y: 0, opacity: 1, filter: 'blur(0px)' }}
          exit={{ y: '-0.5em', opacity: 0, filter: 'blur(2px)' }}
          transition={{ duration: 0.35, ease: [0.23, 1, 0.32, 1] }}
          style={{
            display: 'block',
            lineHeight: '1.1em',
          }}
        >
          {digit}
        </motion.span>
      </AnimatePresence>
    </span>
  )
}

export function Clock({ size = 'large' }: ClockProps) {
  const [now, setNow] = useState(() => new Date())
  const isLight = useLightMode()

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(id)
  }, [])

  const hours   = String(now.getHours()).padStart(2, '0')
  const minutes = String(now.getMinutes()).padStart(2, '0')
  const dayName = DAY_NAMES[now.getDay()]

  const fontSize = SIZE_MAP[size]
  const baseColor = isLight ? '#2a2018' : 'var(--personality-accent)'
  const baseOpacity = isLight ? 0.8 : 0.4

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: '0.15em',
        color: baseColor,
        opacity: baseOpacity,
        textShadow: isLight ? '0 1px 2px rgba(0,0,0,0.08)' : 'none',
        transition: 'color 0.6s ease, opacity 0.6s ease',
        fontFamily: 'var(--font-mono)',
      }}
    >
      {/* Time digits with animated transitions */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          fontWeight: 200,
          letterSpacing: '0.02em',
          lineHeight: 1,
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        <AnimatedDigit digit={hours[0]} fontSize={fontSize} />
        <AnimatedDigit digit={hours[1]} fontSize={fontSize} />

        {/* Pulsing colon separator in personality accent */}
        <motion.span
          animate={{
            opacity: [0.3, 0.9, 0.3],
          }}
          transition={{
            duration: 2,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
          style={{
            display: 'inline-flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: `calc(${fontSize} * 0.12)`,
            width: `calc(${fontSize} * 0.28)`,
            height: '1.1em',
            fontSize,
          }}
        >
          <span
            style={{
              width: `calc(${fontSize} * 0.06)`,
              height: `calc(${fontSize} * 0.06)`,
              borderRadius: '50%',
              background: isLight ? '#2a2018' : 'var(--personality-accent)',
            }}
          />
          <span
            style={{
              width: `calc(${fontSize} * 0.06)`,
              height: `calc(${fontSize} * 0.06)`,
              borderRadius: '50%',
              background: isLight ? '#2a2018' : 'var(--personality-accent)',
            }}
          />
        </motion.span>

        <AnimatedDigit digit={minutes[0]} fontSize={fontSize} />
        <AnimatedDigit digit={minutes[1]} fontSize={fontSize} />
      </div>

      {/* Thin breathing line under the clock */}
      <motion.div
        animate={{
          scaleX: [0.3, 0.6, 0.3],
          opacity: [0.15, 0.35, 0.15],
        }}
        transition={{
          duration: 4,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
        style={{
          width: `calc(${fontSize} * 1.5)`,
          height: 1,
          borderRadius: 1,
          background: isLight
            ? 'rgba(42, 32, 24, 0.3)'
            : 'var(--personality-accent)',
          marginTop: '0.1em',
          transformOrigin: 'center',
        }}
      />

      {/* Day name */}
      <span
        style={{
          fontSize: `calc(${fontSize} * 0.22)`,
          textTransform: 'uppercase',
          letterSpacing: '0.3em',
          fontWeight: 500,
          fontFamily: 'var(--font-sans)',
          marginTop: '0.15em',
        }}
      >
        {dayName}
      </span>
    </div>
  )
}
