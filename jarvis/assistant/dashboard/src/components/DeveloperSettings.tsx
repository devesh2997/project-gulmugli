/**
 * DeveloperSettings -- hidden technical panel behind the Preferences curtain.
 *
 * Deliberately different aesthetic: darker, monospace values, terminal-like feel.
 * Contains: Brain, Ears, Wake Word, Memory, Knowledge, Debug, UI settings.
 * Accessed via long-press on version text or "Advanced..." link.
 */

import { useMemo, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { SettingSchema } from '../types/assistant'
import { SettingControl } from './settings/SettingControl'

interface Props {
  settings: SettingSchema[]
  onUpdate: (path: string, value: any) => void
  onBack: () => void
}

/* Which categories live in developer settings */
const DEV_CATEGORIES = ['brain', 'ears', 'wake_word', 'memory', 'knowledge', 'ui', 'debug']

const CATEGORY_META: Record<string, { label: string; icon: string }> = {
  brain:      { label: 'Brain',      icon: 'B' },
  ears:       { label: 'Ears',       icon: 'E' },
  wake_word:  { label: 'Wake Word',  icon: 'W' },
  memory:     { label: 'Memory',     icon: 'M' },
  knowledge:  { label: 'Knowledge',  icon: 'K' },
  ui:         { label: 'Interface',  icon: 'U' },
  debug:      { label: 'Debug',      icon: 'D' },
}

/* ------------------------------------------------------------------ */
/*  Dev category section                                               */
/* ------------------------------------------------------------------ */

function DevCategory({ cat, children }: { cat: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(true)
  const meta = CATEGORY_META[cat] ?? { label: cat, icon: '?' }

  return (
    <section style={{ position: 'relative' }}>
      <motion.button
        onClick={() => setOpen(!open)}
        whileHover={{ x: 2 }}
        transition={{ type: 'spring', stiffness: 400, damping: 25 }}
        style={{
          display: 'flex', alignItems: 'center', gap: 8,
          width: '100%', padding: '0 0 10px 0',
          background: 'none', border: 'none', cursor: 'pointer',
        }}
      >
        {/* Monospace badge */}
        <span style={{
          width: 20, height: 20,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 10, fontWeight: 700,
          fontFamily: '"SF Mono", "Fira Code", "Cascadia Code", monospace',
          color: 'rgba(var(--personality-accent-rgb), 0.6)',
          background: 'rgba(var(--personality-accent-rgb), 0.08)',
          borderRadius: 4,
          flexShrink: 0,
        }}>
          {meta.icon}
        </span>

        {/* Label */}
        <span style={{
          fontSize: 11, fontWeight: 600,
          fontFamily: '"SF Mono", "Fira Code", "Cascadia Code", monospace',
          letterSpacing: '0.06em',
          color: 'rgba(var(--personality-accent-rgb), 0.5)',
          flex: 1, textAlign: 'left',
        }}>
          {meta.label}
        </span>

        {/* Chevron */}
        <motion.svg
          width="12" height="12" viewBox="0 0 24 24"
          fill="none" stroke="rgba(var(--personality-accent-rgb), 0.3)"
          strokeWidth="2.5" strokeLinecap="round"
          animate={{ rotate: open ? 0 : -90 }}
          transition={{ type: 'spring', stiffness: 400, damping: 25 }}
        >
          <path d="M6 9l6 6 6-6" />
        </motion.svg>
      </motion.button>

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
              display: 'flex', flexDirection: 'column', gap: 14,
              paddingLeft: 28,
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

/* ------------------------------------------------------------------ */
/*  Export                                                             */
/* ------------------------------------------------------------------ */

export function DeveloperSettings({ settings, onUpdate, onBack }: Props) {
  const grouped = useMemo(() => {
    const map: Record<string, SettingSchema[]> = {}
    for (const s of settings) {
      if (s.editable === false) continue
      if (!DEV_CATEGORIES.includes(s.category)) continue
      if (!map[s.category]) map[s.category] = []
      map[s.category].push(s)
    }
    return map
  }, [settings])

  const orderedCategories = DEV_CATEGORIES.filter(c => grouped[c]?.length)

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2 }}
      style={{
        padding: '20px 20px 40px',
        maxWidth: 400,
        margin: '0 auto',
        display: 'flex',
        flexDirection: 'column',
        gap: 24,
      }}
    >
      {/* Header with terminal aesthetic */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 12,
        paddingBottom: 16,
        borderBottom: '1px solid rgba(var(--personality-accent-rgb), 0.08)',
      }}>
        {/* Back button */}
        <motion.button
          onClick={onBack}
          whileHover={{ x: -2 }}
          whileTap={{ scale: 0.95 }}
          style={{
            background: 'rgba(var(--personality-accent-rgb), 0.06)',
            border: '1px solid rgba(var(--personality-accent-rgb), 0.1)',
            borderRadius: 8,
            padding: '6px 10px',
            cursor: 'pointer',
            display: 'flex', alignItems: 'center', gap: 4,
            color: 'var(--personality-accent)',
            fontSize: 11,
            fontWeight: 600,
          }}
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
            <path d="M19 12H5M12 19l-7-7 7-7" />
          </svg>
          Back
        </motion.button>

        <div style={{ flex: 1 }}>
          <div style={{
            fontSize: 13, fontWeight: 700,
            fontFamily: '"SF Mono", "Fira Code", "Cascadia Code", monospace',
            color: 'var(--personality-accent)',
            letterSpacing: '0.04em',
          }}>
            Developer Settings
          </div>
          <div style={{
            fontSize: 9,
            fontFamily: '"SF Mono", "Fira Code", "Cascadia Code", monospace',
            color: 'var(--text-tertiary)',
            marginTop: 2,
          }}>
            Behind the curtain
          </div>
        </div>

        {/* Terminal prompt icon */}
        <span style={{
          fontSize: 16,
          fontFamily: '"SF Mono", "Fira Code", "Cascadia Code", monospace',
          color: 'rgba(var(--personality-accent-rgb), 0.3)',
        }}>
          &gt;_
        </span>
      </div>

      {/* Settings categories */}
      {orderedCategories.map(cat => (
        <DevCategory key={cat} cat={cat}>
          {grouped[cat].map(s => (
            <SettingControl
              key={s.path}
              setting={s}
              onUpdate={onUpdate}
            />
          ))}
        </DevCategory>
      ))}

      {/* Footer */}
      <div style={{
        textAlign: 'center',
        paddingTop: 16,
        borderTop: '1px solid rgba(var(--personality-accent-rgb), 0.06)',
      }}>
        <span style={{
          fontSize: 9,
          fontFamily: '"SF Mono", "Fira Code", "Cascadia Code", monospace',
          color: 'var(--text-tertiary)',
          opacity: 0.5,
        }}>
          Changes to provider settings may require restart
        </span>
      </div>
    </motion.div>
  )
}
