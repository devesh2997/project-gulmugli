/**
 * ThoughtIcons — rich, expressive per-intent-type icons for thought manifestations.
 *
 * Each icon is contextual to what the assistant is actually doing:
 *   music  → animated equalizer bars that pulse
 *   bulb   → lightbulb that glows with the actual target color
 *   volume → sound waves emanating outward
 *   brain  → neural sparks connecting
 *   search → scanning beam sweep
 *   personality → morphing shape
 *   timer  → circular countdown
 *   general → rotating rings
 *
 * Icons are 24px and use personality accent color by default.
 * Processing state triggers active animations. Done = bright flash. Failed = red.
 */

// @ts-nocheck — Framer Motion's strict typing rejects valid animate objects

import { motion, type TargetAndTransition } from 'framer-motion'
import type { IntentStatus } from '../../types/assistant'

const anim = (v: Record<string, unknown>): TargetAndTransition => v as TargetAndTransition

type IconProps = { status?: IntentStatus }

const SIZE = 24
const VB = '0 0 24 24'
const STROKE = 'currentColor'

/* ── Music: Animated equalizer bars ─────────────────────────────── */
function MusicIcon({ status }: IconProps) {
  const isProcessing = status === 'processing'
  const isDone = status === 'done'
  // 5 bars at different heights, animated like a graphic equalizer
  const bars = [
    { x: 3, baseH: 8, animH: [8, 16, 10, 14, 8], delay: 0 },
    { x: 7, baseH: 12, animH: [12, 6, 14, 8, 12], delay: 0.1 },
    { x: 11, baseH: 16, animH: [16, 10, 6, 14, 16], delay: 0.05 },
    { x: 15, baseH: 10, animH: [10, 14, 18, 6, 10], delay: 0.15 },
    { x: 19, baseH: 6, animH: [6, 12, 8, 16, 6], delay: 0.08 },
  ]

  return (
    <svg viewBox={VB} width={SIZE} height={SIZE}>
      {bars.map((bar, i) => (
        <motion.rect
          key={i}
          x={bar.x} width={2.5} rx={1.25}
          fill={isDone ? '#4ade80' : STROKE}
          animate={isProcessing ? {
            height: bar.animH,
            y: bar.animH.map(h => 24 - h),
          } : {
            height: bar.baseH,
            y: 24 - bar.baseH,
          }}
          transition={isProcessing ? {
            duration: 0.8, repeat: Infinity, ease: 'easeInOut', delay: bar.delay,
          } : { duration: 0.3 }}
        />
      ))}
    </svg>
  )
}

/* ── Bulb: Glowing lightbulb ────────────────────────────────────── */
function BulbIcon({ status }: IconProps) {
  const isProcessing = status === 'processing'
  const isDone = status === 'done'
  return (
    <motion.svg viewBox={VB} width={SIZE} height={SIZE}>
      {/* Glow halo behind the bulb when processing */}
      {isProcessing && (
        <motion.circle
          cx="12" cy="10" r="9"
          fill="currentColor"
          animate={{ opacity: [0.05, 0.15, 0.05], scale: [0.8, 1.1, 0.8] }}
          transition={{ duration: 1.5, repeat: Infinity, ease: 'easeInOut' }}
          style={{ filter: 'blur(3px)' }}
        />
      )}
      {/* Bulb body */}
      <motion.path
        d="M9 21h6M10 17h4M12 3a6 6 0 0 1 3.7 10.7c-.5.5-.7 1.1-.7 1.8V17H9v-1.5c0-.7-.3-1.3-.7-1.8A6 6 0 0 1 12 3z"
        stroke={STROKE} strokeWidth={1.8}
        fill={isDone ? 'currentColor' : 'none'}
        strokeLinecap="round" strokeLinejoin="round"
        animate={isProcessing ? { opacity: [0.5, 1, 0.5] } : { opacity: 1 }}
        transition={isProcessing ? { duration: 1.2, repeat: Infinity } : {}}
      />
      {/* Light rays when done */}
      {isDone && [0, 60, 120, 180, 240, 300].map((angle, i) => (
        <motion.line
          key={angle}
          x1={12 + Math.cos(angle * Math.PI / 180) * 8}
          y1={10 + Math.sin(angle * Math.PI / 180) * 8}
          x2={12 + Math.cos(angle * Math.PI / 180) * 11}
          y2={10 + Math.sin(angle * Math.PI / 180) * 11}
          stroke="currentColor" strokeWidth={1.5} strokeLinecap="round"
          initial={{ opacity: 0, pathLength: 0 }}
          animate={{ opacity: [0, 1, 0], pathLength: [0, 1, 0] }}
          transition={{ duration: 0.6, delay: i * 0.05 }}
        />
      ))}
    </motion.svg>
  )
}

