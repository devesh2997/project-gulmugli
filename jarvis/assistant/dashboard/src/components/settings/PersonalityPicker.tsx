/**
 * PersonalityPicker — mini avatar cards for switching personalities.
 *
 * Each personality renders as a card with a mini avatar preview based
 * on the personality's avatar style (pixel grid, orb glow, light strokes,
 * or line art). Active card has a warm glow border + subtle elevation.
 * Horizontal scrollable row for many personalities.
 */

import { motion } from 'framer-motion'
import type { PersonalityInfo } from '../../types/assistant'
import type { AvatarType } from '../../types/assistant'

// Personality → accent colour mapping (fallback)
const COLORS: Record<string, string> = {
  jarvis: '#c99568',
  devesh: '#2dd4bf',
  girlfriend: '#db8fa5',
  chandler: '#e8944d',
}

const AVATAR_TYPES: Record<string, AvatarType> = {
  jarvis: 'orb',
  devesh: 'pixel',
  girlfriend: 'light',
  chandler: 'caricature',
}

function getColor(id: string, index: number): string {
  return COLORS[id] || ['#44ff88', '#ffd444', '#ff4444', '#44ddff'][index % 4]
}

/** Mini orb preview — concentric glowing rings */
function MiniOrb({ color, size }: { color: string; size: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40">
      <circle cx="20" cy="20" r="16" fill="none" stroke={color} strokeWidth="1" opacity="0.2" />
      <circle cx="20" cy="20" r="11" fill="none" stroke={color} strokeWidth="1.5" opacity="0.4" />
      <circle cx="20" cy="20" r="6" fill={color} opacity="0.7" />
      <circle cx="20" cy="20" r="3" fill="#fff" opacity="0.5" />
    </svg>
  )
}

/** Mini pixel face preview — simplified 5x5 grid */
function MiniPixel({ color, size }: { color: string; size: number }) {
  // Simplified pixel face: eyes and smile
  const pixels = [
    // eyes
    [1, 1], [3, 1],
    // smile
    [1, 3], [2, 3], [3, 3],
    // cheeks
    [0, 2], [4, 2],
  ]
  const cellSize = size / 5
  return (
    <svg width={size} height={size} viewBox="0 0 5 5">
      {pixels.map(([x, y], i) => (
        <rect key={i} x={x} y={y} width="0.85" height="0.85" rx="0.15" fill={color}
          opacity={i >= 5 ? 0.3 : 0.8} />
      ))}
    </svg>
  )
}

/** Mini light strokes preview — gentle radiating lines */
function MiniLight({ color, size }: { color: string; size: number }) {
  const lines = 8
  return (
    <svg width={size} height={size} viewBox="0 0 40 40">
      {Array.from({ length: lines }).map((_, i) => {
        const angle = (i / lines) * Math.PI * 2
        const x1 = 20 + Math.cos(angle) * 6
        const y1 = 20 + Math.sin(angle) * 6
        const x2 = 20 + Math.cos(angle) * 16
        const y2 = 20 + Math.sin(angle) * 16
        return (
          <line key={i} x1={x1} y1={y1} x2={x2} y2={y2}
            stroke={color} strokeWidth="1.5" strokeLinecap="round"
            opacity={0.4 + (i % 2) * 0.3} />
        )
      })}
      <circle cx="20" cy="20" r="4" fill={color} opacity="0.6" />
    </svg>
  )
}

/** Mini caricature preview — simple line-art face */
function MiniCaricature({ color, size }: { color: string; size: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40">
      {/* Head outline */}
      <circle cx="20" cy="20" r="14" fill="none" stroke={color} strokeWidth="1.5" opacity="0.5" />
      {/* Eyes */}
      <circle cx="15" cy="17" r="1.5" fill={color} opacity="0.7" />
      <circle cx="25" cy="17" r="1.5" fill={color} opacity="0.7" />
      {/* Smirk */}
      <path d="M15 25 Q20 29 26 24" fill="none" stroke={color} strokeWidth="1.2"
        strokeLinecap="round" opacity="0.6" />
    </svg>
  )
}

function MiniAvatar({ id, color, size }: { id: string; color: string; size: number }) {
  const avatarType = AVATAR_TYPES[id] || 'orb'
  switch (avatarType) {
    case 'pixel': return <MiniPixel color={color} size={size} />
    case 'light': return <MiniLight color={color} size={size} />
    case 'caricature': return <MiniCaricature color={color} size={size} />
    case 'orb':
    default: return <MiniOrb color={color} size={size} />
  }
}

interface Props {
  personalities: PersonalityInfo[]
  active: string
  onSwitch: (id: string) => void
}

export function PersonalityPicker({ personalities, active, onSwitch }: Props) {
  if (!personalities.length) return null

  return (
    <div>
      <div style={{
        fontSize: 10, fontWeight: 600, letterSpacing: 2,
        textTransform: 'uppercase' as const,
        color: 'rgba(var(--personality-accent-rgb), 0.5)',
        marginBottom: 14,
      }}>
        Personality
      </div>
      <div style={{
        display: 'flex', gap: 10,
        overflowX: 'auto', overflowY: 'hidden',
        paddingBottom: 4,
        scrollbarWidth: 'none',
        msOverflowStyle: 'none',
      }}>
        {personalities.map((p, i) => {
          const isActive = p.id === active
          const color = getColor(p.id, i)
          return (
            <motion.button
              key={p.id}
              onClick={() => onSwitch(p.id)}
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.97 }}
              animate={{
                y: isActive ? -2 : 0,
                borderColor: isActive ? color : 'var(--border-subtle)',
                boxShadow: isActive
                  ? `0 0 20px ${color}40, 0 4px 12px rgba(0,0,0,0.3)`
                  : '0 2px 8px rgba(0,0,0,0.2)',
              }}
              transition={{ type: 'spring', stiffness: 400, damping: 28 }}
              style={{
                display: 'flex', flexDirection: 'column',
                alignItems: 'center', justifyContent: 'center',
                gap: 6,
                minWidth: 72, padding: '12px 10px 10px',
                borderRadius: 14,
                background: isActive
                  ? 'var(--surface-subtle)'
                  : 'transparent',
                border: '1.5px solid var(--border-subtle)',
                cursor: 'pointer',
                flexShrink: 0,
              }}
            >
              {/* Mini avatar preview */}
              <motion.div
                animate={{ opacity: isActive ? 1 : 0.45 }}
                transition={{ duration: 0.25 }}
              >
                <MiniAvatar id={p.id} color={color} size={36} />
              </motion.div>

              {/* Name */}
              <motion.span
                animate={{
                  color: isActive ? color : 'var(--text-secondary)',
                }}
                transition={{ duration: 0.25 }}
                style={{
                  fontSize: 10, fontWeight: 600,
                  letterSpacing: 0.5,
                  lineHeight: 1,
                  whiteSpace: 'nowrap',
                }}
              >
                {p.display_name}
              </motion.span>
            </motion.button>
          )
        })}
      </div>
    </div>
  )
}
