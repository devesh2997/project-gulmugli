/**
 * ThoughtRenderer — dispatches to personality-specific thought visuals.
 *
 * Each personality renders thoughts differently:
 *   orb        → Energy Wisps (glowing translucent circles with trailing particles)
 *   pixel      → Pixel Clouds (jittering 3x3 rect clusters)
 *   light      → Light Wisps (SVG stroke arc with glow head)
 *   caricature → Thought Bubbles (classic cartoon cloud trail)
 */

import { motion } from 'framer-motion'
import type { AvatarType, IntentStatus } from '../../types/assistant'
import { ThoughtIcon } from './ThoughtIcons'

interface RendererProps {
  avatarType: AvatarType
  icon: string
  status: IntentStatus
  size: number
}

export function ThoughtRenderer({ avatarType, icon, status, size }: RendererProps) {
  switch (avatarType) {
    case 'orb': return <OrbWisp icon={icon} status={status} size={size} />
    case 'pixel': return <PixelCloud icon={icon} status={status} size={size} />
    case 'light': return <LightWisp icon={icon} status={status} size={size} />
    case 'caricature': return <ThoughtBubble icon={icon} status={status} size={size} />
    default: return <OrbWisp icon={icon} status={status} size={size} />
  }
}

type VariantProps = Omit<RendererProps, 'avatarType'>

