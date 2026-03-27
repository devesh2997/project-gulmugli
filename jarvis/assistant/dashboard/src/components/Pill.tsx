/**
 * Pill — contextual animated capsule badge.
 * Each intent type has its own rich icon animation (music bounces,
 * bulb flickers then glows, search scans, brain thinks, etc.).
 * Icon IS the communication — text labels only appear briefly for
 * done status with a detail message.
 */

import { motion } from 'framer-motion'
import type { IntentIcon, IntentStatus } from '../types/assistant'
import { AnimatedIcon } from './PillIcons'

export interface PillProps {
  icon?: IntentIcon | string
  label: string
  status?: IntentStatus
  detail?: string
  accentColor?: string
  onClick?: () => void
  children?: React.ReactNode
}

/* Color tints per icon for the subtle background glow */
const ICON_TINTS: Record<string, string> = {
  music:       '168, 85, 247',   // purple
  bulb:        '250, 204, 21',   // warm yellow
  volume:      '59, 130, 246',   // blue
  brain:       '129, 140, 248',  // indigo
  personality: '236, 72, 153',   // pink
  search:      '34, 197, 94',    // green
  general:     '148, 163, 184',  // slate
  timer:       '251, 146, 60',   // orange
}

/* Resolve the animate value based on status */
function getPillAnimate(status?: IntentStatus): Record<string, unknown> {
  if (status === 'processing') {
    return { scale: [1, 1.02, 1], opacity: 1 }
  }
  if (status === 'failed') {
    return { x: [0, -4, 4, -3, 3, 0], scale: 1, opacity: 1 }
  }
  return { scale: 1, opacity: 1 }
}

function getPillTransition(status?: IntentStatus) {
  if (status === 'processing') {
    return { duration: 1.8, repeat: Infinity, ease: 'easeInOut' as const }
  }
  if (status === 'failed') {
    return { duration: 0.4 }
  }
  return { duration: 0.3 }
}

export function Pill({ icon, label, status, detail, accentColor, onClick, children }: PillProps) {
  const accent = accentColor ?? 'var(--personality-accent, var(--accent-primary))'
  const tintRgb = icon ? ICON_TINTS[icon] ?? ICON_TINTS.general : null
  const isFailed = status === 'failed'
  const isDone = status === 'done'
  const showLabel = !icon || (isDone && detail) || children

  /* Background glow based on icon + status */
  const bgColor = isFailed
    ? 'rgba(239, 68, 68, 0.12)'
    : tintRgb
      ? `rgba(${tintRgb}, ${status === 'processing' ? 0.15 : 0.08})`
      : 'rgba(255, 255, 255, 0.05)'

  const borderColor = isFailed
    ? 'rgba(239, 68, 68, 0.25)'
    : tintRgb
      ? `rgba(${tintRgb}, ${status === 'processing' ? 0.25 : 0.1})`
      : 'rgba(255, 255, 255, 0.08)'

  return (
    <motion.div
      layout
      initial={{ scale: 0.8, opacity: 0 }}
      animate={getPillAnimate(status)}
      exit={{ scale: 0.7, opacity: 0 }}
      transition={getPillTransition(status)}
      onClick={onClick}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: showLabel ? 6 : 0,
        height: 36,
        padding: showLabel ? '6px 12px' : '6px 10px',
        borderRadius: 'var(--radius-lg)',
        background: bgColor,
        border: `1px solid ${borderColor}`,
        backdropFilter: 'blur(8px)',
        WebkitBackdropFilter: 'blur(8px)',
        cursor: onClick ? 'pointer' : 'default',
        userSelect: 'none',
        flexShrink: 0,
        color: isFailed ? 'var(--accent-error)' : accent,
        boxShadow: status === 'processing' && tintRgb
          ? `0 0 12px rgba(${tintRgb}, 0.2)`
          : isDone && tintRgb
            ? `0 0 8px rgba(${tintRgb}, 0.15)`
            : 'none',
        transition: 'box-shadow 0.3s, background 0.3s, border-color 0.3s',
      }}
    >
      {/* Animated icon */}
      {icon && (
        <span style={{ display: 'flex', alignItems: 'center', flexShrink: 0, opacity: isFailed ? 1 : 0.85 }}>
          <AnimatedIcon icon={icon} status={status} />
        </span>
      )}

      {/* children (NowPlayingPill) or detail text on done */}
      {children
        ? children
        : showLabel && (
            <motion.span
              initial={isDone ? { opacity: 0, x: -4 } : {}}
              animate={{ opacity: 0.85, x: 0 }}
              style={{
                fontSize: '0.72rem',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                maxWidth: 140,
              }}
            >
              {isDone && detail ? detail : label}
            </motion.span>
          )
      }
    </motion.div>
  )
}
