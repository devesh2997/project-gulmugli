/**
 * ResolvedWidget -- HD mini-widget that appears when a thought resolves (Phase 3).
 *
 * Each intent type gets a unique resolved visual:
 *   music  -> mini album-art card with song title + checkmark
 *   bulb   -> glowing circle showing actual light color + brightness
 *   volume -> arc/semicircle showing volume level
 *   brain  -> small speech bubble with "..." that fades
 *   search -> small speech bubble with "..." that fades
 *   memory -> small speech bubble with "..." that fades
 *   failed -> red-tinted version with X mark
 *
 * Uses personality accent color for shadow/glow.
 */

import { motion } from 'framer-motion'
import type { IntentBadge } from '../../types/assistant'

interface ResolvedWidgetProps {
  badge: IntentBadge
  size: number
}

export function ResolvedWidget({ badge, size }: ResolvedWidgetProps) {
  const isFailed = badge.status === 'failed'

  if (isFailed) {
    return <FailedWidget size={size} detail={badge.detail} />
  }

  switch (badge.icon) {
    case 'music':
      return <MusicResolvedWidget size={size} detail={badge.detail} />
    case 'bulb':
      return <LightResolvedWidget size={size} detail={badge.detail} />
    case 'volume':
      return <VolumeResolvedWidget size={size} detail={badge.detail} />
    default:
      return <ChatResolvedWidget size={size} />
  }
}

/* -- Music: mini album card with checkmark -------------------------------- */
function MusicResolvedWidget({ size, detail }: { size: number; detail?: string }) {
  return (
    <motion.div
      initial={{ scale: 0.6, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ duration: 0.4, ease: 'easeOut' }}
      style={{
        width: size,
        height: size,
        borderRadius: size * 0.2,
        background: 'rgba(var(--personality-accent-rgb), 0.12)',
        border: '1px solid rgba(var(--personality-accent-rgb), 0.25)',
        boxShadow: '0 0 12px rgba(var(--personality-accent-rgb), 0.2)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 2,
        overflow: 'hidden',
        position: 'relative',
      }}
    >
      {/* Mini equalizer bars as background decoration */}
      <div style={{ display: 'flex', gap: 1.5, alignItems: 'flex-end', height: size * 0.3 }}>
        {[0, 1, 2, 3].map(i => (
          <motion.div
            key={i}
            style={{
              width: 2.5,
              borderRadius: 1,
              background: 'var(--personality-accent)',
            }}
            animate={{ height: [size * 0.08, size * 0.22, size * 0.12, size * 0.18, size * 0.08] }}
            transition={{ duration: 1.2, repeat: 2, delay: i * 0.1, ease: 'easeInOut' }}
          />
        ))}
      </div>
      {/* Checkmark */}
      <svg width={size * 0.28} height={size * 0.28} viewBox="0 0 16 16" fill="none">
        <motion.path
          d="M3 8.5L6.5 12L13 4"
          stroke="#4ade80"
          strokeWidth={2.5}
          strokeLinecap="round"
          strokeLinejoin="round"
          initial={{ pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 0.4, delay: 0.2 }}
        />
      </svg>
      {/* Song title if present */}
      {detail && (
        <div style={{
          fontSize: 7,
          fontWeight: 500,
          color: 'var(--personality-accent)',
          textAlign: 'center',
          maxWidth: size - 6,
          lineHeight: 1.1,
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          opacity: 0.8,
        }}>
          {detail}
        </div>
      )}
    </motion.div>
  )
}

/* -- Lights: glowing circle with color + brightness ----------------------- */
function LightResolvedWidget({ size, detail }: { size: number; detail?: string }) {
  // Try to extract color from detail string (e.g., "Lights set to red at 80%")
  // Fallback to personality accent
  return (
    <motion.div
      initial={{ scale: 0.6, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ duration: 0.4, ease: 'easeOut' }}
      style={{
        width: size,
        height: size,
        borderRadius: '50%',
        background: 'rgba(var(--personality-accent-rgb), 0.08)',
        border: '1px solid rgba(var(--personality-accent-rgb), 0.2)',
        boxShadow: '0 0 16px rgba(var(--personality-accent-rgb), 0.3), inset 0 0 12px rgba(var(--personality-accent-rgb), 0.1)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        position: 'relative',
      }}
    >
      {/* Inner glow circle */}
      <motion.div
        style={{
          width: size * 0.5,
          height: size * 0.5,
          borderRadius: '50%',
          background: 'rgba(var(--personality-accent-rgb), 0.4)',
          filter: 'blur(3px)',
        }}
        animate={{ scale: [0.8, 1.1, 0.8], opacity: [0.4, 0.7, 0.4] }}
        transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
      />
      {/* Bulb icon center */}
      <svg
        width={size * 0.32}
        height={size * 0.32}
        viewBox="0 0 24 24"
        fill="var(--personality-accent)"
        style={{ position: 'absolute' }}
      >
        <path d="M9 21h6M10 17h4M12 3a6 6 0 0 1 3.7 10.7c-.5.5-.7 1.1-.7 1.8V17H9v-1.5c0-.7-.3-1.3-.7-1.8A6 6 0 0 1 12 3z" />
      </svg>
    </motion.div>
  )
}

