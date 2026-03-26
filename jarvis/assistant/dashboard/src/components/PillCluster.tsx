/**
 * PillCluster — manages a set of Pill badges with auto-dismiss.
 *
 * Mirrors the intents prop into local state and starts dismiss timers
 * when a pill reaches `done` (2s) or `failed` (3s) status.
 */

import { useState, useEffect, useRef } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import type { IntentBadge } from '../types/assistant'
import { Pill } from './Pill'

interface PillClusterProps {
  intents: IntentBadge[]
}

export function PillCluster({ intents }: PillClusterProps) {
  const [visible, setVisible] = useState<IntentBadge[]>([])
  const timers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map())

  // Sync intents prop → local visible state; start dismiss timers on terminal statuses
  useEffect(() => {
    setVisible(prev => {
      const incoming = new Map(intents.map(i => [i.id, i]))
      const merged = new Map(prev.map(i => [i.id, i]))

      // Update existing and add new
      for (const [id, badge] of incoming) {
        merged.set(id, badge)
      }

      return Array.from(merged.values())
    })

    // Schedule dismissal for done/failed pills
    for (const badge of intents) {
      const delay = badge.status === 'done' ? 2000 : badge.status === 'failed' ? 3000 : null
      if (delay !== null && !timers.current.has(badge.id)) {
        const t = setTimeout(() => {
          timers.current.delete(badge.id)
          setVisible(prev => prev.filter(i => i.id !== badge.id))
        }, delay)
        timers.current.set(badge.id, t)
      }
    }
  }, [intents])

  // Clear all timers on unmount
  useEffect(() => {
    return () => {
      for (const t of timers.current.values()) clearTimeout(t)
    }
  }, [])

  if (visible.length === 0) return null

  return (
    <motion.div
      layout
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        justifyContent: 'center',
        gap: 8,
        padding: '0 16px',
      }}
    >
      <AnimatePresence mode="popLayout">
        {visible.map(badge => (
          <Pill
            key={badge.id}
            icon={badge.icon}
            label={badge.label}
            status={badge.status}
          />
        ))}
      </AnimatePresence>
    </motion.div>
  )
}
