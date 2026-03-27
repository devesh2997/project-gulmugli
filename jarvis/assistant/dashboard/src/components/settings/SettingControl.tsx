/**
 * SettingControl — renders a single setting based on its schema type.
 *
 * Supports: bool (animated toggle), float/int (slider), string (text input),
 * choice (segmented control). All controls use personality accent color.
 */

import { useState, useRef, useCallback } from 'react'
import { motion } from 'framer-motion'
import type { SettingSchema } from '../../types/assistant'

interface Props {
  setting: SettingSchema
  onUpdate: (path: string, value: any) => void
}

function Toggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <motion.button
      onClick={() => onChange(!checked)}
      aria-pressed={checked}
      style={{
        width: 44, height: 24, borderRadius: 12, padding: 2,
        background: checked ? 'var(--personality-accent)' : 'rgba(255,255,255,0.1)',
        border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center',
        justifyContent: checked ? 'flex-end' : 'flex-start',
      }}
    >
      <motion.div
        layout
        transition={{ type: 'spring', stiffness: 500, damping: 30 }}
        style={{
          width: 20, height: 20, borderRadius: 10,
          background: checked ? '#fff' : 'rgba(255,255,255,0.4)',
        }}
      />
    </motion.button>
  )
}

function Slider({ value, min, max, step, color, onChange }: {
  value: number; min: number; max: number; step: number; color: string
  onChange: (v: number) => void
}) {
  const trackRef = useRef<HTMLDivElement>(null)
  const pct = ((value - min) / (max - min)) * 100

  const handleClick = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (!trackRef.current) return
    const r = trackRef.current.getBoundingClientRect()
    const ratio = Math.max(0, Math.min(1, (e.clientX - r.left) / r.width))
    const raw = min + ratio * (max - min)
    onChange(step >= 1 ? Math.round(raw) : Math.round(raw * 100) / 100)
  }, [min, max, step, onChange])

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
      <div
        ref={trackRef}
        onClick={handleClick}
        style={{
          flex: 1, height: 6, borderRadius: 3,
          background: 'rgba(255,255,255,0.08)', cursor: 'pointer', position: 'relative',
        }}
      >
        <motion.div
          style={{ height: '100%', borderRadius: 3, background: color }}
          animate={{ width: `${pct}%` }}
          transition={{ type: 'spring', stiffness: 300, damping: 30 }}
        />
        <motion.div
          animate={{ left: `${pct}%` }}
          transition={{ type: 'spring', stiffness: 300, damping: 30 }}
          style={{
            position: 'absolute', top: '50%', transform: 'translate(-50%, -50%)',
            width: 16, height: 16, borderRadius: 8,
            background: color, boxShadow: `0 0 8px ${color}`,
          }}
        />
      </div>
      <span style={{
        fontSize: 12, color: 'rgba(255,255,255,0.5)', fontFamily: 'monospace',
        minWidth: 36, textAlign: 'right',
      }}>
        {step >= 1 ? value : value.toFixed(2)}
      </span>
    </div>
  )
}

function TextInput({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const [local, setLocal] = useState(value)
  return (
    <input
      value={local}
      onChange={e => setLocal(e.target.value)}
      onBlur={() => { if (local !== value) onChange(local) }}
      onKeyDown={e => { if (e.key === 'Enter') onChange(local) }}
      style={{
        background: 'transparent', border: 'none',
        borderBottom: '1px solid rgba(255,255,255,0.15)',
        color: 'rgba(255,255,255,0.8)', fontSize: 13, padding: '4px 0',
        outline: 'none', width: '100%', fontFamily: 'inherit',
      }}
      onFocus={e => { e.target.style.borderBottomColor = 'var(--personality-accent)' }}
      onBlurCapture={e => { e.target.style.borderBottomColor = 'rgba(255,255,255,0.15)' }}
    />
  )
}

function SegmentedControl({ value, choices, onChange }: {
  value: string; choices: string[]; onChange: (v: string) => void
}) {
  return (
    <div style={{
      display: 'flex', gap: 2, padding: 2, borderRadius: 8,
      background: 'rgba(255,255,255,0.05)',
    }}>
      {choices.map(c => (
        <motion.button
          key={c}
          onClick={() => onChange(c)}
          whileTap={{ scale: 0.97 }}
          style={{
            flex: 1, padding: '5px 8px', borderRadius: 6, border: 'none',
            cursor: 'pointer', fontSize: 11, fontWeight: 500,
            background: c === value ? 'var(--personality-accent)' : 'transparent',
            color: c === value ? '#fff' : 'rgba(255,255,255,0.45)',
          }}
        >
          {c}
        </motion.button>
      ))}
    </div>
  )
}

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
        <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.35)', marginTop: 2 }}>
          {description}
        </div>
      </div>
      <div style={{ marginTop: isInline ? 0 : 8 }}>{control}</div>
    </div>
  )
}
