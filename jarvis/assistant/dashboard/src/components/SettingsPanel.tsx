/**
 * SettingsPanel — grouped settings with personality-themed category sections.
 *
 * Redesigned to feel purpose-built:
 *   - Category headers use a short personality accent bar instead of full borders
 *   - Sections have a subtle hover glow and spring-animated collapse
 *   - Background mode picker uses pill-shaped selectors with smooth transitions
 *   - Overall spacing follows a rhythmic 8px grid
 *   - Loading state shows a breathing personality-colored skeleton
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { AssistantStore } from '../types/assistant'
import { SettingControl } from './settings/SettingControl'
import { PersonalityPicker } from './settings/PersonalityPicker'
import { BrightnessControl } from './BrightnessControl'

interface Props {
  store: AssistantStore
}

/** Background mode switcher — pill-shaped selectors */
function BackgroundModePicker() {
  const modes = [
    { id: 'gradient', label: 'Gradient', desc: 'Smooth blend' },
    { id: 'texture', label: 'Texture', desc: 'Fabric grain' },
    { id: 'glass', label: 'Glass', desc: 'Frosted glow' },
  ]
  const [active, setActive] = useState('gradient')

  useEffect(() => {
    const val = getComputedStyle(document.documentElement)
      .getPropertyValue('--ui-backgroundMode').trim()
    if (val) setActive(val)
  }, [])

  const handleSwitch = (mode: string) => {
    setActive(mode)
    document.documentElement.style.setProperty('--ui-backgroundMode', mode)
  }

  return (
    <div data-gesture-ignore="true">
      <SectionLabel icon={
        <svg width="14" height="14" viewBox="0 0 24 24"
          fill="none" stroke="var(--personality-accent)" strokeWidth="2" strokeLinecap="round"
          style={{ opacity: 0.6 }}
        >
          <rect x="3" y="3" width="18" height="18" rx="3" />
          <path d="M3 9h18" />
        </svg>
      } label="Background Style" />
      <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
        {modes.map(m => (
          <motion.button
            key={m.id}
            onClick={() => handleSwitch(m.id)}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.96 }}
            animate={{
              background: m.id === active
                ? 'rgba(var(--personality-accent-rgb), 0.1)'
                : 'rgba(255, 255, 255, 0.02)',
            }}
            transition={{ type: 'spring', stiffness: 400, damping: 30 }}
            style={{
              flex: 1,
              padding: '12px 8px 10px',
              borderRadius: 14,
              border: 'none',
              cursor: 'pointer',
              display: 'flex',
              flexDirection: 'column' as const,
              alignItems: 'center',
              gap: 4,
              position: 'relative',
              overflow: 'hidden',
            }}
          >
            {/* Active indicator line at top */}
            <motion.div
              animate={{
                scaleX: m.id === active ? 1 : 0,
                opacity: m.id === active ? 1 : 0,
              }}
              transition={{ type: 'spring', stiffness: 400, damping: 30 }}
              style={{
                position: 'absolute',
                top: 0,
                left: '20%',
                right: '20%',
                height: 2,
                borderRadius: 1,
                background: 'var(--personality-accent)',
                transformOrigin: 'center',
              }}
            />
            <span style={{
              fontSize: 11, fontWeight: 600,
              color: m.id === active ? 'var(--personality-accent)' : 'var(--text-secondary)',
              transition: 'color 0.2s ease',
            }}>
              {m.label}
            </span>
            <span style={{
              fontSize: 9,
              color: 'var(--text-tertiary)',
            }}>
              {m.desc}
            </span>
          </motion.button>
        ))}
      </div>
    </div>
  )
}

/** Reusable section label with accent bar */
function SectionLabel({ icon, label }: { icon?: React.ReactNode; label: string }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 8,
    }}>
      {icon && (
        <span style={{ display: 'flex', alignItems: 'center', opacity: 0.7 }}>
          {icon}
        </span>
      )}
      <span style={{
        fontSize: 10, fontWeight: 600, letterSpacing: '0.14em',
        textTransform: 'uppercase' as const,
        color: 'rgba(var(--personality-accent-rgb), 0.5)',
        flex: 1, textAlign: 'left',
      }}>
        {label}
      </span>
    </div>
  )
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
  sleep_mode: 'Sleep Mode',
  debug: 'Debug',
  personalities: 'Personalities',
}

/** SVG icon paths for each category */
const CATEGORY_ICONS: Record<string, (color: string) => React.ReactElement> = {
  brain: (c) => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9.5 2A5.5 5.5 0 0 0 4 7.5c0 1.58.7 3 1.8 4C4.67 12.58 4 14.27 4 16a6 6 0 0 0 6 6h0a6 6 0 0 0 6-6c0-1.73-.67-3.42-1.8-4.5A5.46 5.46 0 0 0 16 7.5 5.5 5.5 0 0 0 10.5 2h-1Z" />
      <path d="M12 2v20" />
    </svg>
  ),
  voice: (c) => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
      <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
      <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
    </svg>
  ),
  ears: (c) => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
      <line x1="12" y1="19" x2="12" y2="23" />
      <line x1="8" y1="23" x2="16" y2="23" />
    </svg>
  ),
  music: (c) => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 18V5l12-2v13" />
      <circle cx="6" cy="18" r="3" />
      <circle cx="18" cy="16" r="3" />
    </svg>
  ),
  knowledge: (c) => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  ),
  wake_word: (c) => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </svg>
  ),
  memory: (c) => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="6" width="20" height="12" rx="2" />
      <path d="M6 12h.01M10 12h.01M14 12h.01M18 12h.01" />
      <path d="M6 2v4M10 2v4M14 2v4M18 2v4" />
    </svg>
  ),
  ui: (c) => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="7" />
      <rect x="14" y="3" width="7" height="7" />
      <rect x="14" y="14" width="7" height="7" />
      <rect x="3" y="14" width="7" height="7" />
    </svg>
  ),
  sleep_mode: (c) => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
  ),
  debug: (c) => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 16V8l-8-4-8 4v8l8 4 8-4z" />
      <path d="M12 4v16" />
      <path d="M4 8l8 4 8-4" />
    </svg>
  ),
}

