/**
 * ThoughtIcons — smaller versions of PillIcons for thought manifestations.
 * Rendered at 12px with lower opacity (they sit inside the thought visual).
 */

// @ts-nocheck — Framer Motion's strict typing rejects valid animate objects

import { motion, type TargetAndTransition } from 'framer-motion'
import type { IntentStatus } from '../../types/assistant'

const anim = (v: Record<string, unknown>): TargetAndTransition => v as TargetAndTransition

type IconProps = { status?: IntentStatus }

const SIZE = 12
const VB = '0 0 24 24'
const STROKE = 'currentColor'

function MusicIcon({ status }: IconProps) {
  const bounce = status === 'processing'
    ? { y: [0, -2, 0, 1, 0], transition: { duration: 0.5, repeat: Infinity, ease: 'easeInOut' } }
    : {}
  return (
    <motion.svg viewBox={VB} width={SIZE} height={SIZE} animate={anim(bounce)}>
      <motion.path d="M9 18V5l12-2v13" stroke={STROKE} strokeWidth={2} fill="none" strokeLinecap="round" strokeLinejoin="round" />
      <motion.circle cx="7" cy="18" r="2.5" fill={STROKE} />
      <motion.circle cx="19" cy="16" r="2.5" fill={STROKE} />
    </motion.svg>
  )
}

function BulbIcon({ status }: IconProps) {
  return (
    <motion.svg viewBox={VB} width={SIZE} height={SIZE}>
      <motion.path
        d="M9 21h6M12 3a6 6 0 0 1 3.7 10.7c-.5.5-.7 1.1-.7 1.8V17H9v-1.5c0-.7-.3-1.3-.7-1.8A6 6 0 0 1 12 3z"
        stroke={STROKE} strokeWidth={2} fill={status === 'done' ? 'currentColor' : 'none'} strokeLinecap="round" strokeLinejoin="round"
        animate={status === 'processing' ? { opacity: [1, 0.3, 1], transition: { duration: 0.8, repeat: Infinity } } : {}}
      />
    </motion.svg>
  )
}

function BrainIcon({ status }: IconProps) {
  if (status === 'processing') {
    return (
      <motion.svg viewBox={VB} width={SIZE} height={SIZE}>
        {[7, 12, 17].map((cx, i) => (
          <motion.circle key={cx} cx={cx} cy="12" r="2" fill={STROKE}
            animate={{ y: [0, -2, 0], opacity: [0.4, 1, 0.4] }}
            transition={{ duration: 0.6, repeat: Infinity, delay: i * 0.15 }}
          />
        ))}
      </motion.svg>
    )
  }
  return (
    <motion.svg viewBox={VB} width={SIZE} height={SIZE}>
      <path d="M12 2C9.2 2 7 4.2 7 7c0 1.7.8 3.1 2 4.1V13h6v-1.9c1.2-1 2-2.4 2-4.1 0-2.8-2.2-5-5-5z"
        stroke={STROKE} strokeWidth={2} fill="none" strokeLinecap="round" />
    </motion.svg>
  )
}

function SearchIcon({ status }: IconProps) {
  return (
    <motion.svg viewBox={VB} width={SIZE} height={SIZE}>
      <motion.g animate={status === 'processing' ? { x: [-1, 1, -1], transition: { duration: 0.8, repeat: Infinity } } : {}}>
        <circle cx="10" cy="10" r="6" stroke={STROKE} strokeWidth={2} fill="none" />
        <path d="M15 15l5 5" stroke={STROKE} strokeWidth={2} strokeLinecap="round" />
      </motion.g>
    </motion.svg>
  )
}

function GeneralIcon({ status }: IconProps) {
  return (
    <motion.svg viewBox={VB} width={SIZE} height={SIZE}
      animate={status === 'processing' ? { rotate: 360, transition: { duration: 2, repeat: Infinity, ease: 'linear' } } : {}}>
      <circle cx="12" cy="12" r="3" stroke={STROKE} strokeWidth={2} fill="none" />
      <circle cx="12" cy="12" r="8" stroke={STROKE} strokeWidth={1.5} fill="none" strokeDasharray="4 4" />
    </motion.svg>
  )
}

const ICON_MAP: Record<string, React.FC<IconProps>> = {
  music: MusicIcon,
  bulb: BulbIcon,
  volume: GeneralIcon,
  brain: BrainIcon,
  personality: GeneralIcon,
  search: SearchIcon,
  general: GeneralIcon,
  timer: GeneralIcon,
}

export function ThoughtIcon({ icon, status }: { icon: string; status?: IntentStatus }) {
  const Component = ICON_MAP[icon] ?? GeneralIcon
  return <Component status={status} />
}
