/**
 * SettingControl — renders a single setting based on its schema type.
 *
 * Supports: bool (spring toggle with inner glow), float/int (drag-enabled
 * slider with gradient fill), choice (animated sliding pill segmented
 * control), string (underline input with warm focus glow).
 *
 * All controls use personality accent color and spring animations.
 */

import { useState, useRef, useCallback, useEffect, useLayoutEffect } from 'react'
import { motion, useMotionValue, useTransform, AnimatePresence } from 'framer-motion'
import type { SettingSchema } from '../../types/assistant'

interface Props {
  setting: SettingSchema
  onUpdate: (path: string, value: any) => void
}

/* ──────────────────────── Toggle (bool) ──────────────────────── */

function Toggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <motion.button
      onClick={() => onChange(!checked)}
      aria-pressed={checked}
      animate={{
        background: checked
          ? 'var(--personality-accent)'
          : 'rgba(255,255,255,0.08)',
        boxShadow: checked
          ? 'inset 0 0 12px rgba(var(--personality-accent-rgb), 0.3)'
          : 'inset 0 1px 3px rgba(0,0,0,0.3)',
      }}
      transition={{ type: 'spring', stiffness: 400, damping: 28 }}
      style={{
        width: 52, height: 28, borderRadius: 14, padding: 3,
        border: 'none', cursor: 'pointer',
        display: 'flex', alignItems: 'center',
        justifyContent: checked ? 'flex-end' : 'flex-start',
      }}
    >
      <motion.div
        layout
        transition={{ type: 'spring', stiffness: 500, damping: 30 }}
        style={{
          width: 22, height: 22, borderRadius: 11,
          background: checked ? '#fff' : 'rgba(255,255,255,0.35)',
          boxShadow: '0 1px 4px rgba(0,0,0,0.3)',
        }}
      />
    </motion.button>
  )
}

/* ──────────────────────── Slider (float/int) ──────────────────── */

function Slider({ value, min, max, step, color, onChange }: {
  value: number; min: number; max: number; step: number; color: string
  onChange: (v: number) => void
}) {
  const trackRef = useRef<HTMLDivElement>(null)
  const draggingRef = useRef(false)
  const pct = ((value - min) / (max - min)) * 100

  const computeValue = useCallback((clientX: number) => {
    if (!trackRef.current) return value
    const r = trackRef.current.getBoundingClientRect()
    const ratio = Math.max(0, Math.min(1, (clientX - r.left) / r.width))
    const raw = min + ratio * (max - min)
    return step >= 1 ? Math.round(raw) : Math.round(raw * 100) / 100
  }, [min, max, step, value])

  const handlePointerDown = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    draggingRef.current = true
    ;(e.target as HTMLElement).setPointerCapture(e.pointerId)
    onChange(computeValue(e.clientX))
  }, [computeValue, onChange])

  const handlePointerMove = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    if (!draggingRef.current) return
    onChange(computeValue(e.clientX))
  }, [computeValue, onChange])

  const handlePointerUp = useCallback(() => {
    draggingRef.current = false
  }, [])

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
      <div
        ref={trackRef}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        style={{
          flex: 1, height: 12, borderRadius: 6,
          background: 'rgba(255,255,255,0.06)', cursor: 'pointer',
          position: 'relative', touchAction: 'none',
        }}
      >
        {/* Filled track with gradient */}
        <motion.div
          animate={{ width: `${pct}%` }}
          transition={{ type: 'spring', stiffness: 300, damping: 30 }}
          style={{
            height: '100%', borderRadius: 6,
            background: `linear-gradient(90deg, rgba(var(--personality-accent-rgb), 0.15), ${color})`,
          }}
        />
        {/* Thumb */}
        <motion.div
          animate={{ left: `${pct}%` }}
          transition={{ type: 'spring', stiffness: 300, damping: 30 }}
          style={{
            position: 'absolute', top: '50%', transform: 'translate(-50%, -50%)',
            width: 22, height: 22, borderRadius: 11,
            background: '#1a1820',
            border: `2.5px solid ${color}`,
            boxShadow: `0 0 10px ${color}44, 0 2px 6px rgba(0,0,0,0.4)`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}
        >
          {/* Value inside thumb for floats, or show nothing for ints */}
        </motion.div>
      </div>
      <span style={{
        fontSize: 12, color: 'rgba(255,255,255,0.5)', fontFamily: 'monospace',
        minWidth: 40, textAlign: 'right',
      }}>
        {step >= 1 ? value : value.toFixed(2)}
      </span>
    </div>
  )
}

/* ──────────────────── Segmented Control (choice) ─────────────── */

