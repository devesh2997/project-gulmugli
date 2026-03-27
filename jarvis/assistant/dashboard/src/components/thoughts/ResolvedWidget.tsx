/**
 * ResolvedWidget — HD mini-widgets for resolved thoughts (Phase 3).
 *
 * Inspired by Apple's Dynamic Island: each widget is a rich, self-contained
 * visual that communicates its result through colour, animation, and shape
 * rather than just text. Every widget uses the personality accent colour
 * as its primary chromatic identity.
 *
 * Design principles:
 *   - Frosted glass aesthetic with warm undertones
 *   - Generous use of personality accent colour (not just borders — fills, glows, gradients)
 *   - Every widget has a satisfying "success" or "failure" micro-animation
 *   - Detail text is secondary — the visual should communicate the state
 */

import { motion } from 'framer-motion'
import type { IntentBadge } from '../../types/assistant'

interface ResolvedWidgetProps {
  badge: IntentBadge
  size: number
}

// Shared frosted glass base style
const glassBase = (size: number, accentOpacity = 0.15): React.CSSProperties => ({
  width: size,
  height: size,
  borderRadius: size * 0.28,
  background: `linear-gradient(135deg, rgba(var(--personality-accent-rgb), ${accentOpacity}), rgba(var(--personality-accent-rgb), ${accentOpacity * 0.4}))`,
  backdropFilter: 'blur(12px)',
  WebkitBackdropFilter: 'blur(12px)',
  border: '1px solid rgba(var(--personality-accent-rgb), 0.2)',
  boxShadow: `0 4px 20px rgba(var(--personality-accent-rgb), 0.25), inset 0 1px 0 rgba(255,255,255,0.06)`,
  display: 'flex',
  flexDirection: 'column' as const,
  alignItems: 'center',
  justifyContent: 'center',
  overflow: 'hidden',
  position: 'relative' as const,
})

const enterAnim = {
  initial: { scale: 0.5, opacity: 0, filter: 'blur(8px)' },
  animate: { scale: 1, opacity: 1, filter: 'blur(0px)' },
  transition: { duration: 0.45, ease: [0.34, 1.56, 0.64, 1] as [number, number, number, number] },
}

export function ResolvedWidget({ badge, size }: ResolvedWidgetProps) {
  if (badge.status === 'failed') {
    return <FailedWidget size={size} detail={badge.detail} />
  }
  switch (badge.icon) {
    case 'music': return <MusicWidget size={size} detail={badge.detail} />
    case 'bulb': return <LightWidget size={size} detail={badge.detail} />
    case 'volume': return <VolumeWidget size={size} detail={badge.detail} />
    default: return <SuccessWidget size={size} detail={badge.detail} />
  }
}

/**
 * SuccessBorder — animated green border that traces around the widget perimeter,
 * then collapses into a small checkmark badge outside the corner.
 * Inspired by Apple's completion animations.
 */
function SuccessBorder({ size, borderRadius }: { size: number; borderRadius: number }) {
  // SVG rounded rect perimeter for the border trace animation
  const inset = 1
  const w = size - inset * 2
  const h = size - inset * 2
  const r = Math.min(borderRadius, w / 2, h / 2)

  // Build a rounded rect path
  const path = [
    `M ${inset + r} ${inset}`,
    `L ${inset + w - r} ${inset}`,
    `Q ${inset + w} ${inset} ${inset + w} ${inset + r}`,
    `L ${inset + w} ${inset + h - r}`,
    `Q ${inset + w} ${inset + h} ${inset + w - r} ${inset + h}`,
    `L ${inset + r} ${inset + h}`,
    `Q ${inset} ${inset + h} ${inset} ${inset + h - r}`,
    `L ${inset} ${inset + r}`,
    `Q ${inset} ${inset} ${inset + r} ${inset}`,
  ].join(' ')

  return (
    <>
      {/* Green border traces the perimeter */}
      <svg
        width={size} height={size}
        viewBox={`0 0 ${size} ${size}`}
        style={{ position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 10 }}
      >
        <motion.path
          d={path}
          fill="none"
          stroke="#4ade80"
          strokeWidth={2}
          strokeLinecap="round"
          initial={{ pathLength: 0, opacity: 0 }}
          animate={{ pathLength: [0, 1, 1], opacity: [0, 1, 0] }}
          transition={{ duration: 1.2, times: [0, 0.6, 1], ease: 'easeInOut' }}
          style={{ filter: 'drop-shadow(0 0 4px rgba(74, 222, 128, 0.5))' }}
        />
      </svg>

      {/* Checkmark badge that pops in at top-right after border completes */}
      <motion.div
        style={{
          position: 'absolute',
          top: -6, right: -6, zIndex: 11,
          width: 18, height: 18, borderRadius: 9,
          background: 'linear-gradient(135deg, #4ade80, #22c55e)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: '0 2px 8px rgba(74, 222, 128, 0.4)',
        }}
        initial={{ scale: 0, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ delay: 0.7, type: 'spring', stiffness: 500, damping: 15 }}
      >
        <svg width="10" height="10" viewBox="0 0 16 16" fill="none">
          <motion.path
            d="M3 8.5L6.5 12L13 4"
            stroke="#fff" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round"
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 0.25, delay: 0.85 }}
          />
        </svg>
      </motion.div>
    </>
  )
}

