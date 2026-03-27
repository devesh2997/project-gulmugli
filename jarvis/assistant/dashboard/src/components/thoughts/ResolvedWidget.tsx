/**
 * ResolvedWidget — Rich mini-visualization widgets for resolved thoughts.
 *
 * Each widget is a self-contained, animated micro-UI that communicates
 * its result through colour, animation, and shape. Designed to go beyond
 * Apple's Dynamic Island — richer, more contextual, more alive.
 *
 * Design principles:
 *   - Frosted glass aesthetic with generous personality accent saturation
 *   - Ambient glow pulses on every widget
 *   - Music: spinning vinyl with grooves, equalizer bars, scrolling marquee
 *   - Light: realistic bulb silhouette filled with actual light colour
 *   - Volume: thick arc gauge with pulsing endpoint and speaker icon
 *   - Failed: dramatic shake + red shockwave pulse
 *   - Success: double ripple + large checkmark circle
 */

import { motion } from 'framer-motion'
import type { IntentBadge } from '../../types/assistant'

interface ResolvedWidgetProps {
  badge: IntentBadge
  size: number
}

// Shared frosted glass base style — more personality colour saturation
const glassBase = (size: number, accentOpacity = 0.22): React.CSSProperties => ({
  width: size,
  height: size,
  borderRadius: size * 0.26,
  background: `linear-gradient(135deg, rgba(var(--personality-accent-rgb), ${accentOpacity}), rgba(var(--personality-accent-rgb), ${accentOpacity * 0.5}))`,
  backdropFilter: 'blur(14px)',
  WebkitBackdropFilter: 'blur(14px)',
  border: '1px solid rgba(var(--personality-accent-rgb), 0.25)',
  boxShadow: `0 4px 24px rgba(var(--personality-accent-rgb), 0.3), inset 0 1px 0 rgba(255,255,255,0.08)`,
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
 */
function SuccessBorder({ size, borderRadius }: { size: number; borderRadius: number }) {
  const inset = 1
  const w = size - inset * 2
  const h = size - inset * 2
  const r = Math.min(borderRadius, w / 2, h / 2)

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

/** Ambient glow that pulses gently behind every widget */
function AmbientGlow({ size, borderRadius, color }: { size: number; borderRadius: number; color?: string }) {
  const c = color || 'rgba(var(--personality-accent-rgb), 0.3)'
  return (
    <motion.div
      style={{
        position: 'absolute', inset: -6, borderRadius: borderRadius + 6,
        background: `radial-gradient(circle, ${c} 0%, transparent 70%)`,
        pointerEvents: 'none',
      }}
      animate={{ opacity: [0.4, 0.8, 0.4], scale: [0.96, 1.06, 0.96] }}
      transition={{ duration: 2.5, repeat: Infinity, ease: 'easeInOut' }}
    />
  )
}

/* ── Music: vinyl disc with grooves, music note center, equalizer, marquee ── */
function MusicWidget({ size, detail }: { size: number; detail?: string }) {
  const br = size * 0.26
  const discSize = size * 0.60
  const discR = discSize / 2

  return (
    <motion.div {...enterAnim} style={glassBase(size, 0.22)}>
      <AmbientGlow size={size} borderRadius={br} />

      {/* Spinning vinyl disc with grooves */}
      <motion.div
        style={{
          width: discSize, height: discSize, borderRadius: '50%',
          background: `conic-gradient(from 0deg, rgba(var(--personality-accent-rgb), 0.35), rgba(var(--personality-accent-rgb), 0.1), rgba(var(--personality-accent-rgb), 0.35))`,
          border: '2px solid rgba(var(--personality-accent-rgb), 0.35)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          position: 'relative',
          boxShadow: `0 0 12px rgba(var(--personality-accent-rgb), 0.2)`,
        }}
        animate={{ rotate: 360 }}
        transition={{ duration: 3, repeat: Infinity, ease: 'linear' }}
      >
        {/* Vinyl grooves — concentric rings */}
        {[0.82, 0.68, 0.54].map((frac, i) => (
          <div key={i} style={{
            position: 'absolute',
            width: discR * 2 * frac, height: discR * 2 * frac,
            borderRadius: '50%',
            border: '0.5px solid rgba(var(--personality-accent-rgb), 0.15)',
          }} />
        ))}

        {/* Center — music note icon */}
        <div style={{
          width: size * 0.16, height: size * 0.16, borderRadius: '50%',
          background: 'var(--personality-accent)',
          boxShadow: '0 0 8px rgba(var(--personality-accent-rgb), 0.5)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <svg width={size * 0.09} height={size * 0.09} viewBox="0 0 24 24" fill="white">
            <path d="M12 3v10.55A4 4 0 1 0 14 17V7h4V3h-6z" />
          </svg>
        </div>
      </motion.div>

      {/* Equalizer bars — positioned below disc */}
      <div style={{
        position: 'absolute', bottom: detail ? 14 : 6,
        display: 'flex', gap: 2, alignItems: 'flex-end', height: size * 0.13,
      }}>
        {[0, 0.15, 0.05, 0.2, 0.1].map((delay, i) => (
          <motion.div
            key={i}
            style={{
              width: 3, borderRadius: 1.5,
              background: 'var(--personality-accent)',
              boxShadow: '0 0 4px rgba(var(--personality-accent-rgb), 0.4)',
            }}
            animate={{ height: [size * 0.04, size * 0.12, size * 0.06, size * 0.10, size * 0.04] }}
            transition={{
              duration: 0.8 + i * 0.1,
              repeat: Infinity,
              ease: 'easeInOut',
              delay: delay,
            }}
          />
        ))}
      </div>

      <SuccessBorder size={size} borderRadius={br} />

      {/* Song title — scrolling marquee if overflow */}
      {detail && (
        <motion.div
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.35 }}
          style={{
            position: 'absolute', bottom: 3, left: 4, right: 4,
            fontSize: 7.5, fontWeight: 600, color: 'var(--personality-accent)',
            textAlign: 'center', lineHeight: 1.1,
            overflow: 'hidden', whiteSpace: 'nowrap',
          }}
        >
          <motion.span
            style={{ display: 'inline-block' }}
            animate={detail.length > 14 ? { x: [0, -(detail.length * 3.5), 0] } : {}}
            transition={detail.length > 14 ? { duration: detail.length * 0.3, repeat: Infinity, ease: 'linear', repeatDelay: 1 } : {}}
          >
            {detail}
          </motion.span>
        </motion.div>
      )}
    </motion.div>
  )
}

/* ── Lights: realistic lightbulb silhouette with colour fill + glow ───── */

/** Parse a CSS colour from the detail string. Looks for hex, rgb(), or named colours. */
function parseLightColor(detail?: string): { color: string; isOff: boolean } {
  if (!detail) return { color: 'var(--personality-accent)', isOff: false }
  const lower = detail.toLowerCase()

  // Check for off state
  if (/\boff\b/.test(lower) || /\bturn(ed)?\s*off\b/.test(lower)) {
    return { color: '#666', isOff: true }
  }

  // Match hex colour
  const hexMatch = detail.match(/#([0-9a-fA-F]{3,8})\b/)
  if (hexMatch) return { color: hexMatch[0], isOff: false }

  // Match rgb/rgba
  const rgbMatch = detail.match(/rgba?\([^)]+\)/)
  if (rgbMatch) return { color: rgbMatch[0], isOff: false }

  // Match common colour names from detail text
  const namedColours: Record<string, string> = {
    red: '#ef4444', blue: '#3b82f6', green: '#22c55e', yellow: '#eab308',
    orange: '#f97316', purple: '#a855f7', pink: '#ec4899', white: '#f8fafc',
    warm: '#fbbf24', cool: '#93c5fd', cyan: '#06b6d4', teal: '#14b8a6',
    magenta: '#d946ef', lime: '#84cc16', indigo: '#6366f1', violet: '#8b5cf6',
  }
  for (const [name, hex] of Object.entries(namedColours)) {
    if (lower.includes(name)) return { color: hex, isOff: false }
  }

  return { color: 'var(--personality-accent)', isOff: false }
}

/** Parse brightness from detail string (0-100). Defaults to 80. */
function parseBrightness(detail?: string): number {
  if (!detail) return 80
  const match = detail.match(/(\d+)\s*%/)
  if (match) return Math.min(100, Math.max(0, parseInt(match[1], 10)))
  const brightMatch = detail.match(/brightness\s*[:=]?\s*(\d+)/i)
  if (brightMatch) return Math.min(100, Math.max(0, parseInt(brightMatch[1], 10)))
  return 80
}

function LightWidget({ size, detail }: { size: number; detail?: string }) {
  const br = size * 0.26
  const { color, isOff } = parseLightColor(detail)
  const brightness = isOff ? 0 : parseBrightness(detail)
  const glowIntensity = brightness / 100

  return (
    <motion.div
      {...enterAnim}
      style={{
        ...glassBase(size, 0.15),
        // Tint the widget background with the light colour
        background: isOff
          ? 'linear-gradient(135deg, rgba(100,100,100,0.12), rgba(80,80,80,0.05))'
          : `linear-gradient(135deg, ${color}22, ${color}0a)`,
        border: isOff
          ? '1px solid rgba(100,100,100,0.2)'
          : `1px solid ${color}40`,
        boxShadow: isOff
          ? '0 4px 20px rgba(0,0,0,0.15), inset 0 1px 0 rgba(255,255,255,0.04)'
          : `0 4px 24px ${color}40, 0 0 ${size * glowIntensity * 0.6}px ${color}30, inset 0 1px 0 rgba(255,255,255,0.06)`,
      }}
    >
      {/* Ambient glow using actual light colour */}
      {!isOff && (
        <motion.div
          style={{
            position: 'absolute', inset: -8, borderRadius: br + 8,
            background: `radial-gradient(circle, ${color}50 0%, transparent 65%)`,
            pointerEvents: 'none',
          }}
          animate={{
            opacity: [0.3 * glowIntensity, 0.7 * glowIntensity, 0.3 * glowIntensity],
            scale: [0.95, 1.08, 0.95],
          }}
          transition={{ duration: 2.2, repeat: Infinity, ease: 'easeInOut' }}
        />
      )}

      <SuccessBorder size={size} borderRadius={br} />

      {/* Lightbulb silhouette */}
      <svg
        width={size * 0.48} height={size * 0.56}
        viewBox="0 0 40 48"
        style={{ position: 'relative', zIndex: 2 }}
      >
        {/* Outer glow filter */}
        <defs>
          <filter id={`bulb-glow-${size}`} x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation={isOff ? 0 : 3 * glowIntensity} result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <linearGradient id={`bulb-fill-${size}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={isOff ? '#555' : color} stopOpacity={isOff ? 0.3 : 0.9} />
            <stop offset="100%" stopColor={isOff ? '#444' : color} stopOpacity={isOff ? 0.15 : 0.5} />
          </linearGradient>
        </defs>

        {/* Bulb glass shape */}
        <path
          d="M20 2 C28 2 34 9 34 17 C34 22 31 25.5 28 28 C26 30 25 32 25 34 L15 34 C15 32 14 30 12 28 C9 25.5 6 22 6 17 C6 9 12 2 20 2 Z"
          fill={`url(#bulb-fill-${size})`}
          filter={`url(#bulb-glow-${size})`}
          stroke={isOff ? '#666' : color}
          strokeWidth={0.8}
          strokeOpacity={isOff ? 0.3 : 0.5}
        />

        {/* Bulb screw base */}
        <rect x="14" y="34" width="12" height="3" rx="1"
          fill={isOff ? '#555' : 'rgba(255,255,255,0.3)'}
          stroke={isOff ? '#444' : 'rgba(255,255,255,0.15)'} strokeWidth={0.5}
        />
        <rect x="15" y="37.5" width="10" height="2.5" rx="1"
          fill={isOff ? '#4a4a4a' : 'rgba(255,255,255,0.2)'}
          stroke={isOff ? '#3a3a3a' : 'rgba(255,255,255,0.1)'} strokeWidth={0.5}
        />
        <rect x="16" y="40.5" width="8" height="2" rx="1"
          fill={isOff ? '#444' : 'rgba(255,255,255,0.15)'}
        />

        {/* Filament / inner glow highlight when on */}
        {!isOff && (
          <motion.ellipse
            cx={20} cy={16} rx={6} ry={8}
            fill={color} fillOpacity={0.25}
            animate={{ fillOpacity: [0.15, 0.35, 0.15] }}
            transition={{ duration: 1.8, repeat: Infinity, ease: 'easeInOut' }}
          />
        )}
      </svg>

      {/* Detail text */}
      {detail && (
        <motion.div
          initial={{ opacity: 0 }} animate={{ opacity: 0.85 }}
          transition={{ delay: 0.4 }}
          style={{
            position: 'absolute', bottom: 3, left: 4, right: 4,
            fontSize: 7, fontWeight: 600,
            color: isOff ? '#888' : color,
            textAlign: 'center', lineHeight: 1.1,
            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
            textShadow: isOff ? 'none' : `0 0 6px ${color}60`,
          }}
        >
          {detail}
        </motion.div>
      )}
    </motion.div>
  )
}

/* ── Volume: thick arc gauge + pulsing dot + speaker icon ───────────── */
function VolumeWidget({ size, detail }: { size: number; detail?: string }) {
  const br = size * 0.26
  const levelMatch = detail?.match(/(\d+)/)
  const level = levelMatch ? Math.min(100, Math.max(0, parseInt(levelMatch[1], 10))) : 50
  const fraction = level / 100

  // Arc math
  const r = size * 0.34
  const cx = size / 2
  const cy = size / 2 - 2
  const startDeg = -225
  const endDeg = 45
  const sweepDeg = startDeg + (endDeg - startDeg) * fraction
  const toRad = (d: number) => d * Math.PI / 180
  const arcPt = (deg: number) => ({ x: cx + r * Math.cos(toRad(deg)), y: cy + r * Math.sin(toRad(deg)) })
  const start = arcPt(startDeg)
  const end = arcPt(endDeg)
  const filled = arcPt(sweepDeg)

  return (
    <motion.div {...enterAnim} style={glassBase(size, 0.15)}>
      <AmbientGlow size={size} borderRadius={br} />
      <SuccessBorder size={size} borderRadius={br} />

      {/* Volume-intensity ambient glow */}
      <div style={{
        position: 'absolute', inset: 0, borderRadius: br,
        background: `radial-gradient(circle, rgba(var(--personality-accent-rgb), ${0.08 + fraction * 0.22}) 0%, transparent 70%)`,
      }} />

      <svg width={size * 0.88} height={size * 0.88} viewBox={`0 0 ${size} ${size}`} style={{ position: 'relative' }}>
        {/* Background track — thicker */}
        <path
          d={`M ${start.x} ${start.y} A ${r} ${r} 0 1 1 ${end.x} ${end.y}`}
          fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth={6} strokeLinecap="round"
        />
        {/* Filled arc — thicker 6px */}
        <motion.path
          d={`M ${start.x} ${start.y} A ${r} ${r} 0 ${fraction > 0.5 ? 1 : 0} 1 ${filled.x} ${filled.y}`}
          fill="none" stroke="var(--personality-accent)" strokeWidth={6} strokeLinecap="round"
          initial={{ pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 0.6, delay: 0.15, ease: 'easeOut' }}
          style={{ filter: `drop-shadow(0 0 6px rgba(var(--personality-accent-rgb), 0.5))` }}
        />
        {/* Pulsing endpoint dot */}
        <motion.circle
          cx={filled.x} cy={filled.y} r={4}
          fill="var(--personality-accent)"
          initial={{ scale: 0, opacity: 0 }}
          animate={{ scale: [1, 1.3, 1], opacity: 1 }}
          transition={{
            scale: { delay: 0.7, duration: 1.2, repeat: Infinity, ease: 'easeInOut' },
            opacity: { delay: 0.7, duration: 0.2 },
          }}
          style={{ filter: `drop-shadow(0 0 5px rgba(var(--personality-accent-rgb), 0.7))` }}
        />

        {/* Speaker icon — scales with volume */}
        <g transform={`translate(${cx - 6}, ${cy + r * 0.45})`}>
          <svg width={12} height={12} viewBox="0 0 24 24" fill="none">
            <path d="M11 5L6 9H2v6h4l5 4V5z" fill="var(--personality-accent)" fillOpacity={0.7} />
            {/* Sound waves — more waves at higher volume */}
            {fraction > 0.1 && (
              <motion.path
                d="M15.54 8.46a5 5 0 0 1 0 7.07"
                stroke="var(--personality-accent)" strokeWidth={1.5} strokeLinecap="round"
                initial={{ opacity: 0 }} animate={{ opacity: 0.6 }}
                transition={{ delay: 0.5 }}
              />
            )}
            {fraction > 0.5 && (
              <motion.path
                d="M19.07 4.93a10 10 0 0 1 0 14.14"
                stroke="var(--personality-accent)" strokeWidth={1.5} strokeLinecap="round"
                initial={{ opacity: 0 }} animate={{ opacity: 0.5 }}
                transition={{ delay: 0.7 }}
              />
            )}
          </svg>
        </g>
      </svg>

      {/* Level number — larger, bolder */}
      <div style={{
        position: 'absolute',
        top: '50%', left: '50%',
        transform: 'translate(-50%, -55%)',
        fontSize: size * 0.28, fontWeight: 800,
        color: 'var(--personality-accent)',
        fontFamily: 'ui-monospace, "SF Mono", monospace',
        textShadow: `0 0 10px rgba(var(--personality-accent-rgb), 0.5)`,
        letterSpacing: '-0.02em',
      }}>
        {level}
      </div>
    </motion.div>
  )
}

/* ── Generic success: double ripple + large checkmark circle ─────────── */
function SuccessWidget({ size, detail }: { size: number; detail?: string }) {
  return (
    <motion.div {...enterAnim} style={glassBase(size, 0.15)}>
      <AmbientGlow size={size} borderRadius={size * 0.26} />
      <SuccessBorder size={size} borderRadius={size * 0.26} />

      {/* First ripple */}
      <motion.div
        style={{
          position: 'absolute', width: size * 0.6, height: size * 0.6,
          borderRadius: '50%', border: '2px solid rgba(var(--personality-accent-rgb), 0.35)',
        }}
        initial={{ scale: 0.5, opacity: 0.9 }}
        animate={{ scale: 2, opacity: 0 }}
        transition={{ duration: 1.1, ease: 'easeOut' }}
      />
      {/* Second ripple — delayed for double-ripple impact */}
      <motion.div
        style={{
          position: 'absolute', width: size * 0.5, height: size * 0.5,
          borderRadius: '50%', border: '1.5px solid rgba(var(--personality-accent-rgb), 0.25)',
        }}
        initial={{ scale: 0.5, opacity: 0.7 }}
        animate={{ scale: 2.2, opacity: 0 }}
        transition={{ duration: 1.2, delay: 0.2, ease: 'easeOut' }}
      />

      {/* Checkmark in accent circle — bigger (50% of size) */}
      <motion.div
        style={{
          width: size * 0.50, height: size * 0.50, borderRadius: '50%',
          background: `linear-gradient(135deg, var(--personality-accent), rgba(var(--personality-accent-rgb), 0.7))`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: `0 2px 14px rgba(var(--personality-accent-rgb), 0.45)`,
        }}
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        transition={{ delay: 0.15, type: 'spring', stiffness: 400, damping: 15 }}
      >
        <svg width={size * 0.24} height={size * 0.24} viewBox="0 0 16 16" fill="none">
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
          initial={{ opacity: 0 }} animate={{ opacity: 0.85 }}
          transition={{ delay: 0.4 }}
          style={{
            position: 'absolute', bottom: 4, left: 4, right: 4,
            fontSize: 7.5, fontWeight: 600, color: 'var(--personality-accent)',
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

/* ── Failed: dramatic red shake + error shockwave pulse + large X ───── */
function FailedWidget({ size, detail }: { size: number; detail?: string }) {
  return (
    <motion.div
      {...enterAnim}
      style={{
        ...glassBase(size, 0.08),
        background: 'linear-gradient(135deg, rgba(255, 70, 70, 0.22), rgba(255, 50, 50, 0.08))',
        border: '1px solid rgba(255, 70, 70, 0.35)',
        boxShadow: '0 4px 24px rgba(255, 70, 70, 0.25), inset 0 1px 0 rgba(255,255,255,0.04)',
      }}
    >
      {/* Red shockwave pulse that expands outward */}
      <motion.div
        style={{
          position: 'absolute',
          width: size * 0.5, height: size * 0.5,
          borderRadius: '50%',
          border: '2px solid rgba(255, 80, 80, 0.5)',
          boxShadow: '0 0 8px rgba(255, 80, 80, 0.3)',
        }}
        initial={{ scale: 0.4, opacity: 0.9 }}
        animate={{ scale: 2.5, opacity: 0 }}
        transition={{ duration: 0.8, delay: 0.2, ease: 'easeOut' }}
      />
      {/* Second shockwave — delayed */}
      <motion.div
        style={{
          position: 'absolute',
          width: size * 0.4, height: size * 0.4,
          borderRadius: '50%',
          border: '1.5px solid rgba(255, 80, 80, 0.35)',
        }}
        initial={{ scale: 0.5, opacity: 0.7 }}
        animate={{ scale: 2.8, opacity: 0 }}
        transition={{ duration: 0.9, delay: 0.35, ease: 'easeOut' }}
      />

      {/* Red pulse on the whole widget background */}
      <motion.div
        style={{
          position: 'absolute', inset: 0, borderRadius: size * 0.26,
          background: 'rgba(255, 60, 60, 0.15)',
        }}
        animate={{ opacity: [0, 0.4, 0] }}
        transition={{ duration: 0.6, delay: 0.15 }}
      />

      {/* Dramatic shake — 5px displacement */}
      <motion.div
        animate={{ x: [0, -5, 5, -4, 4, -2, 2, 0] }}
        transition={{ duration: 0.5, delay: 0.25 }}
        style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3 }}
      >
        {/* X mark in red circle — larger */}
        <motion.div
          style={{
            width: size * 0.46, height: size * 0.46, borderRadius: '50%',
            background: 'linear-gradient(135deg, #ff6b6b, #ef4444)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 2px 12px rgba(255, 80, 80, 0.5)',
          }}
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ delay: 0.15, type: 'spring', stiffness: 400, damping: 15 }}
        >
          <svg width={size * 0.24} height={size * 0.24} viewBox="0 0 16 16" fill="none">
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
            textShadow: '0 0 6px rgba(255, 80, 80, 0.3)',
          }}>
            {detail}
          </div>
        )}
      </motion.div>
    </motion.div>
  )
}
