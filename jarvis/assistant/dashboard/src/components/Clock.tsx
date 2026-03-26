/**
 * Clock — displays current time (HH:MM) and day name.
 *
 * Updates every second via setInterval.
 * Color uses --personality-accent at 40% opacity.
 * Font size is driven by the `size` prop, mapped to layout tokens.
 */

import { useEffect, useState } from 'react'

const DAY_NAMES = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

// Clamp values taken directly from layout.json clock_size tokens.
const SIZE_MAP = {
  compact: 'var(--layout-clock_size-compact)',
  medium:  'var(--layout-clock_size-medium)',
  large:   'var(--layout-clock_size-large)',
}

interface ClockProps {
  size?: 'compact' | 'medium' | 'large'
}

export function Clock({ size = 'large' }: ClockProps) {
  const [now, setNow] = useState(() => new Date())

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(id)
  }, [])

  const hours   = String(now.getHours()).padStart(2, '0')
  const minutes = String(now.getMinutes()).padStart(2, '0')
  const dayName = DAY_NAMES[now.getDay()]

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: '0.2em',
        color: 'var(--personality-accent)',
        opacity: 0.4,
      }}
    >
      <span
        style={{
          fontSize: SIZE_MAP[size],
          fontWeight: 200,
          letterSpacing: '0.04em',
          lineHeight: 1,
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        {hours}:{minutes}
      </span>
      <span
        style={{
          fontSize: `calc(${SIZE_MAP[size]} * 0.3)`,
          textTransform: 'uppercase',
          letterSpacing: '0.2em',
          fontWeight: 400,
        }}
      >
        {dayName}
      </span>
    </div>
  )
}
