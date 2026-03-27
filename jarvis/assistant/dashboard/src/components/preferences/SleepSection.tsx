/**
 * SleepSection -- bedtime routine flow for sleep mode settings.
 *
 * Instead of a list of toggles, presents sleep configuration as a
 * step-by-step "bedtime routine" with moon/sun animations.
 * Each step in the routine can be toggled and configured.
 */

import { useMemo } from 'react'
import { motion } from 'framer-motion'
import type { SettingSchema } from '../../types/assistant'

interface Props {
  settings: SettingSchema[]
  onUpdate: (path: string, value: any) => void
}

/* ------------------------------------------------------------------ */
/*  Animated moon/sun header                                           */
/* ------------------------------------------------------------------ */

function SleepWakeHeader() {
  return (
    <div style={{
      display: 'flex', justifyContent: 'center', gap: 32,
      padding: '8px 0 20px',
      position: 'relative',
    }}>
      {/* Connecting arc */}
      <svg width="120" height="40" viewBox="0 0 120 40"
        style={{ position: 'absolute', top: 16 }}
      >
        <motion.path
          d="M 15 30 Q 60 -5 105 30"
          fill="none"
          stroke="rgba(var(--personality-accent-rgb), 0.12)"
          strokeWidth="1"
          strokeDasharray="4 4"
          initial={{ pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 1.5, delay: 0.3 }}
        />
      </svg>

      {/* Moon */}
      <motion.div
        animate={{
          y: [0, -3, 0],
          rotate: [0, -5, 0],
        }}
        transition={{ duration: 6, repeat: Infinity, ease: 'easeInOut' }}
        style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}
      >
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none"
          stroke="var(--personality-accent)" strokeWidth="1.5" strokeLinecap="round"
          style={{ opacity: 0.6 }}
        >
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
        </svg>
        <span style={{ fontSize: 9, color: 'var(--text-tertiary)', fontWeight: 600, letterSpacing: '0.05em' }}>
          SLEEP
        </span>
      </motion.div>

      {/* Sun */}
      <motion.div
        animate={{
          y: [0, -3, 0],
          rotate: [0, 5, 0],
        }}
        transition={{ duration: 6, repeat: Infinity, ease: 'easeInOut', delay: 3 }}
        style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}
      >
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none"
          stroke="var(--personality-accent)" strokeWidth="1.5" strokeLinecap="round"
          style={{ opacity: 0.6 }}
        >
          <circle cx="12" cy="12" r="5" />
          <line x1="12" y1="1" x2="12" y2="3" />
          <line x1="12" y1="21" x2="12" y2="23" />
          <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
          <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
          <line x1="1" y1="12" x2="3" y2="12" />
          <line x1="21" y1="12" x2="23" y2="12" />
          <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
          <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
        </svg>
        <span style={{ fontSize: 9, color: 'var(--text-tertiary)', fontWeight: 600, letterSpacing: '0.05em' }}>
          WAKE
        </span>
      </motion.div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Routine step -- each sleep setting presented as a step             */
/* ------------------------------------------------------------------ */

interface RoutineStepProps {
  icon: React.ReactNode
  title: string
  description: string
  enabled: boolean
  onToggle: (v: boolean) => void
  /** Optional inline control when enabled (slider, text input) */
  control?: React.ReactNode
  index: number
  phase: 'sleep' | 'wake'
}

