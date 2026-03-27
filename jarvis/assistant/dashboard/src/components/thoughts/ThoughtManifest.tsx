/**
 * ThoughtManifest — container for thought manifestations around the avatar.
 *
 * Replaces PillCluster. Manages orbit position assignment, auto-dismiss
 * timers, and renders Thought elements at absolute positions via
 * `position: fixed` with `pointer-events: none`.
 *
 * Position algorithm: divide circle into 8 sectors (45 degrees each),
 * prefer upper hemisphere (thoughts "rise from the mind"), assign each
 * new thought to the sector with fewest active thoughts, with random
 * angle jitter within the sector to avoid grid alignment.
 */

import { useState, useEffect, useRef, useMemo } from 'react'
import { AnimatePresence } from 'framer-motion'
import type { AvatarType, IntentBadge } from '../../types/assistant'
import { useTokens } from '../../context/TokenProvider'
import { Thought } from './Thought'

interface ThoughtManifestProps {
  intents: IntentBadge[]
  avatarCenter: { x: number; y: number }
  avatarSize: number  // avatar visual radius
}

/** 8 sectors, upper hemisphere first for "rising from mind" effect */
const SECTOR_COUNT = 8
const SECTOR_SIZE = (2 * Math.PI) / SECTOR_COUNT

/** Upper hemisphere sectors get priority. Ordered by preference. */
const SECTOR_PRIORITY = [
  7, // 315-360 (upper right)
  0, // 0-45 (right, slightly up)
  6, // 270-315 (upper left)
  1, // 45-90 (right, slightly down)
  5, // 225-270 (left)
  2, // 90-135 (lower right)
  4, // 180-225 (lower left)
  3, // 135-180 (bottom)
]

interface ThoughtPosition {
  angle: number
  distance: number
}

export function ThoughtManifest({ intents, avatarCenter, avatarSize }: ThoughtManifestProps) {
  const [visible, setVisible] = useState<IntentBadge[]>([])
  const timers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map())
  const positions = useRef<Map<string, ThoughtPosition>>(new Map())

  const { getToken } = useTokens()
  const avatarType = (getToken('personality.avatarType') || 'orb') as AvatarType

  // Orbit radius: 1.6x the avatar radius (larger for 44px thoughts)
  const orbitRadius = avatarSize * 0.65 * 1.6

  // Sync intents -> visible state, start dismiss timers
  useEffect(() => {
    setVisible(prev => {
      const incoming = new Map(intents.map(i => [i.id, i]))
      const merged = new Map(prev.map(i => [i.id, i]))
      for (const [id, badge] of incoming) {
        merged.set(id, badge)
      }
      return Array.from(merged.values())
    })

    for (const badge of intents) {
      const delay = badge.status === 'done' ? 2000 : badge.status === 'failed' ? 3000 : null
      if (delay !== null && !timers.current.has(badge.id)) {
        const t = setTimeout(() => {
          timers.current.delete(badge.id)
          positions.current.delete(badge.id)
          setVisible(prev => prev.filter(i => i.id !== badge.id))
        }, delay)
        timers.current.set(badge.id, t)
      }
    }
  }, [intents])

  // Clear timers on unmount
  useEffect(() => {
    return () => {
      for (const t of timers.current.values()) clearTimeout(t)
    }
  }, [])

  // Assign orbit positions to new thoughts
  const positionedThoughts = useMemo(() => {
    // Count how many thoughts are in each sector
    const sectorCounts = new Array(SECTOR_COUNT).fill(0)
    for (const pos of positions.current.values()) {
      const sectorIdx = Math.floor(((pos.angle % (2 * Math.PI)) + 2 * Math.PI) % (2 * Math.PI) / SECTOR_SIZE)
      sectorCounts[sectorIdx]++
    }

    // Assign positions for new thoughts
    for (const badge of visible) {
      if (!positions.current.has(badge.id)) {
        // Find sector with fewest thoughts, using priority order
        let bestSector = SECTOR_PRIORITY[0]
        let bestCount = Infinity
        for (const s of SECTOR_PRIORITY) {
          if (sectorCounts[s] < bestCount) {
            bestCount = sectorCounts[s]
            bestSector = s
            if (bestCount === 0) break
          }
        }

        // Random angle within sector, +/- 15 degrees of center
        const sectorCenter = bestSector * SECTOR_SIZE + SECTOR_SIZE / 2
        const jitter = (Math.random() - 0.5) * (Math.PI / 6) // +/- 15 degrees
        const angle = sectorCenter + jitter

        // Slight distance variation
        const distJitter = 1 + (Math.random() - 0.5) * 0.3 // 0.85 to 1.15
        const distance = orbitRadius * distJitter

        positions.current.set(badge.id, { angle, distance })
        sectorCounts[bestSector]++
      }
    }

    // Clean up positions for thoughts no longer visible
    const visibleIds = new Set(visible.map(b => b.id))
    for (const id of positions.current.keys()) {
      if (!visibleIds.has(id)) positions.current.delete(id)
    }

    return visible.map(badge => ({
      badge,
      position: positions.current.get(badge.id) ?? { angle: 0, distance: orbitRadius },
    }))
  }, [visible, orbitRadius])

  if (visible.length === 0) return null

  return (
    <div style={{ position: 'fixed', inset: 0, pointerEvents: 'none', zIndex: 40 }}>
      <AnimatePresence>
        {positionedThoughts.map(({ badge, position }) => (
          <Thought
            key={badge.id}
            badge={badge}
            angle={position.angle}
            distance={position.distance}
            center={avatarCenter}
            avatarType={avatarType}
          />
        ))}
      </AnimatePresence>
    </div>
  )
}
