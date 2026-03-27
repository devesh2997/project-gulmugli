/**
 * BrightnessControl — quick ambient brightness override.
 *
 * A small sun icon (top-left) that expands into a horizontal slider when tapped.
 * Controls --ui-brightness-override CSS variable (0-100).
 * -1 = auto (follow time-of-day). 0 = darkest (night). 100 = brightest (afternoon).
 *
 * The slider auto-hides after 4 seconds of no interaction.
 * Tap the sun icon again or the "AUTO" label to reset to automatic.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

export function BrightnessControl() {
  const [expanded, setExpanded] = useState(false)
  const [value, setValue] = useState(-1) // -1 = auto
  const hideTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const trackRef = useRef<HTMLDivElement>(null)

  const isAuto = value < 0

  const scheduleHide = useCallback(() => {
    if (hideTimer.current) clearTimeout(hideTimer.current)
    hideTimer.current = setTimeout(() => setExpanded(false), 4000)
  }, [])

  useEffect(() => {
    return () => { if (hideTimer.current) clearTimeout(hideTimer.current) }
  }, [])

  const applyValue = useCallback((v: number) => {
    setValue(v)
    document.documentElement.style.setProperty('--ui-brightness-override', String(v))
    // Trigger the time-of-day hook to re-evaluate
    window.dispatchEvent(new CustomEvent('time-sim-change'))
    scheduleHide()
  }, [scheduleHide])

  const handleToggle = () => {
    if (expanded) {
      // Reset to auto
      applyValue(-1)
      setExpanded(false)
    } else {
      setExpanded(true)
      scheduleHide()
    }
  }

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

  // Sun icon — larger when bright, smaller when dark
  const sunScale = isAuto ? 1 : 0.7 + (value / 100) * 0.6
  const displayValue = isAuto ? 'AUTO' : `${value}%`

  return (
    <div
      data-gesture-ignore="true"
      style={{
        position: 'fixed',
        top: 16,
        left: 16,
        zIndex: 30,
        display: 'flex',
        alignItems: 'center',
        gap: 8,
      }}
    >
      {/* Sun icon button */}
      <motion.button
        onClick={handleToggle}
        whileHover={{ scale: 1.1 }}
        whileTap={{ scale: 0.9 }}
        animate={{ scale: sunScale }}
        style={{
          width: 32, height: 32, borderRadius: 16,
          background: isAuto
            ? 'rgba(255, 255, 255, 0.06)'
            : `rgba(var(--personality-accent-rgb), ${0.1 + (value / 100) * 0.15})`,
          border: `1px solid ${isAuto
            ? 'rgba(255, 255, 255, 0.08)'
            : 'rgba(var(--personality-accent-rgb), 0.2)'}`,
          cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          flexShrink: 0,
          boxShadow: isAuto ? 'none' : `0 0 ${8 + value * 0.12}px rgba(var(--personality-accent-rgb), ${0.1 + (value / 100) * 0.2})`,
          transition: 'box-shadow 0.3s',
        }}
      >
        <svg width="16" height="16" viewBox="0 0 24 24"
          fill="none"
          stroke={isAuto ? 'rgba(255,255,255,0.3)' : 'var(--personality-accent)'}
          strokeWidth="2" strokeLinecap="round"
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
      </motion.button>

      {/* Expandable slider */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: 140, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: 'easeOut' }}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              overflow: 'hidden',
            }}
          >
            {/* Track */}
            <div
              ref={trackRef}
              onPointerDown={handlePointerDown}
              style={{
                flex: 1,
                height: 6,
                borderRadius: 3,
                background: 'rgba(255,255,255,0.08)',
                cursor: 'pointer',
                position: 'relative',
                touchAction: 'none',
              }}
            >
              {/* Fill */}
              <motion.div
                style={{
                  height: '100%',
                  borderRadius: 3,
                  background: `linear-gradient(90deg, rgba(var(--personality-accent-rgb), 0.3), var(--personality-accent))`,
                  width: `${isAuto ? 50 : value}%`,
                }}
                transition={{ type: 'spring', stiffness: 300, damping: 30 }}
              />
              {/* Thumb */}
              <motion.div
                style={{
                  position: 'absolute',
                  top: '50%',
                  left: `${isAuto ? 50 : value}%`,
                  transform: 'translate(-50%, -50%)',
                  width: 14, height: 14, borderRadius: 7,
                  background: 'var(--personality-accent)',
                  boxShadow: '0 0 6px rgba(var(--personality-accent-rgb), 0.4)',
                  border: '2px solid rgba(0,0,0,0.2)',
                }}
              />
            </div>

            {/* Value label / Auto reset button */}
            <motion.button
              onClick={() => { applyValue(-1); setExpanded(false) }}
              whileTap={{ scale: 0.9 }}
              style={{
                fontSize: 9,
                fontWeight: 700,
                letterSpacing: '0.05em',
                color: isAuto ? 'rgba(255,255,255,0.3)' : 'var(--personality-accent)',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                whiteSpace: 'nowrap',
                minWidth: 32,
                textAlign: 'center',
                padding: '2px 4px',
                borderRadius: 4,
              }}
            >
              {displayValue}
            </motion.button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
