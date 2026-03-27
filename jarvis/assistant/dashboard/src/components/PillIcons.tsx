/**
 * PillIcons — animated SVG icons per intent type.
 * Each icon has unique animations for queued/processing/done/failed states.
 * Inspired by Apple's Dynamic Island — icon IS the communication.
 */

// @ts-nocheck — Framer Motion's strict typing rejects valid animate objects
// in conditional expressions. All animations here are runtime-valid.

import { motion, type TargetAndTransition } from 'framer-motion'
import type { IntentStatus } from '../types/assistant'

// Framer Motion's strict typing rejects valid animate objects in some cases.
// This helper casts to the expected type.
const anim = (v: Record<string, unknown>): TargetAndTransition => v as TargetAndTransition

type IconProps = { status?: IntentStatus }

const SIZE = 18
const VB = '0 0 24 24'
const STROKE = 'currentColor'

/* ── Music: bouncing note ──────────────────────────────────── */
export function MusicIcon({ status }: IconProps) {
  const bounce = status === 'processing'
    ? { y: [0, -3, 0, 2, 0], transition: { duration: 0.5, repeat: Infinity, ease: 'easeInOut' } }
    : status === 'done'
      ? { scale: [1, 1.2, 1], transition: { duration: 0.4 } }
      : {}
  return (
    <motion.svg viewBox={VB} width={SIZE} height={SIZE} animate={anim(bounce)}>
      <motion.path
        d="M9 18V5l12-2v13"
        stroke={STROKE} strokeWidth={1.8} fill="none" strokeLinecap="round" strokeLinejoin="round"
      />
      <motion.circle cx="7" cy="18" r="2.5" fill={STROKE}
        animate={status === 'done' ? { scale: [1, 1.4, 1], opacity: [1, 0.5, 1] } : {}}
        transition={{ duration: 0.5 }}
      />
      <motion.circle cx="19" cy="16" r="2.5" fill={STROKE}
        animate={status === 'done' ? { scale: [1, 1.4, 1], opacity: [1, 0.5, 1] } : {}}
        transition={{ duration: 0.5, delay: 0.1 }}
      />
    </motion.svg>
  )
}

/* ── Bulb: flickering → glowing ────────────────────────────── */
export function BulbIcon({ status }: IconProps) {
  const fillColor = status === 'done' ? 'currentColor' : 'none'
  return (
    <motion.svg viewBox={VB} width={SIZE} height={SIZE}>
      <motion.path
        d="M9 21h6M12 3a6 6 0 0 1 3.7 10.7c-.5.5-.7 1.1-.7 1.8V17H9v-1.5c0-.7-.3-1.3-.7-1.8A6 6 0 0 1 12 3z"
        stroke={STROKE} strokeWidth={1.8} fill={fillColor} strokeLinecap="round" strokeLinejoin="round"
        animate={status === 'processing'
          ? { opacity: [1, 0.3, 1, 0.5, 1], transition: { duration: 0.8, repeat: Infinity } }
          : status === 'done'
            ? { filter: ['drop-shadow(0 0 0px currentColor)', 'drop-shadow(0 0 6px currentColor)', 'drop-shadow(0 0 3px currentColor)'], transition: { duration: 0.6 } }
            : {}
        }
      />
      {/* filament lines */}
      <motion.path d="M10 17v-1M14 17v-1" stroke={STROKE} strokeWidth={1.2} strokeLinecap="round"
        animate={status === 'processing' ? { opacity: [0.5, 1, 0.5] } : {}}
        transition={{ duration: 0.4, repeat: Infinity }}
      />
    </motion.svg>
  )
}

/* ── Volume: animated sound bars ───────────────────────────── */
export function VolumeIcon({ status }: IconProps) {
  const barAnim = status === 'processing'
    ? (delay: number) => ({ scaleY: [0.4, 1, 0.6, 1, 0.4], transition: { duration: 0.7, repeat: Infinity, delay } })
    : status === 'done'
      ? () => ({ scaleY: 0.7, transition: { duration: 0.3 } })
      : () => ({})
  return (
    <motion.svg viewBox={VB} width={SIZE} height={SIZE}>
      <path d="M3 9v6h4l5 5V4L7 9H3z" fill={STROKE} />
      {/* three sound bars */}
      <motion.rect x="16" y="6" width="1.8" height="12" rx="0.9" fill={STROKE}
        style={{ originY: '50%' }} animate={barAnim(0)} />
      <motion.rect x="19.5" y="8" width="1.8" height="8" rx="0.9" fill={STROKE}
        style={{ originY: '50%' }} animate={barAnim(0.15)} />
    </motion.svg>
  )
}

