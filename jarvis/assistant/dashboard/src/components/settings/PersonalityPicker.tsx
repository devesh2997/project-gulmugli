/**
 * PersonalityPicker — mini avatar icons for switching personalities.
 *
 * Shows colored circles with personality initials. Active one has a glow ring.
 * Tapping switches personality via the assistant actions.
 */

import { motion } from 'framer-motion'
import type { PersonalityInfo } from '../../types/assistant'

interface Props {
  personalities: PersonalityInfo[]
  active: string
  onSwitch: (id: string) => void
}

const COLORS: Record<string, string> = {
  jarvis: '#4488ff',
  devesh: '#ff8844',
  girlfriend: '#ff44aa',
  chandler: '#aa44ff',
}

function getColor(id: string, index: number): string {
  return COLORS[id] || ['#44ff88', '#ffd444', '#ff4444', '#44ddff'][index % 4]
}

export function PersonalityPicker({ personalities, active, onSwitch }: Props) {
  if (!personalities.length) return null

  return (
    <div>
      <div style={{
        fontSize: 10, fontWeight: 600, letterSpacing: 2,
        textTransform: 'uppercase' as const,
        color: 'rgba(var(--personality-accent-rgb), 0.5)',
        marginBottom: 16,
      }}>
        Personality
      </div>
      <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
        {personalities.map((p, i) => {
          const isActive = p.id === active
          const color = getColor(p.id, i)
          return (
            <motion.button
              key={p.id}
              onClick={() => onSwitch(p.id)}
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.95 }}
              style={{
                width: 44, height: 44, borderRadius: 22,
                background: isActive ? color : 'rgba(255,255,255,0.06)',
                border: `2px solid ${isActive ? color : 'rgba(255,255,255,0.1)'}`,
                boxShadow: isActive ? `0 0 16px ${color}55` : 'none',
                cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
                flexDirection: 'column', gap: 0, padding: 0,
              }}
            >
              <span style={{
                fontSize: 16, fontWeight: 700,
                color: isActive ? '#fff' : 'rgba(255,255,255,0.4)',
                lineHeight: 1,
              }}>
                {p.display_name.charAt(0).toUpperCase()}
              </span>
            </motion.button>
          )
        })}
      </div>
      <div style={{
        textAlign: 'center', marginTop: 8,
        fontSize: 11, color: 'rgba(255,255,255,0.4)',
      }}>
        {personalities.find(p => p.id === active)?.display_name ?? active}
      </div>
    </div>
  )
}