/* ── Music: vinyl record with spinning animation + song info ────────── */
function MusicWidget({ size, detail }: { size: number; detail?: string }) {
  const br = size * 0.28
  return (
    <motion.div {...enterAnim} style={glassBase(size, 0.18)}>
      {/* Ambient glow pulse behind widget */}
      <motion.div
        style={{
          position: 'absolute', inset: -4, borderRadius: br + 4,
          background: 'radial-gradient(circle, rgba(var(--personality-accent-rgb), 0.3) 0%, transparent 70%)',
        }}
        animate={{ opacity: [0.4, 0.8, 0.4], scale: [0.95, 1.05, 0.95] }}
        transition={{ duration: 2.5, repeat: Infinity, ease: 'easeInOut' }}
      />

      {/* Spinning vinyl/disc */}
      <motion.div
        style={{
          width: size * 0.52, height: size * 0.52, borderRadius: '50%',
          background: `conic-gradient(from 0deg, rgba(var(--personality-accent-rgb), 0.3), rgba(var(--personality-accent-rgb), 0.1), rgba(var(--personality-accent-rgb), 0.3))`,
          border: '2px solid rgba(var(--personality-accent-rgb), 0.3)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          position: 'relative',
        }}
        animate={{ rotate: 360 }}
        transition={{ duration: 3, repeat: Infinity, ease: 'linear' }}
      >
        {/* Center dot */}
        <div style={{
          width: size * 0.12, height: size * 0.12, borderRadius: '50%',
          background: 'var(--personality-accent)',
          boxShadow: '0 0 8px rgba(var(--personality-accent-rgb), 0.5)',
        }} />
      </motion.div>

      {/* Green border trace → checkmark animation */}
      <SuccessBorder size={size} borderRadius={br} />

      {/* Song title */}
      {detail && (
        <motion.div
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.35 }}
          style={{
            position: 'absolute', bottom: 3, left: 4, right: 4,
            fontSize: 7, fontWeight: 600, color: 'var(--personality-accent)',
            textAlign: 'center', lineHeight: 1.1,
            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
          }}
        >
          {detail}
        </motion.div>
      )}
    </motion.div>
  )
}