function SegmentedControl({ value, choices, onChange }: {
  value: string; choices: string[]; onChange: (v: string) => void
}) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [pillStyle, setPillStyle] = useState({ left: 0, width: 0 })
  const selectedIndex = choices.indexOf(value)

  // Measure the selected button position for the sliding pill
  useLayoutEffect(() => {
    if (!containerRef.current || selectedIndex < 0) return
    const buttons = containerRef.current.querySelectorAll<HTMLButtonElement>('[data-seg-btn]')
    const btn = buttons[selectedIndex]
    if (!btn) return
    setPillStyle({
      left: btn.offsetLeft,
      width: btn.offsetWidth,
    })
  }, [selectedIndex, choices])

  return (
    <div
      ref={containerRef}
      style={{
        display: 'flex', gap: 0, padding: 3, borderRadius: 10,
        background: 'rgba(255,255,255,0.04)',
        border: '1px solid rgba(255,255,255,0.06)',
        position: 'relative',
      }}
    >
      {/* Sliding pill indicator */}
      {selectedIndex >= 0 && (
        <motion.div
          animate={{ left: pillStyle.left, width: pillStyle.width }}
          transition={{ type: 'spring', stiffness: 400, damping: 30 }}
          style={{
            position: 'absolute', top: 3, bottom: 3,
            borderRadius: 8,
            background: 'rgba(var(--personality-accent-rgb), 0.2)',
            border: '1px solid rgba(var(--personality-accent-rgb), 0.15)',
          }}
        />
      )}
      {choices.map(c => (
        <button
          key={c}
          data-seg-btn=""
          onClick={() => onChange(c)}
          style={{
            flex: 1, padding: '6px 10px', borderRadius: 8, border: 'none',
            cursor: 'pointer', fontSize: 11, fontWeight: 500,
            background: 'transparent',
            color: c === value ? 'var(--personality-accent)' : 'rgba(255,255,255,0.35)',
            position: 'relative', zIndex: 1,
            transition: 'color 0.2s ease',
          }}
        >
          {c}
        </button>
      ))}
    </div>
  )
}

/* ──────────────────── Text Input (string) ────────────────────── */

function TextInput({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const [local, setLocal] = useState(value)
  const [focused, setFocused] = useState(false)

  return (
    <div style={{ position: 'relative' }}>
      <input
        value={local}
        onChange={e => setLocal(e.target.value)}
        onBlur={() => { setFocused(false); if (local !== value) onChange(local) }}
        onFocus={() => setFocused(true)}
        onKeyDown={e => { if (e.key === 'Enter') onChange(local) }}
        style={{
          background: 'transparent', border: 'none',
          borderBottom: '1px solid rgba(255,255,255,0.12)',
          color: 'rgba(255,255,255,0.8)', fontSize: 13, padding: '6px 0',
          outline: 'none', width: '100%', fontFamily: 'inherit',
        }}
      />
      {/* Warm focus glow line */}
      <motion.div
        animate={{
          scaleX: focused ? 1 : 0,
          opacity: focused ? 1 : 0,
        }}
        transition={{ type: 'spring', stiffness: 400, damping: 30 }}
        style={{
          position: 'absolute', bottom: 0, left: 0, right: 0,
          height: 2, borderRadius: 1,
          background: 'var(--personality-accent)',
          transformOrigin: 'center',
          boxShadow: '0 0 8px rgba(var(--personality-accent-rgb), 0.3)',
        }}
      />
    </div>
  )
}

/* ──────────────────── Exported Control ───────────────────────── */

export function SettingControl({ setting, onUpdate }: Props) {
  const { path, type, label, description, value, choices, min, max } = setting

  const control = (() => {
    switch (type) {
      case 'bool':
        return <Toggle checked={!!value} onChange={v => onUpdate(path, v)} />
      case 'float':
        return (
          <Slider
            value={typeof value === 'number' ? value : parseFloat(value) || 0}
            min={min ?? 0} max={max ?? 1} step={0.01}
            color="var(--personality-accent)" onChange={v => onUpdate(path, v)}
          />
        )
      case 'int':
        return (
          <Slider
            value={typeof value === 'number' ? value : parseInt(value) || 0}
            min={min ?? 0} max={max ?? 100} step={1}
            color="var(--personality-accent)" onChange={v => onUpdate(path, v)}
          />
        )
      case 'choice':
        return (
          <SegmentedControl
            value={String(value ?? '')} choices={choices ?? []}
            onChange={v => onUpdate(path, v)}
          />
        )
      case 'string':
      default:
        return <TextInput value={String(value ?? '')} onChange={v => onUpdate(path, v)} />
    }
  })()

  const isInline = type === 'bool'

  return (
    <div style={{
      display: isInline ? 'flex' : 'block',
      alignItems: isInline ? 'center' : undefined,
      justifyContent: isInline ? 'space-between' : undefined,
      gap: isInline ? 12 : 6,
    }}>
      <div style={{ flex: isInline ? 1 : undefined }}>
        <div style={{ fontSize: 13, color: 'rgba(255,255,255,0.8)', fontWeight: 500 }}>
          {label}
        </div>
        {description && (
          <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.3)', marginTop: 2 }}>
            {description}
          </div>
        )}
      </div>
      <div style={{ marginTop: isInline ? 0 : 8 }}>{control}</div>
    </div>
  )
}
