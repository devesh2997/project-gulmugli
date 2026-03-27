/**
 * SettingsPanel — grouped settings with per-type controls.
 *
 * Settings are fetched via WebSocket and grouped by category.
 * Each category renders as a section with controls based on the setting type.
 * Personality picker sits at the top as a special section.
 */

import { useEffect, useMemo } from 'react'
import { motion } from 'framer-motion'
import type { AssistantStore } from '../types/assistant'
import { SettingControl } from './settings/SettingControl'
import { PersonalityPicker } from './settings/PersonalityPicker'

interface Props {
  store: AssistantStore
}

const CATEGORY_LABELS: Record<string, string> = {
  brain: 'Brain',
  voice: 'Voice',
  ears: 'Ears',
  music: 'Music',
  knowledge: 'Knowledge',
  wake_word: 'Wake Word',
  memory: 'Memory',
  ui: 'Interface',
  debug: 'Debug',
  personalities: 'Personalities',
}

const CATEGORY_ORDER = [
  'brain', 'voice', 'ears', 'music',
  'knowledge', 'wake_word', 'memory', 'ui', 'debug',
]

export function SettingsPanel({ store }: Props) {
  const { settings, actions, personalities, personality } = store

  useEffect(() => {
    if (!settings.length) actions.requestSettings()
  }, [settings.length, actions])

  const grouped = useMemo(() => {
    const map: Record<string, typeof settings> = {}
    for (const s of settings) {
      if (s.editable === false) continue
      if (s.category === 'personalities') continue
      const cat = s.category
      if (!map[cat]) map[cat] = []
      map[cat].push(s)
    }
    return map
  }, [settings])

  const orderedCategories = useMemo(() => {
    return CATEGORY_ORDER.filter(c => grouped[c]?.length)
  }, [grouped])

  if (!settings.length) {
    return (
      <div style={{ padding: 32, textAlign: 'center' }}>
        <motion.div
          animate={{ opacity: [0.3, 0.6, 0.3] }}
          transition={{ duration: 1.5, repeat: Infinity }}
          style={{ color: 'rgba(255,255,255,0.4)', fontSize: 13 }}
        >
          Loading settings...
        </motion.div>
      </div>
    )
  }

  return (
    <div style={{
      padding: '24px 20px', maxWidth: 400, margin: '0 auto',
      display: 'flex', flexDirection: 'column', gap: 24,
    }}>
      {/* Personality Picker */}
      {personalities.length > 0 && (
        <PersonalityPicker
          personalities={personalities}
          active={personality}
          onSwitch={actions.switchPersonality}
        />
      )}

      {/* Setting Categories */}
      {orderedCategories.map(cat => (
        <section key={cat}>
          <div style={{
            fontSize: 10, fontWeight: 600, letterSpacing: 2,
            textTransform: 'uppercase' as const,
            color: 'rgba(var(--personality-accent-rgb), 0.5)',
            marginBottom: 16,
          }}>
            {CATEGORY_LABELS[cat] ?? cat}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {grouped[cat].map(s => (
              <SettingControl
                key={s.path}
                setting={s}
                onUpdate={actions.updateSetting}
              />
            ))}
          </div>
        </section>
      ))}
    </div>
  )
}
