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
import { getAvatarTypes } from '../Avatar'

// Personality → accent colour mapping (fallback)
const COLORS: Record<string, string> = {
  jarvis: '#c99568',
  devesh: '#2dd4bf',
  girlfriend: '#db8fa5',
  chandler: '#e8944d',
}

const AVATAR_TYPES: Record<string, AvatarType> = {
  jarvis: 'orb',
  devesh: 'cozmo',
  girlfriend: 'light',
  chandler: 'caricature',
}

/** Human-readable labels for avatar types */
const AVATAR_LABELS: Record<string, string> = {
  orb: 'Orb',
  pixel: 'Pixel',
  light: 'Light',
  caricature: 'Sketch',
  cozmo: 'Cozmo',
  'bubble-eyes': 'Bubble',
  blob: 'Blob',
  plasma: 'Plasma',
  geo: 'Geo',
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

/* Old MiniAvatar removed — replaced by the version below that accepts avatarType */

/** Mini Cozmo preview — two rounded eye rects */
function MiniCozmo({ color, size }: { color: string; size: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40">
      {/* Left eye */}
      <rect x="8" y="14" width="10" height="8" rx="3" fill={color} opacity="0.8" />
      {/* Right eye */}
      <rect x="22" y="14" width="10" height="8" rx="3" fill={color} opacity="0.8" />
      {/* Left pupil */}
      <rect x="12" y="17" width="3" height="3" rx="1" fill="#fff" opacity="0.6" />
      {/* Right pupil */}
      <rect x="26" y="17" width="3" height="3" rx="1" fill="#fff" opacity="0.6" />
      {/* Mouth */}
      <path d="M15 30 Q20 33 25 30" fill="none" stroke={color} strokeWidth="1.2"
        strokeLinecap="round" opacity="0.5" />
    </svg>
  )
}

/** Mini BubbleEyes preview — glassy round eyes with specular highlights */
function MiniBubbleEyes({ color, size }: { color: string; size: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40">
      {/* Left eye body */}
      <circle cx="14" cy="20" r="7" fill={color} opacity="0.85" />
      {/* Right eye body */}
      <circle cx="26" cy="20" r="7" fill={color} opacity="0.85" />
      {/* Left specular highlight */}
      <circle cx="11.5" cy="17.5" r="2.2" fill="#fff" opacity="0.7" />
      {/* Right specular highlight */}
      <circle cx="23.5" cy="17.5" r="2.2" fill="#fff" opacity="0.7" />
      {/* Tiny lower-right pin lights */}
      <circle cx="16.5" cy="22" r="0.8" fill="#fff" opacity="0.7" />
      <circle cx="28.5" cy="22" r="0.8" fill="#fff" opacity="0.7" />
    </svg>
  )
}

/** Mini Blob preview — soft 3D rounded body with two eyes */
function MiniBlob({ color, size }: { color: string; size: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40">
      {/* Body — rounded square with subtle gradient feel via opacity layering */}
      <rect x="6" y="7" width="28" height="26" rx="9" fill={color} opacity="0.85" />
      <rect x="6" y="7" width="28" height="13" rx="9" fill="#fff" opacity="0.08" />
      {/* Eyes */}
      <circle cx="15" cy="19" r="2.4" fill="#1a120a" opacity="0.85" />
      <circle cx="25" cy="19" r="2.4" fill="#1a120a" opacity="0.85" />
      {/* Mouth */}
      <path d="M16 26 Q20 28.5 24 26" fill="none" stroke="#1a120a" strokeWidth="1.4"
        strokeLinecap="round" opacity="0.7" />
      {/* Specular highlight */}
      <ellipse cx="11" cy="11" rx="3" ry="1.6" fill="#fff" opacity="0.35" />
    </svg>
  )
}

/** Mini Plasma preview — irregular morphing blob with floating eye-spots */
function MiniPlasma({ color, size }: { color: string; size: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40">
      {/* Outer glow */}
      <circle cx="20" cy="20" r="15" fill={color} opacity="0.18" />
      {/* Liquid blob path — irregular */}
      <path
        d="M 20 6
           C 28 7  33 11  32 19
           C 33 27  27 32  19 32
           C 11 32  6 27  7 19
           C 7 11  12 6  20 6 Z"
        fill={color}
        opacity="0.85"
      />
      {/* Floating darker eye-spots */}
      <ellipse cx="15" cy="18" rx="2" ry="2.4" fill="#000" opacity="0.55" />
      <ellipse cx="25" cy="18" rx="2" ry="2.4" fill="#000" opacity="0.55" />
      {/* Internal turbulence speck */}
      <circle cx="20" cy="25" r="1" fill="#fff" opacity="0.35" />
      {/* Top specular */}
      <ellipse cx="14" cy="11" rx="3" ry="1.6" fill="#fff" opacity="0.3" />
    </svg>
  )
}

/** Mini Geo preview — flat rounded square with bold geometric eyes */
function MiniGeo({ color, size }: { color: string; size: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40">
      {/* Drop shadow */}
      <rect x="6" y="9" width="28" height="26" rx="8" fill="#000" opacity="0.18" />
      {/* Flat solid face */}
      <rect x="6" y="7" width="28" height="26" rx="8" fill={color} />
      {/* Eyes — solid filled circles for contrast */}
      <circle cx="15" cy="19" r="2.4" fill="#fff8ee" />
      <circle cx="25" cy="19" r="2.4" fill="#fff8ee" />
      {/* Smile arc */}
      <path d="M15 26 Q20 28.5 25 26" fill="none" stroke="#fff8ee" strokeWidth="1.4"
        strokeLinecap="round" />
      {/* Brand-mascot "+" badge top-right */}
      <path d="M30 11 L30 13 M29 12 L31 12" stroke="#fff8ee" strokeWidth="1" strokeLinecap="round" />
    </svg>
  )
}

function MiniAvatar({ id, avatarType, color, size }: { id: string; avatarType?: string; color: string; size: number }) {
  const type = avatarType || AVATAR_TYPES[id] || 'orb'
  switch (type) {
    case 'pixel': return <MiniPixel color={color} size={size} />
    case 'light': return <MiniLight color={color} size={size} />
    case 'caricature': return <MiniCaricature color={color} size={size} />
    case 'cozmo': return <MiniCozmo color={color} size={size} />
    case 'bubble-eyes': return <MiniBubbleEyes color={color} size={size} />
    case 'blob': return <MiniBlob color={color} size={size} />
    case 'plasma': return <MiniPlasma color={color} size={size} />
    case 'geo': return <MiniGeo color={color} size={size} />
    case 'orb':
    default: return <MiniOrb color={color} size={size} />
  }
}

interface Props {
  personalities: PersonalityInfo[]
  active: string
  onSwitch: (id: string) => void
  onAvatarChange?: (avatarType: string) => void
  currentAvatarType?: string
}

export function PersonalityPicker({ personalities, active, onSwitch, onAvatarChange, currentAvatarType }: Props) {
  const availableAvatars = getAvatarTypes()

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
              onClick={() => {
                if (!isActive) onSwitch(p.id)
              }}
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
                <MiniAvatar
                  id={p.id}
                  avatarType={isActive ? currentAvatarType : undefined}
                  color={color}
                  size={36}
                />
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

      {/* Avatar picker — always visible, mirrors the personality picker UX */}
      {onAvatarChange && (
        <div style={{ marginTop: 22 }}>
          <div style={{
            fontSize: 10, fontWeight: 600, letterSpacing: 2,
            textTransform: 'uppercase' as const,
            color: 'rgba(var(--personality-accent-rgb), 0.5)',
            marginBottom: 14,
          }}>
            Avatar Style
          </div>
          <div style={{
            display: 'flex', gap: 8,
            overflowX: 'auto', overflowY: 'hidden',
            paddingBottom: 4,
            scrollbarWidth: 'none',
            msOverflowStyle: 'none',
          }}>
            {availableAvatars.map(type => {
              const isSelected = type === currentAvatarType
              const activeColor = getColor(active, 0)
              return (
                <motion.button
                  key={type}
                  onClick={() => onAvatarChange(type)}
                  whileHover={{ scale: 1.04 }}
                  whileTap={{ scale: 0.96 }}
                  animate={{
                    y: isSelected ? -2 : 0,
                    borderColor: isSelected ? activeColor : 'var(--border-subtle)',
                    boxShadow: isSelected
                      ? `0 0 18px ${activeColor}40, 0 4px 10px rgba(0,0,0,0.25)`
                      : '0 2px 6px rgba(0,0,0,0.18)',
                  }}
                  transition={{ type: 'spring', stiffness: 400, damping: 28 }}
                  style={{
                    display: 'flex', flexDirection: 'column',
                    alignItems: 'center', justifyContent: 'center',
                    gap: 6,
                    minWidth: 64, padding: '10px 8px 8px',
                    borderRadius: 12,
                    background: isSelected ? 'var(--surface-subtle)' : 'transparent',
                    border: '1.5px solid var(--border-subtle)',
                    cursor: 'pointer',
                    flexShrink: 0,
                  }}
                >
                  <motion.div
                    animate={{ opacity: isSelected ? 1 : 0.45 }}
                    transition={{ duration: 0.25 }}
                  >
                    <MiniAvatar id={active} avatarType={type} color={activeColor} size={32} />
                  </motion.div>
                  <motion.span
                    animate={{ color: isSelected ? activeColor : 'var(--text-secondary)' }}
                    transition={{ duration: 0.25 }}
                    style={{
                      fontSize: 9, fontWeight: 600,
                      letterSpacing: 0.5,
                      lineHeight: 1,
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {AVATAR_LABELS[type] || type}
                  </motion.span>
                </motion.button>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
