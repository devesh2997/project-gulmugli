/**
 * AppearanceSection -- creative brightness + background mode controls.
 *
 * Brightness uses a radial glow that you drag to expand/contract.
 * Background mode shows live mini-previews you tap, not pill buttons.
 * Time-of-day preview shows how the theme looks at different hours.
 */

import { useCallback, useRef, useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

/* ------------------------------------------------------------------ */
/*  Radial Brightness                                                  */
/* ------------------------------------------------------------------ */

function RadialBrightness({ onAdjusting }: { onAdjusting?: (v: boolean) => void }) {
  const [value, setValue] = useState(-1) // -1 = auto
  const containerRef = useRef<HTMLDivElement>(null)
  const draggingRef = useRef(false)

  const isAuto = value < 0
  const displayPct = isAuto ? 50 : value

  const applyValue = useCallback((v: number) => {
    setValue(v)
    document.documentElement.style.setProperty('--ui-brightness-override', String(v))
    window.dispatchEvent(new CustomEvent('time-sim-change'))
  }, [])

  // Map pointer distance from center to brightness 0-100
  const computeFromPointer = useCallback((clientX: number, clientY: number) => {
    if (!containerRef.current) return 50
    const rect = containerRef.current.getBoundingClientRect()
    const cx = rect.left + rect.width / 2
    const cy = rect.top + rect.height / 2
    const maxR = rect.width / 2
    const dist = Math.sqrt((clientX - cx) ** 2 + (clientY - cy) ** 2)
    return Math.round(Math.max(0, Math.min(100, (dist / maxR) * 100)))
  }, [])

  const handlePointerDown = useCallback((e: React.PointerEvent) => {
    e.stopPropagation()
    draggingRef.current = true
    ;(e.target as HTMLElement).setPointerCapture(e.pointerId)
    onAdjusting?.(true)
    document.documentElement.style.setProperty('--panel-adjusting-opacity', '0.3')
    applyValue(computeFromPointer(e.clientX, e.clientY))
  }, [applyValue, computeFromPointer, onAdjusting])

  const handlePointerMove = useCallback((e: React.PointerEvent) => {
    if (!draggingRef.current) return
    applyValue(computeFromPointer(e.clientX, e.clientY))
  }, [applyValue, computeFromPointer])

  const handlePointerUp = useCallback(() => {
    draggingRef.current = false
    onAdjusting?.(false)
    document.documentElement.style.setProperty('--panel-adjusting-opacity', '1')
  }, [onAdjusting])

  // The glow radius scales with brightness
  const glowRadius = 20 + (displayPct / 100) * 60 // 20% to 80%

  return (
    <div data-gesture-ignore="true" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16 }}>
      {/* Radial glow orb -- drag to resize */}
      <div
        ref={containerRef}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        style={{
          width: 160, height: 160,
          borderRadius: '50%',
          position: 'relative',
          cursor: 'pointer',
          touchAction: 'none',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        {/* Outer ring -- subtle guide */}
        <div style={{
          position: 'absolute', inset: 0,
          borderRadius: '50%',
          border: '1px solid rgba(var(--personality-accent-rgb), 0.08)',
        }} />

        {/* The glow itself */}
        <motion.div
          animate={{
            width: `${glowRadius}%`,
            height: `${glowRadius}%`,
            opacity: isAuto ? 0.3 : 0.15 + (displayPct / 100) * 0.65,
          }}
          transition={{ type: 'spring', stiffness: 200, damping: 25 }}
          style={{
            borderRadius: '50%',
            background: `radial-gradient(circle, var(--personality-accent), rgba(var(--personality-accent-rgb), 0.05))`,
            filter: `blur(${8 + (displayPct / 100) * 12}px)`,
          }}
        />

        {/* Center sun/moon icon */}
        <motion.div
          animate={{ scale: 0.6 + (displayPct / 100) * 0.5 }}
          transition={{ type: 'spring', stiffness: 300, damping: 25 }}
          style={{ position: 'absolute' }}
        >
          {displayPct > 40 ? (
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none"
              stroke="var(--personality-accent)" strokeWidth="1.5" strokeLinecap="round"
              style={{ opacity: 0.7 }}
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
          ) : (
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none"
              stroke="var(--personality-accent)" strokeWidth="1.5" strokeLinecap="round"
              style={{ opacity: 0.7 }}
            >
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
            </svg>
          )}
        </motion.div>
      </div>

      {/* Value label + auto reset */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <motion.button
          onClick={() => applyValue(-1)}
          whileTap={{ scale: 0.9 }}
          style={{
            fontSize: 10, fontWeight: 700, letterSpacing: '0.05em',
            color: isAuto ? 'var(--text-tertiary)' : 'var(--personality-accent)',
            background: isAuto
              ? 'var(--surface-subtle)'
              : 'rgba(var(--personality-accent-rgb), 0.12)',
            border: `1px solid ${isAuto
              ? 'var(--border-subtle)'
              : 'rgba(var(--personality-accent-rgb), 0.2)'}`,
            borderRadius: 10,
            padding: '4px 10px',
            cursor: 'pointer',
          }}
        >
          {isAuto ? 'AUTO' : `${value}%`}
        </motion.button>
        <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
          {isAuto ? 'Follows time of day' : 'Drag the glow to adjust'}
        </span>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Background Mode -- live mini previews                              */
/* ------------------------------------------------------------------ */

const BG_MODES = [
  {
    id: 'gradient',
    label: 'Gradient',
    // Soft flowing gradient preview
    bg: 'linear-gradient(135deg, rgba(var(--personality-accent-rgb), 0.3), rgba(var(--personality-accent-rgb), 0.05), rgba(var(--personality-accent-rgb), 0.15))',
  },
  {
    id: 'texture',
    label: 'Texture',
    // Fabric-like noise overlay
    bg: 'repeating-conic-gradient(rgba(var(--personality-accent-rgb), 0.06) 0% 25%, transparent 0% 50%) 0 0 / 6px 6px',
  },
  {
    id: 'glass',
    label: 'Glass',
    // Frosted glow
    bg: 'radial-gradient(ellipse at 30% 40%, rgba(var(--personality-accent-rgb), 0.15), transparent 60%)',
  },
]

function BackgroundMiniPreviews() {
  const [active, setActive] = useState('gradient')

  useEffect(() => {
    const val = getComputedStyle(document.documentElement)
      .getPropertyValue('--ui-backgroundMode').trim()
    if (val) setActive(val)
  }, [])

  const handleSwitch = (mode: string) => {
    setActive(mode)
    document.documentElement.style.setProperty('--ui-backgroundMode', mode)
  }

  return (
    <div data-gesture-ignore="true" style={{ display: 'flex', gap: 12 }}>
      {BG_MODES.map(m => (
        <motion.button
          key={m.id}
          onClick={() => handleSwitch(m.id)}
          whileHover={{ scale: 1.04 }}
          whileTap={{ scale: 0.96 }}
          style={{
            flex: 1,
            aspectRatio: '1',
            borderRadius: 16,
            border: 'none',
            cursor: 'pointer',
            position: 'relative',
            overflow: 'hidden',
            background: 'rgba(0,0,0,0.3)',
          }}
        >
          {/* Live preview background */}
          <div style={{
            position: 'absolute', inset: 0,
            background: m.bg,
            borderRadius: 16,
          }} />

          {/* Active ring */}
          <motion.div
            animate={{
              borderColor: m.id === active
                ? 'var(--personality-accent)'
                : 'rgba(var(--personality-accent-rgb), 0.1)',
              boxShadow: m.id === active
                ? '0 0 16px rgba(var(--personality-accent-rgb), 0.3), inset 0 0 12px rgba(var(--personality-accent-rgb), 0.1)'
                : 'none',
            }}
            transition={{ type: 'spring', stiffness: 400, damping: 30 }}
            style={{
              position: 'absolute', inset: 0,
              borderRadius: 16,
              border: '2px solid transparent',
              pointerEvents: 'none',
            }}
          />

          {/* Label at bottom */}
          <div style={{
            position: 'absolute', bottom: 0, left: 0, right: 0,
            padding: '16px 0 8px',
            background: 'linear-gradient(transparent, rgba(0,0,0,0.5))',
            borderRadius: '0 0 16px 16px',
          }}>
            <span style={{
              fontSize: 10, fontWeight: 600,
              color: m.id === active ? 'var(--personality-accent)' : 'var(--text-secondary)',
              letterSpacing: '0.03em',
            }}>
              {m.label}
            </span>
          </div>
        </motion.button>
      ))}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Time-of-day preview strip                                          */
/* ------------------------------------------------------------------ */

function TimePreviewStrip() {
  const hours = [6, 9, 12, 16, 20, 23] // Dawn, morning, noon, afternoon, evening, night
  const labels = ['Dawn', 'Morning', 'Noon', 'Afternoon', 'Evening', 'Night']
  const colors = [
    'linear-gradient(135deg, #2a1f3d, #5a3f6e)',  // dawn
    'linear-gradient(135deg, #3d2f1f, #6e5a3f)',  // morning
    'linear-gradient(135deg, #4a4535, #8a7f6a)',  // noon
    'linear-gradient(135deg, #3d351f, #6e603f)',  // afternoon
    'linear-gradient(135deg, #1f2a3d, #3f5a6e)',  // evening
    'linear-gradient(135deg, #0f0e16, #1a1825)',  // night
  ]

  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null)

  return (
    <div data-gesture-ignore="true" style={{ display: 'flex', gap: 6, marginTop: 4 }}>
      {hours.map((_, i) => (
        <motion.div
          key={i}
          onHoverStart={() => setHoveredIdx(i)}
          onHoverEnd={() => setHoveredIdx(null)}
          animate={{
            flex: hoveredIdx === i ? 2 : 1,
            borderRadius: 10,
          }}
          transition={{ type: 'spring', stiffness: 400, damping: 30 }}
          style={{
            height: 44,
            borderRadius: 10,
            background: colors[i],
            position: 'relative',
            overflow: 'hidden',
            cursor: 'default',
          }}
        >
          <AnimatePresence>
            {hoveredIdx === i && (
              <motion.span
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 4 }}
                style={{
                  position: 'absolute', inset: 0,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 9, fontWeight: 600,
                  color: 'rgba(255,255,255,0.7)',
                  letterSpacing: '0.04em',
                }}
              >
                {labels[i]}
              </motion.span>
            )}
          </AnimatePresence>
        </motion.div>
      ))}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Section Header                                                     */
/* ------------------------------------------------------------------ */

function SectionHeader({ children }: { children: string }) {
  return (
    <div style={{
      fontSize: 10, fontWeight: 600, letterSpacing: '0.12em',
      textTransform: 'uppercase' as const,
      color: 'rgba(var(--personality-accent-rgb), 0.45)',
      marginBottom: 12,
    }}>
      {children}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Export                                                             */
/* ------------------------------------------------------------------ */

interface AppearanceSectionProps {
  onAdjusting?: (isAdjusting: boolean) => void
}

export function AppearanceSection({ onAdjusting }: AppearanceSectionProps) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1, type: 'spring', stiffness: 300, damping: 28 }}
      style={{ display: 'flex', flexDirection: 'column', gap: 28 }}
    >
      {/* Brightness */}
      <div>
        <SectionHeader>Brightness</SectionHeader>
        <RadialBrightness onAdjusting={onAdjusting} />
      </div>

      {/* Background */}
      <div>
        <SectionHeader>Background</SectionHeader>
        <BackgroundMiniPreviews />
      </div>

      {/* Time of Day */}
      <div>
        <SectionHeader>Time of Day Preview</SectionHeader>
        <TimePreviewStrip />
      </div>
    </motion.section>
  )
}
