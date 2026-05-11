/**
 * OutputDevice — a pill-shaped chip for an audio output device.
 *
 * Active device gets a personality-accent glow and subtle pulsing border.
 * Each device type has a unique icon. Tap to PIN it as the active override
 * (the backend will treat this as an explicit user choice).
 *
 * Renders three additional pieces of state next to the active dot:
 *  - `selectionSource` badge (Pinned / Auto / Fallback) — provenance of the
 *    active selection, only meaningful for the active row.
 *  - `available === false` → chip rendered at 50% opacity with a strike-
 *    through name and pointer disabled.
 *  - `label` (friendly name from the config priority list) → shown as a
 *    small caption under the device name when distinct.
 *
 * Feels like selecting an AirPlay device — not a radio button list.
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
    case 'speaker':
      return (
        <svg {...props}>
          <rect x="4" y="2" width="16" height="20" rx="3" />
          <circle cx="12" cy="14" r="4" />
          <circle cx="12" cy="6" r="1.5" />
        </svg>
      )
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
    default:
      return (
        <svg {...props}>
          <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
          <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
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

export function OutputDevice({ device, onSelect }: Props) {
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
          layoutId="active-output-dot"
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