function RoutineStep({ icon, title, description, enabled, onToggle, control, index, phase }: RoutineStepProps) {
  const phaseColor = phase === 'sleep'
    ? 'rgba(var(--personality-accent-rgb), 0.5)'
    : 'rgba(var(--personality-accent-rgb), 0.7)'

  return (
    <motion.div
      initial={{ opacity: 0, x: phase === 'sleep' ? -20 : 20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: 0.1 + index * 0.06, type: 'spring', stiffness: 300, damping: 28 }}
      style={{
        display: 'flex', alignItems: 'flex-start', gap: 12,
        position: 'relative',
      }}
    >
      {/* Timeline connector dot */}
      <div style={{
        width: 28, height: 28,
        borderRadius: '50%',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: enabled
          ? 'rgba(var(--personality-accent-rgb), 0.12)'
          : 'var(--surface-subtle)',
        border: `1.5px solid ${enabled ? phaseColor : 'var(--border-subtle)'}`,
        flexShrink: 0,
        transition: 'all 0.3s ease',
      }}>
        <motion.div
          animate={{ opacity: enabled ? 0.8 : 0.3 }}
          style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}
        >
          {icon}
        </motion.div>
      </div>

      {/* Content */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          gap: 8,
        }}>
          <span style={{
            fontSize: 13, fontWeight: 500,
            color: enabled ? 'var(--text-primary)' : 'var(--text-tertiary)',
            transition: 'color 0.2s ease',
          }}>
            {title}
          </span>
          {/* Toggle */}
          <motion.button
            onClick={() => onToggle(!enabled)}
            animate={{
              background: enabled ? 'var(--personality-accent)' : 'var(--surface-subtle)',
              boxShadow: enabled
                ? 'inset 0 0 12px rgba(var(--personality-accent-rgb), 0.3)'
                : 'inset 0 1px 3px rgba(0,0,0,0.3)',
            }}
            transition={{ type: 'spring', stiffness: 400, damping: 28 }}
            style={{
              width: 40, height: 22, borderRadius: 11, padding: 2,
              border: 'none', cursor: 'pointer',
              display: 'flex', alignItems: 'center',
              justifyContent: enabled ? 'flex-end' : 'flex-start',
              flexShrink: 0,
            }}
          >
            <motion.div
              layout
              transition={{ type: 'spring', stiffness: 500, damping: 30 }}
              style={{
                width: 18, height: 18, borderRadius: 9,
                background: enabled ? '#fff' : 'var(--text-secondary)',
                boxShadow: '0 1px 4px rgba(0,0,0,0.3)',
              }}
            />
          </motion.button>
        </div>
        <div style={{
          fontSize: 10, color: 'var(--text-tertiary)', marginTop: 2,
        }}>
          {description}
        </div>
        {/* Inline control */}
        {enabled && control && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ type: 'spring', stiffness: 300, damping: 28 }}
            style={{ marginTop: 10 }}
          >
            {control}
          </motion.div>
        )}
      </div>
    </motion.div>
  )
}

/* ------------------------------------------------------------------ */
/*  Inline mini slider for volume/brightness values                    */
/* ------------------------------------------------------------------ */

function MiniSlider({ value, min, max, onChange }: {
  value: number; min: number; max: number
  onChange: (v: number) => void
}) {
  const pct = ((value - min) / (max - min)) * 100
  const trackRef = React.useRef<HTMLDivElement>(null)
  const draggingRef = React.useRef(false)

  const compute = (clientX: number) => {
    if (!trackRef.current) return value
    const r = trackRef.current.getBoundingClientRect()
    const ratio = Math.max(0, Math.min(1, (clientX - r.left) / r.width))
    return Math.round(min + ratio * (max - min))
  }

  return (
    <div data-gesture-ignore="true" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div
        ref={trackRef}
        onPointerDown={(e) => {
          draggingRef.current = true
          ;(e.target as HTMLElement).setPointerCapture(e.pointerId)
          onChange(compute(e.clientX))
        }}
        onPointerMove={(e) => { if (draggingRef.current) onChange(compute(e.clientX)) }}
        onPointerUp={() => { draggingRef.current = false }}
        style={{
          flex: 1, height: 6, borderRadius: 3,
          background: 'var(--surface-subtle)',
          cursor: 'pointer', position: 'relative',
          touchAction: 'none',
        }}
      >
        <motion.div
          animate={{ width: `${pct}%` }}
          transition={{ type: 'spring', stiffness: 300, damping: 30 }}
          style={{
            height: '100%', borderRadius: 3,
            background: 'var(--personality-accent)',
            opacity: 0.6,
          }}
        />
        <motion.div
          animate={{ left: `${pct}%` }}
          transition={{ type: 'spring', stiffness: 300, damping: 30 }}
          style={{
            position: 'absolute', top: '50%',
            transform: 'translate(-50%, -50%)',
            width: 14, height: 14, borderRadius: 7,
            background: 'var(--personality-accent)',
            boxShadow: '0 0 6px rgba(var(--personality-accent-rgb), 0.3)',
          }}
        />
      </div>
      <span style={{ fontSize: 11, color: 'var(--text-secondary)', fontFamily: 'monospace', minWidth: 28, textAlign: 'right' }}>
        {value}
      </span>
    </div>
  )
}

