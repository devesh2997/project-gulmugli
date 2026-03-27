/**
 * BrightnessControl — ambient brightness override for the settings panel.
 *
 * An inline slider that controls --ui-brightness-override CSS variable (0-100).
 * -1 = auto (follow time-of-day). 0 = darkest (night). 100 = brightest (afternoon).
 *
 * Shows a sun icon that scales with the brightness level, a draggable slider,
 * and an AUTO reset button.
 */

import { useCallback, useRef, useState } from 'react'
import { motion } from 'framer-motion'

export function BrightnessControl() {
  const [value, setValue] = useState(-1) // -1 = auto
  const trackRef = useRef<HTMLDivElement>(null)

  const isAuto = value < 0
  const displayPct = isAuto ? 50 : value

  const applyValue = useCallback((v: number) => {
    setValue(v)
    document.documentElement.style.setProperty('--ui-brightness-override', String(v))
    window.dispatchEvent(new CustomEvent('time-sim-change'))
  }, [])

  const handlePointerDown = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    if (!trackRef.current) return
    e.stopPropagation()
    const target = e.currentTarget
    target.setPointerCapture(e.pointerId)

    const seek = (clientX: number) => {
      const r = trackRef.current!.getBoundingClientRect()
      const ratio = Math.max(0, Math.min(1, (clientX - r.left) / r.width))
      applyValue(Math.round(ratio * 100))
    }

    seek(e.clientX)

    const onMove = (ev: PointerEvent) => seek(ev.clientX)
    const onUp = () => {
      target.removeEventListener('pointermove', onMove)
      target.removeEventListener('pointerup', onUp)
    }
    target.addEventListener('pointermove', onMove)
    target.addEventListener('pointerup', onUp)
  }, [applyValue])

  return (
    <div data-gesture-ignore="true">
      {/* Label row */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        marginBottom: 12,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {/* Sun icon */}
          <svg width="14" height="14" viewBox="0 0 24 24"
            fill="none" stroke="var(--personality-accent)" strokeWidth="2" strokeLinecap="round"
            style={{ opacity: 0.6 }}
          >
            <circle cx="12" cy="12" r="5" />
            <line x1="12" y1="1" x2="12" y2="3" />
            <line x1="12" y1="21" x2="12" y2="23" />
            <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
            <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
            <line x1="1" y1="12" x2="3" y2="12" />
            <line x1="21" y1="12" x2="23" y2="12" />
            <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
            <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
          </svg>
          <span style={{
            fontSize: 13, fontWeight: 500,
            color: 'rgba(255,255,255,0.8)',
          }}>
            Ambient Brightness
          </span>
        </div>

        {/* Auto/value badge */}
        <motion.button
          onClick={() => applyValue(-1)}
          whileTap={{ scale: 0.9 }}
          style={{
            fontSize: 10, fontWeight: 700,
            letterSpacing: '0.05em',
            color: isAuto ? 'rgba(255,255,255,0.3)' : 'var(--personality-accent)',
            background: isAuto
              ? 'rgba(255,255,255,0.05)'
              : 'rgba(var(--personality-accent-rgb), 0.12)',
            border: `1px solid ${isAuto
              ? 'rgba(255,255,255,0.06)'
              : 'rgba(var(--personality-accent-rgb), 0.2)'}`,
            borderRadius: 10,
            padding: '3px 8px',
            cursor: 'pointer',
          }}
        >
          {isAuto ? 'AUTO' : `${value}%`}
        </motion.button>
      </div>

      {/* Slider with sun icons */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        {/* Moon/dark icon */}
        <svg width="12" height="12" viewBox="0 0 24 24"
          fill="none" stroke="rgba(255,255,255,0.25)" strokeWidth="2" strokeLinecap="round"
          style={{ flexShrink: 0 }}
        >
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
        </svg>

        {/* Track */}
        <div
          ref={trackRef}
          onPointerDown={handlePointerDown}
          style={{
            flex: 1, height: 8, borderRadius: 4,
            background: 'rgba(255,255,255,0.06)',
            cursor: 'pointer',
            position: 'relative',
            touchAction: 'none',
          }}
        >
          {/* Gradient fill */}
          <motion.div
            animate={{ width: `${displayPct}%` }}
            transition={{ type: 'spring', stiffness: 300, damping: 30 }}
            style={{
              height: '100%', borderRadius: 4,
              background: `linear-gradient(90deg, rgba(var(--personality-accent-rgb), 0.2), var(--personality-accent))`,
            }}
          />
          {/* Thumb */}
          <motion.div
            animate={{ left: `${displayPct}%` }}
            transition={{ type: 'spring', stiffness: 300, damping: 30 }}
            style={{
              position: 'absolute', top: '50%',
              transform: 'translate(-50%, -50%)',
              width: 18, height: 18, borderRadius: 9,
              background: 'var(--personality-accent)',
              boxShadow: '0 0 8px rgba(var(--personality-accent-rgb), 0.4)',
              border: '2px solid rgba(0,0,0,0.15)',
            }}
          />
        </div>

        {/* Sun/bright icon */}
        <svg width="14" height="14" viewBox="0 0 24 24"
          fill="none" stroke="rgba(255,255,255,0.35)" strokeWidth="2" strokeLinecap="round"
          style={{ flexShrink: 0 }}
        >
          <circle cx="12" cy="12" r="5" />
          <line x1="12" y1="1" x2="12" y2="3" />
          <line x1="12" y1="21" x2="12" y2="23" />
          <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
          <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
          <line x1="1" y1="12" x2="3" y2="12" />
          <line x1="21" y1="12" x2="23" y2="12" />
          <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
          <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
        </svg>
      </div>

      {/* Description */}
      <div style={{
        fontSize: 11, color: 'rgba(255,255,255,0.3)', marginTop: 8,
      }}>
        {isAuto
          ? 'Follows time of day automatically'
          : 'Manual override — tap AUTO to reset'}
      </div>
    </div>
  )
}