/* ── Brain: thinking dots → sparkle ────────────────────────── */
export function BrainIcon({ status }: IconProps) {
  if (status === 'processing') {
    return (
      <motion.svg viewBox={VB} width={SIZE} height={SIZE}>
        {[7, 12, 17].map((cx, i) => (
          <motion.circle key={cx} cx={cx} cy="12" r="2" fill={STROKE}
            animate={{ y: [0, -3, 0], opacity: [0.4, 1, 0.4] }}
            transition={{ duration: 0.6, repeat: Infinity, delay: i * 0.15 }}
          />
        ))}
      </motion.svg>
    )
  }
  if (status === 'done') {
    return (
      <motion.svg viewBox={VB} width={SIZE} height={SIZE}>
        <motion.path d="M12 2l1.5 4.5L18 8l-4.5 1.5L12 14l-1.5-4.5L6 8l4.5-1.5L12 2z"
          fill={STROKE} initial={{ scale: 0, rotate: -90 }} animate={{ scale: 1, rotate: 0 }}
          transition={{ type: 'spring', stiffness: 300, damping: 15 }}
        />
        <motion.path d="M18 14l1 3 3 1-3 1-1 3-1-3-3-1 3-1 1-3z"
          fill={STROKE} initial={{ scale: 0 }} animate={{ scale: 1 }}
          transition={{ delay: 0.2, type: 'spring', stiffness: 300 }}
        />
      </motion.svg>
    )
  }
  // queued / default: brain shape
  return (
    <motion.svg viewBox={VB} width={SIZE} height={SIZE}
      animate={status === 'queued' ? { opacity: [0.5, 1, 0.5] } : {}}
      transition={{ duration: 2, repeat: Infinity }}
    >
      <path d="M12 2C9.2 2 7 4.2 7 7c0 1.7.8 3.1 2 4.1V13h6v-1.9c1.2-1 2-2.4 2-4.1 0-2.8-2.2-5-5-5z"
        stroke={STROKE} strokeWidth={1.8} fill="none" strokeLinecap="round" />
      <path d="M9 17h6M10 21h4M12 13v4"
        stroke={STROKE} strokeWidth={1.5} fill="none" strokeLinecap="round" />
    </motion.svg>
  )
}

/* ── Personality: morphing silhouette ──────────────────────── */
export function PersonalityIcon({ status }: IconProps) {
  return (
    <motion.svg viewBox={VB} width={SIZE} height={SIZE}
      animate={status === 'processing'
        ? { rotate: [0, 10, -10, 0], transition: { duration: 0.8, repeat: Infinity } }
        : status === 'done'
          ? { scale: [1, 1.15, 1], transition: { duration: 0.4 } }
          : status === 'queued'
            ? { opacity: [0.5, 1, 0.5], transition: { duration: 2, repeat: Infinity } }
            : {}
      }
    >
      <circle cx="12" cy="8" r="4" fill={STROKE} />
      <path d="M4 21c0-4.4 3.6-8 8-8s8 3.6 8 8" fill={STROKE} />
    </motion.svg>
  )
}

/* ── Search: scanning glass → checkmark ────────────────────── */
export function SearchIcon({ status }: IconProps) {
  if (status === 'done') {
    return (
      <motion.svg viewBox={VB} width={SIZE} height={SIZE}>
        <motion.path d="M5 12l5 5L19 7"
          stroke={STROKE} strokeWidth={2.5} fill="none" strokeLinecap="round" strokeLinejoin="round"
          initial={{ pathLength: 0 }} animate={{ pathLength: 1 }}
          transition={{ duration: 0.4, ease: 'easeOut' }}
        />
      </motion.svg>
    )
  }
  return (
    <motion.svg viewBox={VB} width={SIZE} height={SIZE}>
      <motion.g
        animate={status === 'processing'
          ? { x: [-2, 2, -2], transition: { duration: 0.8, repeat: Infinity, ease: 'easeInOut' } }
          : status === 'queued'
            ? { opacity: [0.5, 1, 0.5], transition: { duration: 2, repeat: Infinity } }
            : {}
        }
      >
        <circle cx="10" cy="10" r="6" stroke={STROKE} strokeWidth={2} fill="none" />
        <path d="M15 15l5 5" stroke={STROKE} strokeWidth={2} strokeLinecap="round" />
      </motion.g>
    </motion.svg>
  )
}

/* ── General: rotating gear ────────────────────────────────── */
export function GeneralIcon({ status }: IconProps) {
  return (
    <motion.svg viewBox={VB} width={SIZE} height={SIZE}
      animate={status === 'processing'
        ? { rotate: 360, transition: { duration: 2, repeat: Infinity, ease: 'linear' } }
        : status === 'queued'
          ? { opacity: [0.5, 1, 0.5], transition: { duration: 2, repeat: Infinity } }
          : {}
      }
    >
      <path
        d="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z"
        stroke={STROKE} strokeWidth={1.8} fill="none"
      />
      <path
        d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"
        stroke={STROKE} strokeWidth={1.5} fill="none" strokeLinecap="round" strokeLinejoin="round"
      />
    </motion.svg>
  )
}

/* ── Timer ─────────────────────────────────────────────────── */
export function TimerIcon({ status }: IconProps) {
  return (
    <motion.svg viewBox={VB} width={SIZE} height={SIZE}
      animate={status === 'queued' ? { opacity: [0.5, 1, 0.5], transition: { duration: 2, repeat: Infinity } } : {}}
    >
      <circle cx="12" cy="13" r="8" stroke={STROKE} strokeWidth={1.8} fill="none" />
      <motion.path d="M12 9v4l3 2" stroke={STROKE} strokeWidth={1.8} fill="none" strokeLinecap="round"
        animate={status === 'processing'
          ? { rotate: [0, 360], transition: { duration: 2, repeat: Infinity, ease: 'linear' } }
          : {}
        }
        style={{ transformOrigin: '12px 13px' }}
      />
      <path d="M10 3h4" stroke={STROKE} strokeWidth={1.8} strokeLinecap="round" />
    </motion.svg>
  )
}

/* ── Icon resolver ─────────────────────────────────────────── */
const ICON_MAP: Record<string, React.FC<IconProps>> = {
  music:       MusicIcon,
  bulb:        BulbIcon,
  volume:      VolumeIcon,
  brain:       BrainIcon,
  personality: PersonalityIcon,
  search:      SearchIcon,
  general:     GeneralIcon,
  timer:       TimerIcon,
}

export function AnimatedIcon({ icon, status }: { icon: string; status?: IntentStatus }) {
  const Component = ICON_MAP[icon] ?? GeneralIcon
  return <Component status={status} />
}
