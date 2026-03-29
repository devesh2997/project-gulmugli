/**
 * AmbientIndicator — floating pill that appears when ambient sounds are playing.
 *
 * Shows an animated icon matching the sound type, a volume slider on tap,
 * and a stop button. Designed to be minimal so it doesn't compete with
 * the avatar or now-playing bar.
 */

import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import type { AmbientState, AssistantActions } from '../types/assistant'

interface Props {
  ambient: AmbientState
  actions: AssistantActions
}

/** Map sound name to a display label */
const SOUND_LABELS: Record<string, string> = {
  rain: 'Rain',
  ocean: 'Ocean',
  thunderstorm: 'Storm',
  white_noise: 'White Noise',
  pink_noise: 'Pink Noise',
  brown_noise: 'Brown Noise',
  fireplace: 'Fireplace',
  forest: 'Forest',
  birds: 'Birds',
  wind: 'Wind',
  cafe: 'Cafe',
  fan: 'Fan',
}

// ── Animated icons per sound type ────────────────────────────────

function RainIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
      {/* Three animated falling droplets */}
      <motion.circle
        cx="5" r="1.2" fill="rgba(130, 180, 255, 0.9)"
        animate={{ cy: [2, 16], opacity: [1, 0] }}
        transition={{ duration: 1.2, repeat: Infinity, ease: 'linear', delay: 0 }}
      />
      <motion.circle
        cx="9" r="1.2" fill="rgba(130, 180, 255, 0.9)"
        animate={{ cy: [0, 16], opacity: [1, 0] }}
        transition={{ duration: 1.0, repeat: Infinity, ease: 'linear', delay: 0.3 }}
      />
      <motion.circle
        cx="13" r="1.2" fill="rgba(130, 180, 255, 0.9)"
        animate={{ cy: [3, 16], opacity: [1, 0] }}
        transition={{ duration: 1.4, repeat: Infinity, ease: 'linear', delay: 0.6 }}
      />
    </svg>
  )
}

function OceanIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
      <motion.path
        d="M1 10 Q4.5 6, 9 10 Q13.5 14, 17 10"
        stroke="rgba(100, 180, 255, 0.8)"
        strokeWidth="2"
        fill="none"
        animate={{ d: [
          'M1 10 Q4.5 6, 9 10 Q13.5 14, 17 10',
          'M1 10 Q4.5 14, 9 10 Q13.5 6, 17 10',
          'M1 10 Q4.5 6, 9 10 Q13.5 14, 17 10',
        ]}}
        transition={{ duration: 2.5, repeat: Infinity, ease: 'easeInOut' }}
      />
    </svg>
  )
}

function FireIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
      <motion.path
        d="M9 2 C6 6, 4 10, 5 14 C6 16, 8 17, 9 17 C10 17, 12 16, 13 14 C14 10, 12 6, 9 2Z"
        fill="rgba(255, 140, 40, 0.9)"
        animate={{ scale: [1, 1.08, 0.95, 1], opacity: [0.9, 1, 0.85, 0.9] }}
        transition={{ duration: 0.8, repeat: Infinity, ease: 'easeInOut' }}
      />
      <motion.path
        d="M9 6 C7.5 9, 7 12, 7.5 14 C8 15.5, 10 15.5, 10.5 14 C11 12, 10.5 9, 9 6Z"
        fill="rgba(255, 210, 80, 0.9)"
        animate={{ scale: [1, 0.92, 1.05, 1], opacity: [0.9, 0.8, 1, 0.9] }}
        transition={{ duration: 0.6, repeat: Infinity, ease: 'easeInOut' }}
      />
    </svg>
  )
}

function NoiseIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
      {/* Animated static bars */}
      {[2, 5, 8, 11, 14].map((x, i) => (
        <motion.rect
          key={x}
          x={x} width="2" rx="1"
          fill="rgba(180, 180, 200, 0.7)"
          animate={{ y: [4, 8, 2, 6, 4], height: [10, 4, 14, 6, 10] }}
          transition={{ duration: 1.5, repeat: Infinity, ease: 'easeInOut', delay: i * 0.15 }}
        />
      ))}
    </svg>
  )
}

function NatureIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
      {/* Simple tree */}
      <motion.path
        d="M9 2 L5 9 L7 9 L4 14 L14 14 L11 9 L13 9 Z"
        fill="rgba(80, 180, 80, 0.8)"
        animate={{ scale: [1, 1.03, 1] }}
        transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
      />
      <rect x="8" y="14" width="2" height="3" fill="rgba(140, 100, 60, 0.8)" rx="0.5" />
    </svg>
  )
}

function DefaultSoundIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
      <motion.circle
        cx="9" cy="9" r="6"
        stroke="rgba(180, 180, 200, 0.6)"
        strokeWidth="1.5"
        fill="none"
        animate={{ r: [5, 7, 5], opacity: [0.8, 0.4, 0.8] }}
        transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
      />
      <circle cx="9" cy="9" r="2.5" fill="rgba(180, 180, 200, 0.7)" />
    </svg>
  )
}

function SoundIcon({ sound }: { sound: string }) {
  switch (sound) {
    case 'rain':
    case 'thunderstorm':
      return <RainIcon />
    case 'ocean':
      return <OceanIcon />
    case 'fireplace':
      return <FireIcon />
    case 'white_noise':
    case 'pink_noise':
    case 'brown_noise':
    case 'fan':
      return <NoiseIcon />
    case 'forest':
    case 'birds':
    case 'wind':
    case 'cafe':
      return <NatureIcon />
    default:
      return <DefaultSoundIcon />
  }
}

export function AmbientIndicator({ ambient, actions }: Props) {
  const [expanded, setExpanded] = useState(false)
  const [localVolume, setLocalVolume] = useState(ambient.volume)

  // Keep local volume in sync when backend updates
  if (!expanded && localVolume !== ambient.volume) {
    setLocalVolume(ambient.volume)
  }

  const label = SOUND_LABELS[ambient.sound] || ambient.sound || 'Ambient'

  return (
    <AnimatePresence>
      {ambient.active && (
        <motion.div
          initial={{ opacity: 0, y: 20, scale: 0.9 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 20, scale: 0.9 }}
          transition={{ type: 'spring', stiffness: 300, damping: 25 }}
          style={{
            position: 'fixed',
            bottom: 24,
            left: '50%',
            transform: 'translateX(-50%)',
            zIndex: 30,
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: expanded ? '8px 14px' : '6px 12px',
            borderRadius: 20,
            background: 'rgba(20, 20, 30, 0.75)',
            backdropFilter: 'blur(12px)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            cursor: 'pointer',
            userSelect: 'none',
          }}
          onClick={() => !expanded && setExpanded(true)}
        >
          <SoundIcon sound={ambient.sound} />

          <span style={{
            fontSize: 12,
            fontWeight: 500,
            color: 'rgba(255, 255, 255, 0.7)',
            letterSpacing: '0.02em',
          }}>
            {label}
          </span>

          <AnimatePresence>
            {expanded && (
              <motion.div
                initial={{ width: 0, opacity: 0 }}
                animate={{ width: 'auto', opacity: 1 }}
                exit={{ width: 0, opacity: 0 }}
                transition={{ duration: 0.2 }}
                style={{ display: 'flex', alignItems: 'center', gap: 8, overflow: 'hidden' }}
              >
                {/* Volume slider */}
                <input
                  type="range"
                  min={0}
                  max={100}
                  value={localVolume}
                  onChange={(e) => {
                    const v = parseInt(e.target.value, 10)
                    setLocalVolume(v)
                  }}
                  onMouseUp={() => actions.setAmbientVolume(localVolume)}
                  onTouchEnd={() => actions.setAmbientVolume(localVolume)}
                  onClick={(e) => e.stopPropagation()}
                  style={{
                    width: 80,
                    height: 4,
                    accentColor: 'rgba(130, 180, 255, 0.8)',
                    cursor: 'pointer',
                  }}
                />

                <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.5)', minWidth: 24, textAlign: 'right' }}>
                  {localVolume}%
                </span>

                {/* Stop button */}
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    actions.stopAmbient()
                    setExpanded(false)
                  }}
                  style={{
                    background: 'rgba(255, 80, 80, 0.2)',
                    border: '1px solid rgba(255, 80, 80, 0.3)',
                    borderRadius: 12,
                    padding: '2px 8px',
                    fontSize: 11,
                    color: 'rgba(255, 120, 120, 0.9)',
                    cursor: 'pointer',
                    whiteSpace: 'nowrap',
                  }}
                >
                  Stop
                </button>

                {/* Close expand */}
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    setExpanded(false)
                  }}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: 'rgba(255,255,255,0.4)',
                    cursor: 'pointer',
                    fontSize: 14,
                    padding: '0 2px',
                    lineHeight: 1,
                  }}
                >
                  x
                </button>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