/* -- Volume: arc showing the level ---------------------------------------- */
function VolumeResolvedWidget({ size, detail }: { size: number; detail?: string }) {
  // Try to extract volume level from detail (e.g. "Volume set to 50")
  const levelMatch = detail?.match(/(\d+)/)
  const level = levelMatch ? Math.min(100, Math.max(0, parseInt(levelMatch[1], 10))) : 50
  const fraction = level / 100

  const r = size * 0.38
  const cx = size / 2
  const cy = size / 2
  // Arc from -135deg to +135deg (270 deg sweep for full)
  const startAngle = -225 * (Math.PI / 180)
  const endAngle = 45 * (Math.PI / 180)
  const sweepAngle = startAngle + (endAngle - startAngle) * fraction

  const arcPath = (angle: number) => ({
    x: cx + r * Math.cos(angle),
    y: cy + r * Math.sin(angle),
  })

  const start = arcPath(startAngle)
  const end = arcPath(endAngle)
  const filled = arcPath(sweepAngle)
  const largeArcBg = 1
  const largeArcFill = fraction > 0.5 ? 1 : 0

  return (
    <motion.div
      initial={{ scale: 0.6, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ duration: 0.4, ease: 'easeOut' }}
      style={{
        width: size,
        height: size,
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        {/* Background arc track */}
        <path
          d={`M ${start.x} ${start.y} A ${r} ${r} 0 ${largeArcBg} 1 ${end.x} ${end.y}`}
          fill="none"
          stroke="rgba(255,255,255,0.08)"
          strokeWidth={3}
          strokeLinecap="round"
        />
        {/* Filled arc */}
        <motion.path
          d={`M ${start.x} ${start.y} A ${r} ${r} 0 ${largeArcFill} 1 ${filled.x} ${filled.y}`}
          fill="none"
          stroke="var(--personality-accent)"
          strokeWidth={3}
          strokeLinecap="round"
          initial={{ pathLength: 0, opacity: 0 }}
          animate={{ pathLength: 1, opacity: 0.85 }}
          transition={{ duration: 0.6, delay: 0.15 }}
          style={{ filter: 'drop-shadow(0 0 4px rgba(var(--personality-accent-rgb), 0.4))' }}
        />
      </svg>
      {/* Level number */}
      <div style={{
        position: 'absolute',
        fontSize: size * 0.22,
        fontWeight: 700,
        color: 'var(--personality-accent)',
        opacity: 0.85,
        fontFamily: 'ui-monospace, "SF Mono", "Cascadia Mono", monospace',
      }}>
        {level}
      </div>
    </motion.div>
  )
}

/* -- Chat/Brain/Search/Memory: speech bubble with dots -------------------- */
function ChatResolvedWidget({ size }: { size: number }) {
  return (
    <motion.div
      initial={{ scale: 0.6, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.4, ease: 'easeOut' }}
      style={{
        width: size,
        height: size * 0.75,
        borderRadius: size * 0.25,
        borderBottomLeftRadius: size * 0.08,
        background: 'rgba(var(--personality-accent-rgb), 0.1)',
        border: '1px solid rgba(var(--personality-accent-rgb), 0.2)',
        boxShadow: '0 0 10px rgba(var(--personality-accent-rgb), 0.15)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 3,
      }}
    >
      {[0, 1, 2].map(i => (
        <motion.div
          key={i}
          style={{
            width: 4,
            height: 4,
            borderRadius: '50%',
            background: 'var(--personality-accent)',
          }}
          animate={{ opacity: [0.3, 0.8, 0.3], y: [0, -2, 0] }}
          transition={{ duration: 0.8, repeat: 2, delay: i * 0.15, ease: 'easeInOut' }}
        />
      ))}
    </motion.div>
  )
}

/* -- Failed: red-tinted with X mark --------------------------------------- */
function FailedWidget({ size, detail }: { size: number; detail?: string }) {
  return (
    <motion.div
      initial={{ scale: 0.6, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ duration: 0.4, ease: 'easeOut' }}
      style={{
        width: size,
        height: size,
        borderRadius: size * 0.2,
        background: 'rgba(255, 80, 80, 0.08)',
        border: '1px solid rgba(255, 80, 80, 0.25)',
        boxShadow: '0 0 10px rgba(255, 80, 80, 0.15)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 2,
      }}
    >
      {/* X mark */}
      <svg width={size * 0.3} height={size * 0.3} viewBox="0 0 16 16" fill="none">
        <motion.path
          d="M4 4L12 12M12 4L4 12"
          stroke="#ff6b6b"
          strokeWidth={2.5}
          strokeLinecap="round"
          initial={{ pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 0.3 }}
        />
      </svg>
      {detail && (
        <div style={{
          fontSize: 7,
          fontWeight: 500,
          color: '#ff6b6b',
          textAlign: 'center',
          maxWidth: size - 6,
          lineHeight: 1.1,
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          opacity: 0.7,
        }}>
          {detail}
        </div>
      )}
    </motion.div>
  )
}
