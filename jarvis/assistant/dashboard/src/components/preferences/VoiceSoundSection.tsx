/**
 * VoiceSoundSection -- voice + music preferences with waveform previews.
 *
 * Voice selection shows mini waveform animations for each option.
 * Speech speed uses a spring-based "tempo" visualizer.
 * Music prefs are presented with personality-colored accents.
 */

import { useState, useMemo, useRef, useCallback } from 'react'
import { motion } from 'framer-motion'
import type { SettingSchema } from '../../types/assistant'

interface Props {
  settings: SettingSchema[]
  onUpdate: (path: string, value: any) => void
}

/* ------------------------------------------------------------------ */
/*  Mini waveform animation                                            */
/* ------------------------------------------------------------------ */

function MiniWaveform({ active, color, seed }: { active: boolean; color: string; seed: number }) {
  const bars = 7
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 1.5, height: 24 }}>
      {Array.from({ length: bars }).map((_, i) => {
        const baseHeight = 4 + ((seed * (i + 1) * 7) % 16)
        return (
          <motion.div
            key={i}
            animate={{
              height: active ? [baseHeight, baseHeight * 0.3, baseHeight] : 3,
              opacity: active ? 0.8 : 0.2,
            }}
            transition={{
              duration: 0.4 + (i * 0.08),
              repeat: active ? Infinity : 0,
              repeatType: 'mirror',
              delay: i * 0.05,
              ease: 'easeInOut',
            }}
            style={{
              width: 3,
              borderRadius: 1.5,
              background: color,
            }}
          />
        )
      })}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Voice provider card                                                */
/* ------------------------------------------------------------------ */

function VoiceCard({ name, active, onClick, index }: {
  name: string; active: boolean; onClick: () => void; index: number
}) {
  const [hovered, setHovered] = useState(false)

  // Friendly labels
  const LABELS: Record<string, string> = {
    kokoro: 'Kokoro',
    piper: 'Piper',
    xtts: 'XTTS',
    edge: 'Edge',
  }

  const DESCS: Record<string, string> = {
    kokoro: 'Natural, Hindi support',
    piper: 'Fast, lightweight',
    xtts: 'Voice cloning',
    edge: 'Cloud, premium quality',
  }

  return (
    <motion.button
      onClick={onClick}
      onHoverStart={() => setHovered(true)}
      onHoverEnd={() => setHovered(false)}
      whileTap={{ scale: 0.96 }}
      animate={{
        borderColor: active
          ? 'var(--personality-accent)'
          : 'var(--border-subtle)',
        boxShadow: active
          ? '0 0 16px rgba(var(--personality-accent-rgb), 0.15)'
          : 'none',
      }}
      transition={{ type: 'spring', stiffness: 400, damping: 28 }}
      style={{
        flex: 1,
        minWidth: 0,
        padding: '12px 10px',
        borderRadius: 14,
        border: '1.5px solid var(--border-subtle)',
        background: active
          ? 'rgba(var(--personality-accent-rgb), 0.06)'
          : 'transparent',
        cursor: 'pointer',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 8,
      }}
    >
      <MiniWaveform
        active={active || hovered}
        color={active ? 'var(--personality-accent)' : 'var(--text-tertiary)'}
        seed={index + 1}
      />
      <span style={{
        fontSize: 11, fontWeight: 600,
        color: active ? 'var(--personality-accent)' : 'var(--text-secondary)',
      }}>
        {LABELS[name] || name}
      </span>
      <span style={{
        fontSize: 9, color: 'var(--text-tertiary)',
        whiteSpace: 'nowrap',
      }}>
        {DESCS[name] || ''}
      </span>
    </motion.button>
  )
}

/* ------------------------------------------------------------------ */
/*  Speed visualizer -- tempo dots                                     */
/* ------------------------------------------------------------------ */

function SpeedVisualizer({ speed }: { speed: number }) {
  const dots = 5
  return (
    <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
      {Array.from({ length: dots }).map((_, i) => (
        <motion.div
          key={i}
          animate={{
            scale: [0.5, 1.2, 0.5],
            opacity: [0.3, 0.8, 0.3],
          }}
          transition={{
            duration: 1.5 / speed,
            repeat: Infinity,
            delay: i * (0.2 / speed),
            ease: 'easeInOut',
          }}
          style={{
            width: 5, height: 5, borderRadius: '50%',
            background: 'var(--personality-accent)',
          }}
        />
      ))}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Inline slider (reusable)                                           */
/* ------------------------------------------------------------------ */

function InlineSlider({ value, min, max, step, label, onChange }: {
  value: number; min: number; max: number; step: number; label: string
  onChange: (v: number) => void
}) {
  const trackRef = useRef<HTMLDivElement>(null)
  const draggingRef = useRef(false)
  const pct = ((value - min) / (max - min)) * 100

  const compute = useCallback((clientX: number) => {
    if (!trackRef.current) return value
    const r = trackRef.current.getBoundingClientRect()
    const ratio = Math.max(0, Math.min(1, (clientX - r.left) / r.width))
    const raw = min + ratio * (max - min)
    return step >= 1 ? Math.round(raw) : Math.round(raw * 100) / 100
  }, [min, max, step, value])

  return (
    <div data-gesture-ignore="true">
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        marginBottom: 8,
      }}>
        <span style={{ fontSize: 12, color: 'var(--text-primary)', fontWeight: 500 }}>
          {label}
        </span>
        <span style={{ fontSize: 11, color: 'var(--text-secondary)', fontFamily: 'monospace' }}>
          {step >= 1 ? value : value.toFixed(2)}
        </span>
      </div>
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
          height: 8, borderRadius: 4,
          background: 'var(--surface-subtle)',
          cursor: 'pointer', position: 'relative',
          touchAction: 'none',
        }}
      >
        <motion.div
          animate={{ width: `${pct}%` }}
          transition={{ type: 'spring', stiffness: 300, damping: 30 }}
          style={{
            height: '100%', borderRadius: 4,
            background: 'var(--personality-accent)',
            opacity: 0.5,
          }}
        />
        <motion.div
          animate={{ left: `${pct}%` }}
          transition={{ type: 'spring', stiffness: 300, damping: 30 }}
          style={{
            position: 'absolute', top: '50%',
            transform: 'translate(-50%, -50%)',
            width: 16, height: 16, borderRadius: 8,
            background: 'var(--personality-accent)',
            boxShadow: '0 0 6px rgba(var(--personality-accent-rgb), 0.3)',
          }}
        />
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Section header                                                     */
/* ------------------------------------------------------------------ */