/* Need React import for useRef in MiniSlider */
import React from 'react'

/* ------------------------------------------------------------------ */
/*  Mini text input for search query                                   */
/* ------------------------------------------------------------------ */

function MiniTextInput({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const [local, setLocal] = React.useState(value)

  return (
    <input
      value={local}
      onChange={e => setLocal(e.target.value)}
      onBlur={() => { if (local !== value) onChange(local) }}
      onKeyDown={e => { if (e.key === 'Enter') onChange(local) }}
      style={{
        width: '100%',
        background: 'rgba(var(--personality-accent-rgb), 0.05)',
        border: '1px solid rgba(var(--personality-accent-rgb), 0.1)',
        borderRadius: 8,
        padding: '6px 10px',
        fontSize: 12,
        color: 'var(--text-primary)',
        outline: 'none',
        fontFamily: 'inherit',
      }}
      placeholder="e.g. rain sounds, lo-fi..."
    />
  )
}

/* ------------------------------------------------------------------ */
/*  Export                                                             */
/* ------------------------------------------------------------------ */

// Small icons for the routine steps
const ICONS = {
  lights_off: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
      stroke="var(--personality-accent)" strokeWidth="1.5" strokeLinecap="round">
      <path d="M9 18h6M10 22h4" />
      <path d="M15.09 14c.18-.98.65-1.74 1.41-2.5A4.65 4.65 0 0 0 18 8 6 6 0 0 0 6 8c0 1 .23 2.23 1.5 3.5.76.76 1.23 1.52 1.41 2.5" />
    </svg>
  ),
  music: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
      stroke="var(--personality-accent)" strokeWidth="1.5" strokeLinecap="round">
      <path d="M9 18V5l12-2v13" />
      <circle cx="6" cy="18" r="3" />
      <circle cx="18" cy="16" r="3" />
    </svg>
  ),
  volume: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
      stroke="var(--personality-accent)" strokeWidth="1.5" strokeLinecap="round">
      <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
      <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
    </svg>
  ),
  duck: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
      stroke="var(--personality-accent)" strokeWidth="1.5" strokeLinecap="round">
      <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
      <line x1="23" y1="9" x2="17" y2="15" />
      <line x1="17" y1="9" x2="23" y2="15" />
    </svg>
  ),
  restore_lights: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
      stroke="var(--personality-accent)" strokeWidth="1.5" strokeLinecap="round">
      <circle cx="12" cy="12" r="5" />
      <line x1="12" y1="1" x2="12" y2="3" />
      <line x1="12" y1="21" x2="12" y2="23" />
      <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
      <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
      <line x1="1" y1="12" x2="3" y2="12" />
      <line x1="21" y1="12" x2="23" y2="12" />
    </svg>
  ),
  restore_vol: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
      stroke="var(--personality-accent)" strokeWidth="1.5" strokeLinecap="round">
      <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
      <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
      <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
    </svg>
  ),
  brightness: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
      stroke="var(--personality-accent)" strokeWidth="1.5" strokeLinecap="round">
      <circle cx="12" cy="12" r="5" />
      <line x1="12" y1="1" x2="12" y2="3" />
      <line x1="12" y1="21" x2="12" y2="23" />
    </svg>
  ),
}