/* ── Orb: Energy Wisps ───────────────────────────────────────── */
function OrbWisp({ icon, status, size }: VariantProps) {
  const s = Math.max(size, 14)
  const isProcessing = status === 'processing'
  return (
    <motion.div
      style={{ width: s, height: s, position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
      animate={isProcessing ? { scale: [0.9, 1.1, 0.9], opacity: [0.3, 0.5, 0.3] } : { scale: 1, opacity: 0.45 }}
      transition={isProcessing ? { duration: 2.4, repeat: Infinity, ease: 'easeInOut' } : { duration: 0.3 }}
    >
      {/* Main wisp glow */}
      <div style={{
        position: 'absolute', inset: 0, borderRadius: '50%',
        background: 'rgba(var(--personality-accent-rgb), 0.4)',
        filter: 'blur(4px)',
      }} />
      {/* Core circle */}
      <div style={{
        position: 'absolute', inset: '15%', borderRadius: '50%',
        background: 'rgba(var(--personality-accent-rgb), 0.6)',
      }} />
      {/* Trailing particles */}
      {[0, 1, 2].map(i => (
        <motion.div
          key={i}
          style={{
            position: 'absolute', width: s * 0.22, height: s * 0.22, borderRadius: '50%',
            background: 'rgba(var(--personality-accent-rgb), 0.3)',
            filter: 'blur(2px)',
          }}
          animate={{
            x: [Math.cos(i * 2.1) * s * 0.3, Math.cos(i * 2.1 + 1) * s * 0.35, Math.cos(i * 2.1) * s * 0.3],
            y: [Math.sin(i * 2.1) * s * 0.3, Math.sin(i * 2.1 + 1) * s * 0.35, Math.sin(i * 2.1) * s * 0.3],
          }}
          transition={{ duration: 3 + i * 0.4, repeat: Infinity, ease: 'easeInOut' }}
        />
      ))}
      {/* Icon silhouette */}
      <span style={{ position: 'relative', zIndex: 1, opacity: 0.3, color: 'var(--personality-accent)', display: 'flex' }}>
        <ThoughtIcon icon={icon} status={status} />
      </span>
    </motion.div>
  )
}

/* ── Pixel: Pixel Clouds ─────────────────────────────────────── */
function PixelCloud({ icon, status, size }: VariantProps) {
  const s = Math.max(size, 14)
  const px = 3
  // 5 pixels in a loose cluster
  const offsets = [
    { x: 0, y: 0 }, { x: px + 1, y: -1 }, { x: -(px + 1), y: 1 },
    { x: 1, y: px + 1 }, { x: -(px), y: -(px) },
  ]
  const isProcessing = status === 'processing'
  return (
    <motion.div style={{
      width: s, height: s, position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center',
      imageRendering: 'pixelated' as any,
    }}>
      {offsets.map((off, i) => (
        <motion.div
          key={i}
          style={{
            position: 'absolute', width: px, height: px,
            background: 'rgba(var(--personality-accent-rgb), 0.5)',
          }}
          initial={{ x: (Math.random() - 0.5) * s, y: (Math.random() - 0.5) * s, opacity: 0 }}
          animate={{
            x: off.x + (isProcessing ? (Math.random() - 0.5) * 2 : 0),
            y: off.y + (isProcessing ? (Math.random() - 0.5) * 2 : 0),
            opacity: 1,
          }}
          transition={{ type: 'spring', stiffness: 200, damping: 12, delay: i * 0.05 }}
        />
      ))}
      <span style={{ position: 'relative', zIndex: 1, opacity: 0.3, color: 'var(--personality-accent)', display: 'flex' }}>
        <ThoughtIcon icon={icon} status={status} />
      </span>
    </motion.div>
  )
}

/* ── Light: Light Wisps ──────────────────────────────────────── */
function LightWisp({ icon, status, size }: VariantProps) {
  const s = Math.max(size, 14)
  const r = s * 0.4
  const isProcessing = status === 'processing'
  return (
    <motion.div style={{ width: s, height: s, position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <svg width={s} height={s} viewBox={`0 0 ${s} ${s}`} style={{ position: 'absolute', inset: 0 }}>
        {/* Comet-tail arc */}
        <motion.path
          d={`M ${s * 0.2} ${s * 0.5} Q ${s * 0.5} ${s * 0.15}, ${s * 0.8} ${s * 0.5}`}
          stroke="rgba(var(--personality-accent-rgb), 0.35)"
          strokeWidth={1.5}
          fill="none"
          strokeLinecap="round"
          initial={{ pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 0.6, ease: 'easeOut' }}
        />
        {/* Glow head */}
        <motion.circle
          cx={s * 0.8} cy={s * 0.5} r={3}
          fill="rgba(var(--personality-accent-rgb), 0.5)"
          style={{ filter: 'blur(2px)' }}
          animate={isProcessing ? { r: [3, 4, 3], opacity: [0.4, 0.6, 0.4] } : {}}
          transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
        />
      </svg>
      <span style={{ position: 'relative', zIndex: 1, opacity: 0.3, color: 'var(--personality-accent)', display: 'flex' }}>
        <ThoughtIcon icon={icon} status={status} />
      </span>
    </motion.div>
  )
}

/* ── Caricature: Thought Bubbles ─────────────────────────────── */
function ThoughtBubble({ icon, status, size }: VariantProps) {
  const s = Math.max(size, 14)
  const isProcessing = status === 'processing'
  // Trail: 3 circles decreasing in size from thought to avatar
  const trail = [
    { r: s * 0.14, x: s * 0.25, y: s * 0.75, delay: 0.2 },
    { r: s * 0.1, x: s * 0.15, y: s * 0.85, delay: 0.1 },
    { r: s * 0.06, x: s * 0.08, y: s * 0.92, delay: 0 },
  ]
  return (
    <motion.div style={{ width: s, height: s, position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      {/* Main cloud */}
      <motion.div
        style={{
          position: 'absolute', top: '5%', left: '15%', right: '5%', bottom: '35%',
          borderRadius: '50% 50% 50% 30%',
          background: 'rgba(var(--personality-accent-rgb), 0.12)',
          border: '1px solid rgba(var(--personality-accent-rgb), 0.2)',
        }}
        animate={isProcessing ? { rotate: [-2, 2, -2], scale: [0.97, 1.03, 0.97] } : {}}
        transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
      />
      {/* Trail circles */}
      {trail.map((t, i) => (
        <motion.div
          key={i}
          style={{
            position: 'absolute', left: t.x, top: t.y,
            width: t.r * 2, height: t.r * 2, borderRadius: '50%',
            background: 'rgba(var(--personality-accent-rgb), 0.15)',
            border: '1px solid rgba(var(--personality-accent-rgb), 0.12)',
          }}
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ type: 'spring', stiffness: 400, damping: 15, delay: t.delay }}
        />
      ))}
      <span style={{ position: 'relative', zIndex: 1, opacity: 0.3, color: 'var(--personality-accent)', display: 'flex' }}>
        <ThoughtIcon icon={icon} status={status} />
      </span>
    </motion.div>
  )
}
