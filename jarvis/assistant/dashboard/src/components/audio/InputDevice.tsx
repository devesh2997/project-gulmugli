/**
 * InputDevice — a pill-shaped chip for an audio input (microphone) device.
 *
 * Active device gets a personality-accent glow and subtle pulsing border.
 * Each device type has a unique icon. Tap to PIN it as the active override.
 *
 * Mirrors OutputDevice's selection-source / availability rendering:
 *  - `selectionSource` badge (Pinned / Auto / Fallback) on the active row.
 *  - `available === false` → 50% opacity + strike-through, pointer disabled.
 *  - `label` (friendly name from the config priority list) shown when set.
 */

import { motion } from 'framer-motion'
import type {
  AudioDevice,
  AudioOutputType,
  AudioSelectionSource,
} from '../../types/assistant'

interface Props {
  device: AudioDevice
  onSelect: () => void
}

/** Tiny inline SVG icons per device type */
function DeviceIcon({ type, active }: { type: AudioOutputType; active: boolean }) {
  const color = active ? 'var(--personality-accent)' : 'var(--text-tertiary)'
  const props = { width: 16, height: 16, viewBox: '0 0 24 24', fill: 'none', stroke: color, strokeWidth: 1.8, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const }

  switch (type) {
    case 'headphones':
      return (
        <svg {...props}>
          <path d="M3 18v-6a9 9 0 0 1 18 0v6" />
          <path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z" />
        </svg>
      )
    case 'bluetooth':
      return (
        <svg {...props}>
          <polyline points="6.5 6.5 17.5 17.5 12 23 12 1 17.5 6.5 6.5 17.5" />
        </svg>
      )
    case 'hdmi':
      return (
        <svg {...props}>
          <rect x="2" y="7" width="20" height="10" rx="2" />
          <path d="M6 11h2M10 11h2M14 11h2M18 11h0" />
        </svg>
      )
    case 'airplay':
      return (
        <svg {...props}>
          <path d="M5 17H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2h-1" />
          <polygon points="12 15 17 21 7 21 12 15" />
        </svg>
      )
    case 'usb':
      return (
        <svg {...props}>
          <circle cx="10" cy="18" r="2" />
          <circle cx="18" cy="14" r="2" />
          <path d="M12 2v10l4-2" />
          <path d="M12 12l-2 6" />
          <path d="M12 8l6 4" />
          <circle cx="12" cy="2" r="1" />
        </svg>
      )
    // 'speaker' and default (incl. 'unknown') both fall back to the
    // microphone glyph. PulseAudio often types capture sinks as
    // 'speaker', which is wrong for the input side — and the
    // existing OutputDevice default is a megaphone, also wrong here.
    case 'speaker':
    default:
      return (
        <svg {...props}>
          <rect x="9" y="2" width="6" height="11" rx="3" />
          <path d="M5 10v2a7 7 0 0 0 14 0v-2" />
          <line x1="12" y1="19" x2="12" y2="22" />
          <line x1="8" y1="22" x2="16" y2="22" />
        </svg>
      )
  }
}

/** Compact 10px badge showing where the active selection came from. */
function SelectionSourceBadge({ source }: { source: AudioSelectionSource | undefined }) {
  if (!source) return null
  const config: Record<NonNullable<AudioSelectionSource>, { glyph: string; label: string; color: string }> = {
    override: { glyph: '\u{1F4CC}', label: 'pinned',   color: 'var(--personality-accent)' },
    priority: { glyph: '✓',    label: 'auto',     color: 'var(--text-tertiary)' },
    default:  { glyph: '↓',    label: 'fallback', color: 'var(--text-secondary)' },
  }
  const c = config[source]
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 3,
      fontSize: 10, fontWeight: 600, letterSpacing: 2,
      textTransform: 'uppercase' as const,
      color: c.color, whiteSpace: 'nowrap' as const,
    }}>
      <span style={{ fontSize: 10, letterSpacing: 0 }}>{c.glyph}</span>
      {c.label}
    </span>
  )
}

export function InputDevice({ device, onSelect }: Props) {
  const available = device.available !== false  // default true for back-compat
  const disabled = !available

  return (
    <motion.button
      onClick={disabled ? undefined : onSelect}
      disabled={disabled}
      whileHover={disabled ? undefined : { scale: 1.03 }}
      whileTap={disabled ? undefined : { scale: 0.95 }}
      animate={{
        borderColor: device.active
          ? 'rgba(var(--personality-accent-rgb), 0.5)'
          : 'var(--border-subtle)',
        boxShadow: device.active
          ? '0 0 16px rgba(var(--personality-accent-rgb), 0.15), 0 2px 8px rgba(0,0,0,0.2)'
          : '0 1px 4px rgba(0,0,0,0.15)',
        opacity: disabled ? 0.5 : 1,
      }}
      transition={{ type: 'spring', stiffness: 400, damping: 28 }}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: '10px 14px',
        borderRadius: 16,
        background: device.active
          ? 'rgba(var(--personality-accent-rgb), 0.06)'
          : 'transparent',
        border: '1.5px solid var(--border-subtle)',
        cursor: disabled ? 'not-allowed' : 'pointer',
        width: '100%',
      }}
      aria-disabled={disabled}
    >
      <DeviceIcon type={device.type} active={device.active} />
      <span style={{
        fontSize: 12, fontWeight: device.active ? 600 : 400,
        color: device.active ? 'var(--personality-accent)' : 'var(--text-secondary)',
        flex: 1, textAlign: 'left',
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        textDecoration: disabled ? 'line-through' : 'none',
      }}>
        {device.label || device.name}
      </span>

      {/* Selection-source badge — only meaningful when active */}
      {device.active && <SelectionSourceBadge source={device.selectionSource} />}

      {/* Active indicator dot */}
      {device.active && (
        <motion.div
          layoutId="active-input-dot"
          style={{
            width: 6, height: 6, borderRadius: 3,
            background: 'var(--personality-accent)',
            boxShadow: '0 0 8px var(--personality-accent)',
          }}
          transition={{ type: 'spring', stiffness: 500, damping: 25 }}
        />
      )}
    </motion.button>
  )
}
