/**
 * PreferencesPanel -- the user-facing settings experience.
 *
 * Four creative sections with human-readable names:
 *   1. Personality Picker (existing, unchanged)
 *   2. Appearance (radial brightness + live background previews)
 *   3. Sleep & Wake (bedtime routine flow)
 *   4. Voice & Sound (waveform previews, speed visualizer)
 *   + "Advanced..." link at bottom opens developer settings
 *
 * Developer Settings is an overlay within this same panel.
 * Each section has its own micro-identity and spring animations.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { AssistantStore, SettingSchema } from '../types/assistant'
import { PersonalityPicker } from './settings/PersonalityPicker'
import { AppearanceSection } from './preferences/AppearanceSection'
import { SleepSection } from './preferences/SleepSection'
import { VoiceSoundSection } from './preferences/VoiceSoundSection'
import { DeveloperSettings } from './DeveloperSettings'

interface Props {
  store: AssistantStore
}

/* ------------------------------------------------------------------ */
/*  Section Divider -- a thin accent breath between sections           */
/* ------------------------------------------------------------------ */

function SectionDivider() {
  return (
    <div style={{
      display: 'flex', justifyContent: 'center',
      padding: '4px 0',
    }}>
      <motion.div
        initial={{ scaleX: 0 }}
        animate={{ scaleX: 1 }}
        transition={{ delay: 0.3, type: 'spring', stiffness: 300, damping: 30 }}
        style={{
          width: 40, height: 1,
          borderRadius: 0.5,
          background: 'rgba(var(--personality-accent-rgb), 0.12)',
          transformOrigin: 'center',
        }}
      />
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Loading skeleton                                                   */
/* ------------------------------------------------------------------ */

function LoadingSkeleton() {
  return (
    <div style={{ padding: 32, textAlign: 'center' }}>
      <motion.div
        animate={{ opacity: [0.2, 0.5, 0.2] }}
        transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
        style={{ color: 'var(--personality-accent)', fontSize: 13, fontWeight: 500 }}
      >
        Loading preferences...
      </motion.div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Export -- renamed internally to PreferencesPanel but keeping       */
/*  SettingsPanel export for backward compat with App.tsx              */
/* ------------------------------------------------------------------ */

export function SettingsPanel({ store }: Props) {
  const settings = store?.settings ?? []
  const actions = store?.actions
  const personalities = store?.personalities ?? []
  const personality = store?.personality ?? 'jarvis'

  // Track whether developer settings overlay is open
  const [showDev, setShowDev] = useState(false)

  // Request settings once on mount
  const requestedRef = useRef(false)
  useEffect(() => {
    if (!requestedRef.current && !settings.length && actions?.requestSettings) {
      requestedRef.current = true
      actions.requestSettings()
    }
  }, [])

  // Group settings by category for sub-components
  const sleepSettings = useMemo(
    () => settings.filter(s => s.category === 'sleep_mode' && s.editable !== false),
    [settings],
  )

  const voiceMusicSettings = useMemo(
    () => settings.filter(s => (s.category === 'voice' || s.category === 'music') && s.editable !== false),
    [settings],
  )

  // Brightness adjusting state -- fade other sections
  const [adjustingBrightness, setAdjustingBrightness] = useState(false)
  const handleBrightnessAdjusting = useCallback((isAdjusting: boolean) => {
    setAdjustingBrightness(isAdjusting)
  }, [])

  if (!settings.length) {
    return <LoadingSkeleton />
  }

  return (
    <AnimatePresence mode="wait">
      {showDev ? (
        <motion.div
          key="dev"
          initial={{ opacity: 0, x: 40 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: 40 }}
          transition={{ type: 'spring', stiffness: 300, damping: 28 }}
        >
          <DeveloperSettings
            settings={settings}
            onUpdate={actions.updateSetting}
            onBack={() => setShowDev(false)}
          />
        </motion.div>
      ) : (
        <motion.div
          key="prefs"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0, x: -40 }}
          transition={{ type: 'spring', stiffness: 300, damping: 28 }}
          style={{
            padding: '24px 20px 40px',
            maxWidth: 400,
            margin: '0 auto',
            display: 'flex',
            flexDirection: 'column',
            gap: 28,
          }}
        >
          {/* 1. Personality Picker */}
          <motion.div animate={{ opacity: adjustingBrightness ? 0.15 : 1 }} transition={{ duration: 0.3 }}>
            {personalities.length > 0 && (
              <PersonalityPicker
                personalities={personalities}
                active={personality}
                onSwitch={actions.switchPersonality}
              />
            )}
          </motion.div>

          <SectionDivider />

          {/* 2. Appearance */}
          <AppearanceSection onAdjusting={handleBrightnessAdjusting} />

          <SectionDivider />

          {/* 3. Sleep & Wake */}
          <motion.div animate={{ opacity: adjustingBrightness ? 0.08 : 1 }} transition={{ duration: 0.3 }}>
            {sleepSettings.length > 0 && (
              <SleepSection
                settings={sleepSettings}
                onUpdate={actions.updateSetting}
              />
            )}
          </motion.div>

          <SectionDivider />

          {/* 4. Voice & Sound */}
          <motion.div animate={{ opacity: adjustingBrightness ? 0.08 : 1 }} transition={{ duration: 0.3 }}>
            {voiceMusicSettings.length > 0 && (
              <VoiceSoundSection
                settings={voiceMusicSettings}
                onUpdate={actions.updateSetting}
              />
            )}
          </motion.div>

          {/* 5. Advanced link */}
          <motion.div
            animate={{ opacity: adjustingBrightness ? 0.05 : 1 }}
            transition={{ duration: 0.3 }}
            style={{ textAlign: 'center', paddingTop: 8 }}
          >
            <motion.button
              onClick={() => setShowDev(true)}
              whileHover={{ opacity: 0.7 }}
              whileTap={{ scale: 0.97 }}
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                fontSize: 11,
                color: 'var(--text-tertiary)',
                opacity: 0.4,
                fontWeight: 500,
                letterSpacing: '0.02em',
                padding: '8px 16px',
              }}
            >
              Advanced...
            </motion.button>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