/* ── Lights: radiating glow with light rays ─────────────────────────── */
function LightWidget({ size, detail }: { size: number; detail?: string }) {
  return (
    <motion.div {...enterAnim} style={{ ...glassBase(size, 0.12), borderRadius: '50%' }}>
      <SuccessBorder size={size} borderRadius={size / 2} />
      {/* Radiating light rays */}
      {[0, 45, 90, 135, 180, 225, 270, 315].map((angle) => (
        <motion.div
          key={angle}
          style={{
            position: 'absolute',
            width: 2, height: size * 0.25,
            background: `linear-gradient(to top, rgba(var(--personality-accent-rgb), 0.5), transparent)`,
            transformOrigin: `50% ${size * 0.5}px`,
            transform: `rotate(${angle}deg)`,
            top: 0,
          }}
          initial={{ scaleY: 0, opacity: 0 }}
          animate={{ scaleY: 1, opacity: 0.7 }}
          transition={{ delay: 0.1 + (angle / 360) * 0.3, duration: 0.4 }}
        />
      ))}

      {/* Central glow orb */}
      <motion.div
        style={{
          width: size * 0.45, height: size * 0.45, borderRadius: '50%',
          background: `radial-gradient(circle, rgba(var(--personality-accent-rgb), 0.8) 0%, rgba(var(--personality-accent-rgb), 0.3) 60%, transparent 100%)`,
          boxShadow: `0 0 ${size * 0.3}px rgba(var(--personality-accent-rgb), 0.5)`,
        }}
        animate={{
          boxShadow: [
            `0 0 ${size * 0.2}px rgba(var(--personality-accent-rgb), 0.4)`,
            `0 0 ${size * 0.4}px rgba(var(--personality-accent-rgb), 0.6)`,
            `0 0 ${size * 0.2}px rgba(var(--personality-accent-rgb), 0.4)`,
          ],
        }}
        transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
      />

      {/* Bulb icon */}
      <svg
        width={size * 0.22} height={size * 0.22}
        viewBox="0 0 24 24"
        fill="white" fillOpacity={0.9}
        style={{ position: 'absolute' }}
      >
        <path d="M12 3a6 6 0 0 1 3.7 10.7c-.5.5-.7 1.1-.7 1.8V17H9v-1.5c0-.7-.3-1.3-.7-1.8A6 6 0 0 1 12 3z" />
        <path d="M9 21h6" stroke="white" strokeWidth={2} fill="none" strokeLinecap="round" />
      </svg>
    </motion.div>
  )
}

/* ── Volume: circular gauge with level indicator ────────────────────── */
function VolumeWidget({ size, detail }: { size: number; detail?: string }) {
  const br = size * 0.28
  const levelMatch = detail?.match(/(\d+)/)
  const level = levelMatch ? Math.min(100, Math.max(0, parseInt(levelMatch[1], 10))) : 50
  const fraction = level / 100

  // Arc math
  const r = size * 0.36
  const cx = size / 2
  const cy = size / 2
  const startDeg = -225
  const endDeg = 45
  const sweepDeg = startDeg + (endDeg - startDeg) * fraction
  const toRad = (d: number) => d * Math.PI / 180
  const arcPt = (deg: number) => ({ x: cx + r * Math.cos(toRad(deg)), y: cy + r * Math.sin(toRad(deg)) })
  const start = arcPt(startDeg)
  const end = arcPt(endDeg)
  const filled = arcPt(sweepDeg)

  return (
    <motion.div {...enterAnim} style={glassBase(size, 0.12)}>
      <SuccessBorder size={size} borderRadius={br} />
      {/* Ambient glow that intensifies with volume */}
      <div style={{
        position: 'absolute', inset: 0, borderRadius: size * 0.28,
        background: `radial-gradient(circle, rgba(var(--personality-accent-rgb), ${0.1 + fraction * 0.2}) 0%, transparent 70%)`,
      }} />

      <svg width={size * 0.85} height={size * 0.85} viewBox={`0 0 ${size} ${size}`} style={{ position: 'relative' }}>
        {/* Background track */}
        <path
          d={`M ${start.x} ${start.y} A ${r} ${r} 0 1 1 ${end.x} ${end.y}`}
          fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth={4} strokeLinecap="round"
        />
        {/* Filled arc with gradient effect via filter */}
        <motion.path
          d={`M ${start.x} ${start.y} A ${r} ${r} 0 ${fraction > 0.5 ? 1 : 0} 1 ${filled.x} ${filled.y}`}
          fill="none" stroke="var(--personality-accent)" strokeWidth={4} strokeLinecap="round"
          initial={{ pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 0.6, delay: 0.15, ease: 'easeOut' }}
          style={{ filter: `drop-shadow(0 0 6px rgba(var(--personality-accent-rgb), 0.5))` }}
        />
        {/* End dot */}
        <motion.circle
          cx={filled.x} cy={filled.y} r={3}
          fill="var(--personality-accent)"
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ delay: 0.7, type: 'spring', stiffness: 400 }}
          style={{ filter: `drop-shadow(0 0 4px rgba(var(--personality-accent-rgb), 0.6))` }}
        />
      </svg>

      {/* Level number */}
      <div style={{
        position: 'absolute',
        fontSize: size * 0.24, fontWeight: 700,
        color: 'var(--personality-accent)',
        fontFamily: 'ui-monospace, "SF Mono", monospace',
        textShadow: `0 0 8px rgba(var(--personality-accent-rgb), 0.4)`,
      }}>
        {level}
      </div>
    </motion.div>
  )
}