function SubHeader({ children }: { children: string }) {
  return (
    <div style={{
      fontSize: 10, fontWeight: 600, letterSpacing: '0.12em',
      textTransform: 'uppercase' as const,
      color: 'rgba(var(--personality-accent-rgb), 0.45)',
      marginBottom: 12,
    }}>
      {children}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Toggle row                                                         */
/* ------------------------------------------------------------------ */

function ToggleRow({ label, description, checked, onChange }: {
  label: string; description: string; checked: boolean; onChange: (v: boolean) => void
}) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      gap: 12,
    }}>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 13, color: 'var(--text-primary)', fontWeight: 500 }}>{label}</div>
        <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 2 }}>{description}</div>
      </div>
      <motion.button
        onClick={() => onChange(!checked)}
        animate={{
          background: checked ? 'var(--personality-accent)' : 'var(--surface-subtle)',
          boxShadow: checked
            ? 'inset 0 0 12px rgba(var(--personality-accent-rgb), 0.3)'
            : 'inset 0 1px 3px rgba(0,0,0,0.3)',
        }}
        transition={{ type: 'spring', stiffness: 400, damping: 28 }}
        style={{
          width: 44, height: 24, borderRadius: 12, padding: 2,
          border: 'none', cursor: 'pointer',
          display: 'flex', alignItems: 'center',
          justifyContent: checked ? 'flex-end' : 'flex-start',
          flexShrink: 0,
        }}
      >
        <motion.div
          layout
          transition={{ type: 'spring', stiffness: 500, damping: 30 }}
          style={{
            width: 20, height: 20, borderRadius: 10,
            background: checked ? '#fff' : 'var(--text-secondary)',
            boxShadow: '0 1px 4px rgba(0,0,0,0.3)',
          }}
        />
      </motion.button>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Export                                                             */
/* ------------------------------------------------------------------ */

export function VoiceSoundSection({ settings, onUpdate }: Props) {
  const settingsMap = useMemo(() => {
    const m: Record<string, SettingSchema> = {}
    for (const s of settings) m[s.path] = s
    return m
  }, [settings])

  const voiceEnabled = settingsMap['voice.enabled']
  const voiceSpeed = settingsMap['voice.speed']
  const voiceFallback = settingsMap['voice.fallback_provider']
  const musicResults = settingsMap['music.search_results']
  const musicAutoPlay = settingsMap['music.auto_play_first']

  const fallbackChoices = voiceFallback?.choices ?? []
  const currentFallback = String(voiceFallback?.value ?? '')

  return (
    <motion.section
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.2, type: 'spring', stiffness: 300, damping: 28 }}
      style={{ display: 'flex', flexDirection: 'column', gap: 28 }}
    >
      {/* Voice toggle */}
      {voiceEnabled && (
        <ToggleRow
          label="Text-to-Speech"
          description="Enable or disable voice output"
          checked={!!voiceEnabled.value}
          onChange={v => onUpdate(voiceEnabled.path, v)}
        />
      )}

      {/* Voice selection */}
      {fallbackChoices.length > 0 && (
        <div>
          <SubHeader>Voice Engine</SubHeader>
          <div style={{
            display: 'flex', gap: 8,
            overflowX: 'auto',
            scrollbarWidth: 'none',
            msOverflowStyle: 'none',
            paddingBottom: 4,
          }}>
            {fallbackChoices.map((name, i) => (
              <VoiceCard
                key={name}
                name={name}
                active={name === currentFallback}
                onClick={() => onUpdate(voiceFallback!.path, name)}
                index={i}
              />
            ))}
          </div>
        </div>
      )}

      {/* Speech speed */}
      {voiceSpeed && (
        <div>
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            marginBottom: 4,
          }}>
            <SubHeader>Speech Speed</SubHeader>
            <SpeedVisualizer speed={typeof voiceSpeed.value === 'number' ? voiceSpeed.value : 1} />
          </div>
          <InlineSlider
            value={typeof voiceSpeed.value === 'number' ? voiceSpeed.value : 1}
            min={voiceSpeed.min ?? 0.5}
            max={voiceSpeed.max ?? 2.0}
            step={0.01}
            label=""
            onChange={v => onUpdate(voiceSpeed.path, v)}
          />
        </div>
      )}

      {/* Music preferences */}
      <div>
        <SubHeader>Music</SubHeader>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {musicResults && (
            <InlineSlider
              value={typeof musicResults.value === 'number' ? musicResults.value : 5}
              min={musicResults.min ?? 1}
              max={musicResults.max ?? 20}
              step={1}
              label="Search results"
              onChange={v => onUpdate(musicResults.path, v)}
            />
          )}
          {musicAutoPlay && (
            <ToggleRow
              label="Auto-play first result"
              description="Play the best match automatically"
              checked={!!musicAutoPlay.value}
              onChange={v => onUpdate(musicAutoPlay.path, v)}
            />
          )}
        </div>
      </div>
    </motion.section>
  )
}