/* ── Volume: Sound waves emanating ──────────────────────────────── */
function VolumeIcon({ status }: IconProps) {
  const isProcessing = status === 'processing'
  return (
    <svg viewBox={VB} width={SIZE} height={SIZE}>
      {/* Speaker cone */}
      <path
        d="M6 9h2l4-4v14l-4-4H6a1 1 0 0 1-1-1v-4a1 1 0 0 1 1-1z"
        fill={status === 'done' ? STROKE : 'none'}
        stroke={STROKE} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round"
      />
      {/* Sound waves */}
      {[0, 1, 2].map(i => (
        <motion.path
          key={i}
          d={`M ${15 + i * 2.5} ${8 - i * 1.5} a ${4 + i * 2} ${4 + i * 2} 0 0 1 0 ${8 + i * 3}`}
          stroke={STROKE} strokeWidth={1.5} fill="none" strokeLinecap="round"
          animate={isProcessing ? {
            opacity: [0, 0.8, 0],
            pathLength: [0, 1, 0],
          } : { opacity: 0.4, pathLength: 1 }}
          transition={isProcessing ? {
            duration: 1.2, repeat: Infinity, delay: i * 0.25, ease: 'easeOut',
          } : { duration: 0.3 }}
        />
      ))}
    </svg>
  )
}

/* ── Brain/Chat: Neural sparks ──────────────────────────────────── */
function BrainIcon({ status }: IconProps) {
  const isProcessing = status === 'processing'
  // Three dots that connect with lines, simulating neural activity
  const nodes = [
    { cx: 7, cy: 8 }, { cx: 17, cy: 8 }, { cx: 12, cy: 17 },
  ]
  const connections = [
    { x1: 7, y1: 8, x2: 17, y2: 8 },
    { x1: 17, y1: 8, x2: 12, y2: 17 },
    { x1: 12, y1: 17, x2: 7, y2: 8 },
  ]
  return (
    <svg viewBox={VB} width={SIZE} height={SIZE}>
      {/* Connection lines */}
      {connections.map((c, i) => (
        <motion.line
          key={`c${i}`}
          x1={c.x1} y1={c.y1} x2={c.x2} y2={c.y2}
          stroke={STROKE} strokeWidth={1} strokeLinecap="round"
          animate={isProcessing ? {
            opacity: [0.1, 0.6, 0.1],
            strokeWidth: [0.5, 1.5, 0.5],
          } : { opacity: 0.3 }}
          transition={isProcessing ? {
            duration: 1.2, repeat: Infinity, delay: i * 0.3, ease: 'easeInOut',
          } : {}}
        />
      ))}
      {/* Neural nodes */}
      {nodes.map((n, i) => (
        <motion.circle
          key={`n${i}`}
          cx={n.cx} cy={n.cy} r={2.5}
          fill={STROKE}
          animate={isProcessing ? {
            r: [2, 3.5, 2],
            opacity: [0.4, 1, 0.4],
          } : { r: 2.5, opacity: 0.6 }}
          transition={isProcessing ? {
            duration: 0.8, repeat: Infinity, delay: i * 0.2,
          } : { duration: 0.3 }}
        />
      ))}
      {/* Spark traveling along connections when processing */}
      {isProcessing && connections.map((c, i) => (
        <motion.circle
          key={`s${i}`}
          r={1.5} fill={STROKE}
          animate={{
            cx: [c.x1, c.x2],
            cy: [c.y1, c.y2],
            opacity: [0, 1, 0],
          }}
          transition={{
            duration: 0.6, repeat: Infinity, delay: i * 0.4 + 0.1,
            ease: 'easeInOut',
          }}
        />
      ))}
    </svg>
  )
}

/* ── Search: Scanning beam ──────────────────────────────────────── */
function SearchIcon({ status }: IconProps) {
  const isProcessing = status === 'processing'
  return (
    <svg viewBox={VB} width={SIZE} height={SIZE}>
      {/* Magnifying glass */}
      <circle cx="10" cy="10" r="6" stroke={STROKE} strokeWidth={1.8} fill="none" />
      <motion.line
        x1="15" y1="15" x2="21" y2="21"
        stroke={STROKE} strokeWidth={2} strokeLinecap="round"
      />
      {/* Scanning sweep inside the glass */}
      {isProcessing && (
        <motion.line
          x1="10" y1="4.5" x2="10" y2="15.5"
          stroke={STROKE} strokeWidth={1} strokeLinecap="round"
          animate={{ x1: [5, 15, 5], x2: [5, 15, 5], opacity: [0.1, 0.5, 0.1] }}
          transition={{ duration: 1.5, repeat: Infinity, ease: 'easeInOut' }}
        />
      )}
    </svg>
  )
}