/* ── Generic success: checkmark with ripple ──────────────────────────── */
function SuccessWidget({ size, detail }: { size: number; detail?: string }) {
  return (
    <motion.div {...enterAnim} style={glassBase(size, 0.12)}>
      <SuccessBorder size={size} borderRadius={size * 0.28} />
      {/* Success ripple */}
      <motion.div
        style={{
          position: 'absolute', width: size * 0.6, height: size * 0.6,
          borderRadius: '50%', border: '2px solid rgba(var(--personality-accent-rgb), 0.3)',
        }}
        initial={{ scale: 0.5, opacity: 0.8 }}
        animate={{ scale: 1.8, opacity: 0 }}
        transition={{ duration: 1, ease: 'easeOut' }}
      />

      {/* Checkmark in accent circle */}
      <motion.div
        style={{
          width: size * 0.45, height: size * 0.45, borderRadius: '50%',
          background: `linear-gradient(135deg, var(--personality-accent), rgba(var(--personality-accent-rgb), 0.7))`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: `0 2px 12px rgba(var(--personality-accent-rgb), 0.4)`,
        }}
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        transition={{ delay: 0.15, type: 'spring', stiffness: 400, damping: 15 }}
      >
        <svg width={size * 0.22} height={size * 0.22} viewBox="0 0 16 16" fill="none">
          <motion.path
            d="M3 8.5L6.5 12L13 4"
            stroke="#fff" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round"
            initial={{ pathLength: 0 }} animate={{ pathLength: 1 }}
            transition={{ duration: 0.3, delay: 0.35 }}
          />
        </svg>
      </motion.div>

      {detail && (
        <motion.div
          initial={{ opacity: 0 }} animate={{ opacity: 0.8 }}
          transition={{ delay: 0.4 }}
          style={{
            position: 'absolute', bottom: 4, left: 4, right: 4,
            fontSize: 7, fontWeight: 600, color: 'var(--personality-accent)',
            textAlign: 'center', lineHeight: 1.1,
            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
          }}
        >
          {detail}
        </motion.div>
      )}
    </motion.div>
  )
}

/* ── Failed: red glass with animated X ───────────────────────────────── */
function FailedWidget({ size, detail }: { size: number; detail?: string }) {
  return (
    <motion.div
      {...enterAnim}
      style={{
        ...glassBase(size, 0.08),
        background: 'linear-gradient(135deg, rgba(255, 80, 80, 0.15), rgba(255, 60, 60, 0.06))',
        border: '1px solid rgba(255, 80, 80, 0.3)',
        boxShadow: '0 4px 20px rgba(255, 80, 80, 0.2), inset 0 1px 0 rgba(255,255,255,0.04)',
      }}
    >
      {/* Shake animation */}
      <motion.div
        animate={{ x: [0, -3, 3, -2, 2, 0] }}
        transition={{ duration: 0.4, delay: 0.3 }}
        style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3 }}
      >
        {/* X mark in red circle */}
        <motion.div
          style={{
            width: size * 0.4, height: size * 0.4, borderRadius: '50%',
            background: 'linear-gradient(135deg, #ff6b6b, #ff4444)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 2px 10px rgba(255, 80, 80, 0.4)',
          }}
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ delay: 0.15, type: 'spring', stiffness: 400, damping: 15 }}
        >
          <svg width={size * 0.2} height={size * 0.2} viewBox="0 0 16 16" fill="none">
            <motion.path
              d="M4 4L12 12M12 4L4 12"
              stroke="#fff" strokeWidth={2.5} strokeLinecap="round"
              initial={{ pathLength: 0 }} animate={{ pathLength: 1 }}
              transition={{ duration: 0.25, delay: 0.35 }}
            />
          </svg>
        </motion.div>

        {detail && (
          <div style={{
            fontSize: 7, fontWeight: 600, color: '#ff8888',
            textAlign: 'center', maxWidth: size - 8, lineHeight: 1.1,
            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
          }}>
            {detail}
          </div>
        )}
      </motion.div>
    </motion.div>
  )
}