const CATEGORY_ORDER = [
  'brain', 'voice', 'ears', 'music',
  'knowledge', 'wake_word', 'memory', 'ui', 'sleep_mode', 'debug',
]

function CategorySection({ cat, children }: { cat: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(true)
  const label = CATEGORY_LABELS[cat] ?? cat
  const IconFn = CATEGORY_ICONS[cat]
  const iconColor = 'rgba(var(--personality-accent-rgb), 0.5)'

  return (
    <section style={{ position: 'relative' }}>
      {/* Category header — accent bar + tap to toggle */}
      <motion.button
        onClick={() => setOpen(!open)}
        whileHover={{ x: 2 }}
        transition={{ type: 'spring', stiffness: 400, damping: 25 }}
        style={{
          display: 'flex', alignItems: 'center', gap: 8,
          width: '100%', padding: '0 0 12px 0',
          background: 'none', border: 'none', cursor: 'pointer',
          position: 'relative',
        }}
      >
        {/* Short accent bar on the left */}
        <motion.div
          animate={{
            height: open ? 16 : 8,
            opacity: open ? 0.6 : 0.2,
          }}
          transition={{ type: 'spring', stiffness: 400, damping: 25 }}
          style={{
            width: 2,
            borderRadius: 1,
            background: 'var(--personality-accent)',
            flexShrink: 0,
          }}
        />
        {/* Icon */}
        {IconFn && (
          <span style={{ display: 'flex', alignItems: 'center', opacity: 0.7 }}>
            {IconFn(iconColor)}
          </span>
        )}
        {/* Label */}
        <span style={{
          fontSize: 10, fontWeight: 600, letterSpacing: '0.14em',
          textTransform: 'uppercase' as const,
          color: iconColor,
          flex: 1, textAlign: 'left',
        }}>
          {label}
        </span>
        {/* Chevron */}
        <motion.svg
          width="12" height="12" viewBox="0 0 24 24"
          fill="none" stroke={iconColor} strokeWidth="2.5" strokeLinecap="round"
          animate={{ rotate: open ? 0 : -90 }}
          transition={{ type: 'spring', stiffness: 400, damping: 25 }}
        >
          <path d="M6 9l6 6 6-6" />
        </motion.svg>
      </motion.button>

      {/* Collapsible content */}
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 280, damping: 28 }}
            style={{ overflow: 'hidden' }}
          >
            <div style={{
              display: 'flex', flexDirection: 'column', gap: 16,
              paddingLeft: 10,
              paddingBottom: 4,
            }}>
              {children}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  )
}

export function SettingsPanel({ store }: Props) {
  const settings = store?.settings ?? []
  const actions = store?.actions
  const personalities = store?.personalities ?? []
  const personality = store?.personality ?? 'jarvis'

  // Request settings once on mount
  const requestedRef = useRef(false)
  useEffect(() => {
    if (!requestedRef.current && !settings.length && actions?.requestSettings) {
      requestedRef.current = true
      actions.requestSettings()
    }
  }, [])

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
          animate={{ opacity: [0.2, 0.5, 0.2] }}
          transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
          style={{ color: 'var(--personality-accent)', fontSize: 13, fontWeight: 500 }}
        >
          Loading settings...
        </motion.div>
      </div>
    )
  }

  // When brightness is being adjusted, fade everything else
  const [adjustingBrightness, setAdjustingBrightness] = useState(false)
  const handleBrightnessAdjusting = useCallback((isAdjusting: boolean) => {
    setAdjustingBrightness(isAdjusting)
  }, [])

  return (
    <div style={{
      padding: '24px 20px', maxWidth: 400, margin: '0 auto',
      display: 'flex', flexDirection: 'column', gap: 28,
    }}>
      {/* Personality Picker */}
      <motion.div animate={{ opacity: adjustingBrightness ? 0.15 : 1 }} transition={{ duration: 0.3 }}>
        {personalities.length > 0 && (
          <PersonalityPicker
            personalities={personalities}
            active={personality}
            onSwitch={actions.switchPersonality}
          />
        )}
      </motion.div>

      {/* Ambient Brightness */}
      <BrightnessControl onAdjusting={handleBrightnessAdjusting} />

      {/* Background Mode */}
      <BackgroundModePicker />

      {/* Setting Categories */}
      <motion.div
        animate={{ opacity: adjustingBrightness ? 0.08 : 1 }}
        transition={{ duration: 0.3 }}
        style={{ display: 'flex', flexDirection: 'column', gap: 28 }}
      >
      {orderedCategories.map(cat => (
        <CategorySection key={cat} cat={cat}>
          {grouped[cat].map(s => (
            <SettingControl
              key={s.path}
              setting={s}
              onUpdate={actions.updateSetting}
            />
          ))}
        </CategorySection>
      ))}
      </motion.div>
    </div>
  )
}