/* ── Personality: Morphing shape ─────────────────────────────────── */
function PersonalityIcon({ status }: IconProps) {
  const isProcessing = status === 'processing'
  return (
    <motion.svg viewBox={VB} width={SIZE} height={SIZE}>
      {/* Morphing face outline */}
      <motion.circle
        cx="12" cy="12" r="9"
        stroke={STROKE} strokeWidth={1.5} fill="none"
        animate={isProcessing ? {
          rx: [9, 7, 9], ry: [9, 11, 9],
        } : {}}
        transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
      />
      {/* Eyes */}
      <motion.circle cx="9" cy="10" r={1.5} fill={STROKE}
        animate={isProcessing ? { cy: [10, 9, 10] } : {}}
        transition={{ duration: 1, repeat: Infinity }}
      />
      <motion.circle cx="15" cy="10" r={1.5} fill={STROKE}
        animate={isProcessing ? { cy: [10, 9, 10] } : {}}
        transition={{ duration: 1, repeat: Infinity, delay: 0.1 }}
      />
      {/* Smile */}
      <motion.path
        d="M9 15c1 1.5 5 1.5 6 0"
        stroke={STROKE} strokeWidth={1.5} fill="none" strokeLinecap="round"
      />
    </motion.svg>
  )
}

/* ── Timer: Circular countdown ──────────────────────────────────── */
function TimerIcon({ status }: IconProps) {
  const isProcessing = status === 'processing'
  return (
    <svg viewBox={VB} width={SIZE} height={SIZE}>
      {/* Clock face */}
      <circle cx="12" cy="13" r="9" stroke={STROKE} strokeWidth={1.5} fill="none" />
      {/* Top nub */}
      <line x1="12" y1="1" x2="12" y2="4" stroke={STROKE} strokeWidth={2} strokeLinecap="round" />
      {/* Hands */}
      <motion.line
        x1="12" y1="13" x2="12" y2="8"
        stroke={STROKE} strokeWidth={1.5} strokeLinecap="round"
        animate={isProcessing ? { rotate: [0, 360] } : {}}
        transition={isProcessing ? { duration: 4, repeat: Infinity, ease: 'linear' } : {}}
        style={{ transformOrigin: '12px 13px' }}
      />
      <motion.line
        x1="12" y1="13" x2="15" y2="13"
        stroke={STROKE} strokeWidth={1.5} strokeLinecap="round"
        animate={isProcessing ? { rotate: [0, 360] } : {}}
        transition={isProcessing ? { duration: 1, repeat: Infinity, ease: 'linear' } : {}}
        style={{ transformOrigin: '12px 13px' }}
      />
    </svg>
  )
}

/* ── General: Rotating rings ────────────────────────────────────── */
function GeneralIcon({ status }: IconProps) {
  const isProcessing = status === 'processing'
  return (
    <motion.svg viewBox={VB} width={SIZE} height={SIZE}
      animate={isProcessing ? { rotate: 360 } : {}}
      transition={isProcessing ? { duration: 3, repeat: Infinity, ease: 'linear' } : {}}
    >
      <circle cx="12" cy="12" r="4" stroke={STROKE} strokeWidth={1.8} fill="none" />
      <circle cx="12" cy="12" r="9" stroke={STROKE} strokeWidth={1} fill="none"
        strokeDasharray="5 5" opacity={0.5} />
    </motion.svg>
  )
}

/* ── Memory: Database/brain recall ──────────────────────────────── */
function MemoryIcon({ status }: IconProps) {
  const isProcessing = status === 'processing'
  return (
    <svg viewBox={VB} width={SIZE} height={SIZE}>
      {/* Stacked discs (database) */}
      {[6, 12, 18].map((cy, i) => (
        <motion.ellipse
          key={cy} cx="12" cy={cy} rx="8" ry="3"
          stroke={STROKE} strokeWidth={1.5} fill="none"
          animate={isProcessing ? {
            opacity: [0.3, 1, 0.3],
          } : { opacity: 0.6 }}
          transition={isProcessing ? {
            duration: 1, repeat: Infinity, delay: i * 0.2,
          } : {}}
        />
      ))}
      {/* Vertical connecting lines */}
      <line x1="4" y1="6" x2="4" y2="18" stroke={STROKE} strokeWidth={1.5} />
      <line x1="20" y1="6" x2="20" y2="18" stroke={STROKE} strokeWidth={1.5} />
    </svg>
  )
}

const ICON_MAP: Record<string, React.FC<IconProps>> = {
  music: MusicIcon,
  bulb: BulbIcon,
  volume: VolumeIcon,
  brain: BrainIcon,
  personality: PersonalityIcon,
  search: SearchIcon,
  general: GeneralIcon,
  timer: TimerIcon,
  memory: MemoryIcon,
}

export function ThoughtIcon({ icon, status }: { icon: string; status?: IntentStatus }) {
  const Component = ICON_MAP[icon] ?? GeneralIcon
  return <Component status={status} />
}
