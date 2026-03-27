/**
 * VolumeControl — arc-shaped rotary dial for system volume.
 *
 * Draws a 240-degree SVG arc that fills with personality accent color
 * as volume increases. The arc has a glowing knob that follows the
 * current position, and the center shows a volume icon that morphs
 * between muted/quiet/loud states. Drag anywhere on the arc to adjust.
 *
 * This is NOT a slider — it's a radial dial that feels like turning
 * a physical volume knob on a premium speaker.
 */

import { useRef, useCallback } from 'react'
import { motion } from 'framer-motion'

interface Props {
  volume: number
  onChange: (vol: number) => void
}

// Arc geometry: 240-degree sweep starting from bottom-left
const CX = 80
const CY = 80
const R = 62
const ARC_START_DEG = 150  // bottom-left
const ARC_END_DEG = 390    // bottom-right (150 + 240)
const ARC_SWEEP = ARC_END_DEG - ARC_START_DEG

function degToRad(deg: number) { return (deg * Math.PI) / 180 }

function polarToCart(cx: number, cy: number, r: number, deg: number) {
  const rad = degToRad(deg)
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) }
}

function describeArc(cx: number, cy: number, r: number, startDeg: number, endDeg: number) {
  const start = polarToCart(cx, cy, r, startDeg)
  const end = polarToCart(cx, cy, r, endDeg)
  const sweep = endDeg - startDeg
  const largeArc = sweep > 180 ? 1 : 0
  return `M ${start.x} ${start.y} A ${r} ${r} 0 ${largeArc} 1 ${end.x} ${end.y}`
}

/** Volume icon that morphs based on level */
function VolumeIcon({ volume }: { volume: number }) {
  const muted = volume === 0
  const quiet = volume > 0 && volume <= 33
  const medium = volume > 33 && volume <= 66

  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none"
      stroke="var(--text-secondary)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"
    >
      <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
      {muted && <line x1="22" y1="9" x2="16" y2="15" />}
      {muted && <line x1="16" y1="9" x2="22" y2="15" />}
      {!muted && <path d="M15.54 8.46a5 5 0 0 1 0 7.07" opacity={quiet ? 0.3 : 1} />}
      {!muted && !quiet && <path d="M19.07 4.93a10 10 0 0 1 0 14.14" opacity={medium ? 0.4 : 1} />}
    </svg>
  )
}

export function VolumeControl({ volume, onChange }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const draggingRef = useRef(false)

  // Convert pointer position to volume (0-100)
  const pointerToVolume = useCallback((clientX: number, clientY: number) => {
    if (!containerRef.current) return volume
    const rect = containerRef.current.getBoundingClientRect()
    const cx = rect.left + rect.width / 2
    const cy = rect.top + rect.height / 2
    const dx = clientX - cx
    const dy = clientY - cy
    let angle = Math.atan2(dy, dx) * (180 / Math.PI) // -180 to 180
    if (angle < 0) angle += 360 // 0 to 360

    // Map angle to volume: our arc goes 150 -> 390 (wrapping past 360)
    // Normalize: if angle < ARC_START_DEG, add 360 to handle wrap
    let adjustedAngle = angle
    if (adjustedAngle < ARC_START_DEG - 30) adjustedAngle += 360

    const ratio = (adjustedAngle - ARC_START_DEG) / ARC_SWEEP
    return Math.round(Math.max(0, Math.min(100, ratio * 100)))
  }, [volume])

  const handlePointerDown = useCallback((e: React.PointerEvent) => {
    draggingRef.current = true
    ;(e.target as HTMLElement).setPointerCapture?.(e.pointerId)
    onChange(pointerToVolume(e.clientX, e.clientY))
  }, [pointerToVolume, onChange])

  const handlePointerMove = useCallback((e: React.PointerEvent) => {
    if (!draggingRef.current) return
    onChange(pointerToVolume(e.clientX, e.clientY))
  }, [pointerToVolume, onChange])

  const handlePointerUp = useCallback(() => {
    draggingRef.current = false
  }, [])

  // Current knob position
  const knobDeg = ARC_START_DEG + (volume / 100) * ARC_SWEEP
  const knob = polarToCart(CX, CY, R, knobDeg)

  // Filled arc path
  const filledEndDeg = ARC_START_DEG + (volume / 100) * ARC_SWEEP
  const filledPath = volume > 0.5
    ? describeArc(CX, CY, R, ARC_START_DEG, filledEndDeg)
    : ''

  // Track arc path (full 240 degrees)
  const trackPath = describeArc(CX, CY, R, ARC_START_DEG, ARC_END_DEG)

  return (
    <div
      ref={containerRef}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      style={{
        width: 160, height: 140, margin: '0 auto',
        cursor: 'pointer', touchAction: 'none',
        position: 'relative',
        userSelect: 'none',
      }}
    >
      <svg width="160" height="140" viewBox="0 0 160 140">
        <defs>
          {/* Glow filter for the filled arc */}
          <filter id="vol-glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="4" />
          </filter>
        </defs>

        {/* Background track — subtle, always visible */}
        <path
          d={trackPath}
          fill="none"
          stroke="var(--surface-subtle)"
          strokeWidth="6"
          strokeLinecap="round"
          opacity="0.5"
        />

        {/* Filled arc — personality colored */}
        {filledPath && (
          <>
            {/* Glow layer */}
            <motion.path
              d={filledPath}
              fill="none"
              stroke="var(--personality-accent)"
              strokeWidth="8"
              strokeLinecap="round"
              filter="url(#vol-glow)"
              animate={{ opacity: 0.4 }}
              transition={{ duration: 0.2 }}
            />
            {/* Solid fill layer */}
            <motion.path
              d={filledPath}
              fill="none"
              stroke="var(--personality-accent)"
              strokeWidth="5"
              strokeLinecap="round"
              initial={false}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.15 }}
            />
          </>
        )}

        {/* Knob — glowing orb at current position */}
        <motion.circle
          cx={knob.x}
          cy={knob.y}
          r="9"
          fill="var(--personality-accent)"
          animate={{
            filter: `drop-shadow(0 0 6px var(--personality-accent))`,
          }}
          transition={{ type: 'spring', stiffness: 300, damping: 25 }}
        />
        <circle
          cx={knob.x}
          cy={knob.y}
          r="4"
          fill="var(--bg-primary, #0e0c14)"
        />
      </svg>

      {/* Center content — icon + value */}
      <div style={{
        position: 'absolute',
        top: '46%', left: '50%',
        transform: 'translate(-50%, -50%)',
        display: 'flex', flexDirection: 'column',
        alignItems: 'center', gap: 4,
        pointerEvents: 'none',
      }}>
        <VolumeIcon volume={volume} />
        <motion.span
          key={volume}
          initial={{ scale: 1.15, opacity: 0.7 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ type: 'spring', stiffness: 400, damping: 20 }}
          style={{
            fontSize: 22, fontWeight: 600,
            color: 'var(--text-primary)',
            fontVariantNumeric: 'tabular-nums',
            letterSpacing: -0.5,
          }}
        >
          {volume}
        </motion.span>
      </div>
    </div>
  )
}
