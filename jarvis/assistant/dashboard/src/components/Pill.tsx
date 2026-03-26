/**
 * Pill — generic reusable capsule badge.
 * Icon (left) · label (center) · status indicator (right).
 */

import { motion } from 'framer-motion'
import type { IntentIcon, IntentStatus } from '../types/assistant'

// Minimal SVG icons — each ≤5 path elements
const ICONS: Record<string, React.ReactNode> = {
  music:       <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor"><path d="M5 10.5a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0z"/><path d="M5 10.5V3l7-1.5v7"/><path d="M12 8.5a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0z"/></svg>,
  bulb:        <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor"><path d="M7 1a4 4 0 0 1 2.5 7.1V10H4.5V8.1A4 4 0 0 1 7 1z"/><rect x="4.5" y="10.5" width="5" height="1.5" rx=".5"/></svg>,
  brain:       <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor"><path d="M5 2C3.3 2 2 3.3 2 5c0 1 .5 1.9 1.2 2.4C2.5 8 2 9 2 10c0 1.1.9 2 2 2h2V2H5z"/><path d="M9 2c1.7 0 3 1.3 3 3 0 1-.5 1.9-1.2 2.4.7.6 1.2 1.6 1.2 2.6 0 1.1-.9 2-2 2H8V2h1z"/></svg>,
  volume:      <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor"><path d="M2 5h2.5L8 2v10L4.5 9H2V5z"/><path d="M10 4.5a3.5 3.5 0 0 1 0 5" stroke="currentColor" strokeWidth="1.2" fill="none"/></svg>,
  personality: <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor"><circle cx="7" cy="4.5" r="2.5"/><path d="M2 12c0-2.8 2.2-5 5-5s5 2.2 5 5"/></svg>,
  timer:       <svg width="14" height="14" viewBox="0 0 14 14"><circle cx="7" cy="8" r="5" fill="none" stroke="currentColor" strokeWidth="1.2"/><path d="M7 5v3l2 1.5" stroke="currentColor" strokeWidth="1.2" fill="none"/></svg>,
  search:      <svg width="14" height="14" viewBox="0 0 14 14"><circle cx="6" cy="6" r="4" fill="none" stroke="currentColor" strokeWidth="1.4"/><path d="M9 9l3 3" stroke="currentColor" strokeWidth="1.4" fill="none"/></svg>,
  general:     <svg width="14" height="14" viewBox="0 0 14 14"><circle cx="7" cy="7" r="5" fill="none" stroke="currentColor" strokeWidth="1.2"/><path d="M7 6v4M7 4.5v.5" stroke="currentColor" strokeWidth="1.4" fill="none"/></svg>,
}

function StatusDot({ status }: { status?: IntentStatus }) {
  if (!status) return null
  if (status === 'queued')
    return <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--text-muted)', flexShrink: 0, display: 'inline-block' }} />
  if (status === 'processing')
    return <span style={{ width: 12, height: 12, borderRadius: '50%', border: '2px solid transparent', borderTopColor: 'var(--personality-accent, var(--accent-primary))', flexShrink: 0, display: 'inline-block', animation: 'pill-spin .7s linear infinite' }} />
  if (status === 'done')
    return <motion.svg width="12" height="12" viewBox="0 0 12 12" fill="none" initial={{ scale: 0 }} animate={{ scale: 1 }} style={{ flexShrink: 0, color: 'var(--accent-success)' }}><path d="M2 6l3 3 5-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></motion.svg>
  if (status === 'failed')
    return <svg width="12" height="12" viewBox="0 0 12 12" fill="none" style={{ flexShrink: 0, color: 'var(--accent-error)' }}><path d="M3 3l6 6M9 3l-6 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
  return null
}

// Inject spin keyframe once at module load
if (typeof document !== 'undefined' && !document.getElementById('pill-spin-kf')) {
  const s = document.createElement('style')
  s.id = 'pill-spin-kf'
  s.textContent = '@keyframes pill-spin{to{transform:rotate(360deg)}}'
  document.head.appendChild(s)
}

export interface PillProps {
  icon?: IntentIcon | string
  label: string
  status?: IntentStatus
  detail?: string
  accentColor?: string
  onClick?: () => void
  children?: React.ReactNode
}

export function Pill({ icon, label, status, accentColor, onClick, children }: PillProps) {
  const accent = accentColor ?? 'var(--personality-accent, var(--accent-primary))'
  return (
    <motion.div
      layout
      initial={{ scale: 0.8, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      exit={{ scale: 0.8, opacity: 0 }}
      transition={{ duration: 0.3 }}
      onClick={onClick}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 6,
        height: 32, padding: '6px 12px', borderRadius: 'var(--radius-lg)',
        background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.08)',
        backdropFilter: 'blur(8px)', WebkitBackdropFilter: 'blur(8px)',
        cursor: onClick ? 'pointer' : 'default', userSelect: 'none', flexShrink: 0,
      }}
    >
      {icon && <span style={{ color: accent, opacity: 0.7, display: 'flex', alignItems: 'center', flexShrink: 0 }}>{ICONS[icon] ?? ICONS.general}</span>}
      {children ?? (
        <span style={{ fontSize: '0.72rem', color: accent, opacity: 0.7, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 140 }}>
          {label}
        </span>
      )}
      <StatusDot status={status} />
    </motion.div>
  )
}