export function SleepSection({ settings, onUpdate }: Props) {
  const settingsMap = useMemo(() => {
    const m: Record<string, SettingSchema> = {}
    for (const s of settings) m[s.path] = s
    return m
  }, [settings])

  const get = (path: string) => settingsMap[path]
  const val = (path: string) => settingsMap[path]?.value

  // Sleep phase steps
  const sleepSteps = [
    {
      setting: 'sleep_mode.turn_off_lights',
      icon: ICONS.lights_off,
      title: 'Dim the lights',
      description: 'Turn off all lights as you fall asleep',
      phase: 'sleep' as const,
    },
    {
      setting: 'sleep_mode.play_sleep_music',
      icon: ICONS.music,
      title: 'Play sleep sounds',
      description: 'Gentle music to drift off to',
      phase: 'sleep' as const,
      controls: [
        { path: 'sleep_mode.sleep_music_query', type: 'text' as const },
        { path: 'sleep_mode.sleep_music_volume', type: 'slider' as const },
      ],
    },
    {
      setting: 'sleep_mode.duck_existing_music',
      icon: ICONS.duck,
      title: 'Soften playing music',
      description: 'Lower volume instead of stopping what is playing',
      phase: 'sleep' as const,
    },
  ]

  const wakeSteps = [
    {
      setting: 'sleep_mode.restore_lights_on_wake',
      icon: ICONS.restore_lights,
      title: 'Bring back the lights',
      description: 'Gently restore lights when you wake',
      phase: 'wake' as const,
      controls: [
        { path: 'sleep_mode.wake_lights_brightness', type: 'slider' as const },
      ],
    },
    {
      setting: 'sleep_mode.restore_volume_on_wake',
      icon: ICONS.restore_vol,
      title: 'Restore volume',
      description: 'Return music to pre-sleep volume',
      phase: 'wake' as const,
    },
  ]

  return (
    <motion.section
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.15, type: 'spring', stiffness: 300, damping: 28 }}
    >
      <SleepWakeHeader />

      {/* Sleep routine */}
      <div style={{
        fontSize: 10, fontWeight: 600, letterSpacing: '0.12em',
        textTransform: 'uppercase' as const,
        color: 'rgba(var(--personality-accent-rgb), 0.35)',
        marginBottom: 14,
      }}>
        When you say goodnight...
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginBottom: 28 }}>
        {sleepSteps.map((step, i) => {
          const s = get(step.setting)
          if (!s) return null
          const enabled = !!s.value

          let controlEl: React.ReactNode = null
          if (step.controls) {
            controlEl = (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {step.controls.map(c => {
                  const cs = get(c.path)
                  if (!cs) return null
                  if (c.type === 'slider') {
                    return (
                      <MiniSlider
                        key={c.path}
                        value={typeof cs.value === 'number' ? cs.value : 0}
                        min={cs.min ?? 0}
                        max={cs.max ?? 100}
                        onChange={v => onUpdate(c.path, v)}
                      />
                    )
                  }
                  return (
                    <MiniTextInput
                      key={c.path}
                      value={String(cs.value ?? '')}
                      onChange={v => onUpdate(c.path, v)}
                    />
                  )
                })}
              </div>
            )
          }

          return (
            <RoutineStep
              key={step.setting}
              icon={step.icon}
              title={step.title}
              description={step.description}
              enabled={enabled}
              onToggle={v => onUpdate(step.setting, v)}
              control={controlEl}
              index={i}
              phase={step.phase}
            />
          )
        })}
      </div>

      {/* Wake routine */}
      <div style={{
        fontSize: 10, fontWeight: 600, letterSpacing: '0.12em',
        textTransform: 'uppercase' as const,
        color: 'rgba(var(--personality-accent-rgb), 0.35)',
        marginBottom: 14,
      }}>
        When you wake up...
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {wakeSteps.map((step, i) => {
          const s = get(step.setting)
          if (!s) return null
          const enabled = !!s.value

          let controlEl: React.ReactNode = null
          if (step.controls) {
            controlEl = (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {step.controls.map(c => {
                  const cs = get(c.path)
                  if (!cs) return null
                  if (c.type === 'slider') {
                    return (
                      <MiniSlider
                        key={c.path}
                        value={typeof cs.value === 'number' ? cs.value : 0}
                        min={cs.min ?? 0}
                        max={cs.max ?? 100}
                        onChange={v => onUpdate(c.path, v)}
                      />
                    )
                  }
                  return (
                    <MiniTextInput
                      key={c.path}
                      value={String(cs.value ?? '')}
                      onChange={v => onUpdate(c.path, v)}
                    />
                  )
                })}
              </div>
            )
          }

          return (
            <RoutineStep
              key={step.setting}
              icon={step.icon}
              title={step.title}
              description={step.description}
              enabled={enabled}
              onToggle={v => onUpdate(step.setting, v)}
              control={controlEl}
              index={i}
              phase={step.phase}
            />
          )
        })}
      </div>
    </motion.section>
  )
}
