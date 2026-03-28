/**
 * ControlsPanel — unified device control panel (replaces the old LightsPanel).
 *
 * Expandable sections that only appear when their devices are connected:
 *   - Lights: wraps the existing LightOrb, color strip, brightness, scenes
 *   - Audio: volume dial, output devices, Bluetooth scanner
 *   - Future: smart plugs, etc.
 *
 * Sections flow organically — no rigid card borders. Each section header
 * has a personality-accent bar and spring-animated collapse, matching the
 * SettingsPanel's CategorySection style.
 */

import { useState, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { AssistantStore } from '../types/assistant'
import { LightsSection } from './controls/LightsSection'
import { AudioSection } from './audio/AudioSection'

interface Props {
  store: AssistantStore
}

/* ───── Collapsible section wrapper ───── */

interface SectionProps {
  icon: React.ReactNode
  label: string
  defaultOpen?: boolean
  children: React.ReactNode
}

function ControlSection({ icon, label, defaultOpen = true, children }: SectionProps) {
  const [open, setOpen] = useState(defaultOpen)

  return (
    <section style={{ position: 'relative' }}>
      {/* Section header — tap to toggle */}
      <motion.button
        onClick={() => setOpen(!open)}
        whileHover={{ x: 2 }}
        transition={{ type: 'spring', stiffness: 400, damping: 25 }}
        style={{
          display: 'flex', alignItems: 'center', gap: 8,
          width: '100%', padding: '0 0 14px 0',
          background: 'none', border: 'none', cursor: 'pointer',
          position: 'relative',
        }}
      >
        {/* Accent bar */}
        <motion.div
          animate={{
            height: open ? 18 : 8,
            opacity: open ? 0.6 : 0.25,
          }}
          transition={{ type: 'spring', stiffness: 400, damping: 25 }}
          style={{
            width: 2, borderRadius: 1,
            background: 'var(--personality-accent)',
            flexShrink: 0,
          }}
        />
        {/* Icon */}
        <span style={{ display: 'flex', alignItems: 'center', opacity: 0.7 }}>
          {icon}
        </span>
        {/* Label */}
        <span style={{
          fontSize: 10, fontWeight: 600, letterSpacing: '0.14em',
          textTransform: 'uppercase' as const,
          color: 'rgba(var(--personality-accent-rgb), 0.5)',
          flex: 1, textAlign: 'left',
        }}>
          {label}
        </span>
        {/* Chevron */}
        <motion.svg
          width="12" height="12" viewBox="0 0 24 24"
          fill="none" stroke="rgba(var(--personality-accent-rgb), 0.5)"
          strokeWidth="2.5" strokeLinecap="round"
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
            <div style={{ paddingBottom: 8 }}>
              {children}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  )
}

/* ───── Section icons ───── */

function LightsIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24"
      fill="none" stroke="rgba(var(--personality-accent-rgb), 0.5)"
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
    >
      <path d="M9 18h6" />
      <path d="M10 22h4" />
      <path d="M12 2a7 7 0 0 0-4 12.7V17h8v-2.3A7 7 0 0 0 12 2z" />
    </svg>
  )
}

function AudioIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24"
      fill="none" stroke="rgba(var(--personality-accent-rgb), 0.5)"
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
    >
      <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
      <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
      <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
    </svg>
  )
}

/* ───── Main panel ───── */

export function ControlsPanel({ store }: Props) {
  // Always show lights section — even without state, the user should be able to control them
  const hasLights = true

  return (
    <div style={{
      padding: '24px 20px', maxWidth: 400, margin: '0 auto',
      display: 'flex', flexDirection: 'column', gap: 28,
    }}>
      {/* Lights section — only when lights are connected */}
      {hasLights && (
        <ControlSection
          icon={<LightsIcon />}
          label="Lights"
          defaultOpen={true}
        >
          <LightsSection store={store} />
        </ControlSection>
      )}

      {/* Audio section — always available */}
      <ControlSection
        icon={<AudioIcon />}
        label="Audio"
        defaultOpen={!hasLights}
      >
        <AudioSection store={store} />
      </ControlSection>
    </div>
  )
}
