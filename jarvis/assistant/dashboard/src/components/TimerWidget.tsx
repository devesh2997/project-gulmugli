/**
 * TimerWidget -- floating pill(s) showing active timers and alarms.
 *
 * Appears in the top-right corner when any timer or alarm is active.
 * Shows countdown for timers (MM:SS) and target time for alarms.
 * Countdown updates every second via setInterval.
 * When a timer fires, the pill pulses with the personality accent color.
 * Cancel (X) and Snooze (for alarms) buttons on each pill.
 * Multiple timers stack vertically with spring animation entry/exit.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { useTokens } from '../context/TokenProvider'
import type { TimerData, AssistantActions } from '../types/assistant'

interface TimerWidgetProps {
  timers: TimerData[]
  firedTimer: TimerData | null
  actions: AssistantActions
}

function formatCountdown(seconds: number): string {
  if (seconds <= 0) return '00:00'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  if (h > 0) {
    return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
  }
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
}

function formatAlarmTime(targetTime: number): string {
  const d = new Date(targetTime * 1000)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function TimerPill({
  entry,
  accent,
  onCancel,
  onSnooze,
  isFired,
}: {
  entry: TimerData
  accent: string
  onCancel: () => void
  onSnooze?: () => void
  isFired: boolean
}) {
  const [remaining, setRemaining] = useState(entry.remaining_seconds)

  useEffect(() => {
    if (entry.type !== 'timer') return

    const tick = () => {
      const now = Date.now() / 1000
      setRemaining(Math.max(0, entry.target_time - now))
    }
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [entry.target_time, entry.type])

  const isTimer = entry.type === 'timer'
  const displayTime = isTimer ? formatCountdown(remaining) : formatAlarmTime(entry.target_time)
  const icon = isTimer ? (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  ) : (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </svg>
  )

  return (
    <motion.div
      layout
      initial={{ x: 80, opacity: 0, scale: 0.9 }}
      animate={{
        x: 0,
        opacity: 1,
        scale: isFired ? [1, 1.05, 1] : 1,
      }}
      exit={{ x: 80, opacity: 0, scale: 0.9 }}
      transition={{
        type: 'spring',
        stiffness: 400,
        damping: 30,
        scale: isFired ? { repeat: Infinity, duration: 1.2 } : undefined,
      }}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '8px 12px',
        borderRadius: 14,
        background: isFired ? `${accent}22` : 'rgba(15, 15, 25, 0.85)',
        backdropFilter: 'blur(16px)',
        WebkitBackdropFilter: 'blur(16px)',
        border: `1px solid ${isFired ? accent + '55' : accent + '22'}`,
        boxShadow: isFired
          ? `0 0 24px ${accent}33, 0 4px 16px rgba(0,0,0,0.3)`
          : `0 2px 12px rgba(0,0,0,0.2)`,
        color: '#fff',
        minWidth: 160,
      }}
    >
      <div style={{ color: accent, display: 'flex', alignItems: 'center', flexShrink: 0 }}>
        {icon}
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        {entry.label && entry.label !== 'Timer' && entry.label !== 'Alarm' && (
          <div style={{
            fontSize: 10,
            color: '#ffffff77',
            fontWeight: 500,
            letterSpacing: 0.3,
            textTransform: 'uppercase',
            lineHeight: 1,
            marginBottom: 2,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}>
            {entry.label}
          </div>
        )}
        <div style={{
          fontSize: 15,
          fontWeight: 600,
          fontVariantNumeric: 'tabular-nums',
          color: isFired ? accent : '#ffffffdd',
          lineHeight: 1.2,
        }}>
          {displayTime}
        </div>
      </div>

      {/* Snooze button — alarms only */}
      {entry.type === 'alarm' && onSnooze && (
        <button
          onClick={onSnooze}
          title="Snooze 5 min"
          style={{
            width: 26,
            height: 26,
            borderRadius: 8,
            border: `1px solid ${accent}33`,
            background: 'transparent',
            color: accent,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            fontSize: 11,
            fontWeight: 700,
            flexShrink: 0,
            transition: 'background 0.15s',
          }}
          onMouseEnter={e => (e.currentTarget.style.background = `${accent}22`)}
          onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M4 12h8" />
            <path d="M4 4h16" />
            <path d="M4 20h16" />
          </svg>
        </button>
      )}

      {/* Cancel button */}
      <button
        onClick={onCancel}
        title="Cancel"
        style={{
          width: 26,
          height: 26,
          borderRadius: 8,
          border: '1px solid rgba(255,255,255,0.1)',
          background: 'transparent',
          color: '#ffffff77',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: 'pointer',
          flexShrink: 0,
          transition: 'all 0.15s',
        }}
        onMouseEnter={e => {
          e.currentTarget.style.background = 'rgba(255,255,255,0.1)'
          e.currentTarget.style.color = '#ffffffcc'
        }}
        onMouseLeave={e => {
          e.currentTarget.style.background = 'transparent'
          e.currentTarget.style.color = '#ffffff77'
        }}
      >
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <line x1="18" y1="6" x2="6" y2="18" />
          <line x1="6" y1="6" x2="18" y2="18" />
        </svg>
      </button>
    </motion.div>
  )
}

export function TimerWidget({ timers, firedTimer, actions }: TimerWidgetProps) {
  const { getToken } = useTokens()
  const accent = (getToken('color.accent') as string) || '#6366f1'
  const autoDismissRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Auto-dismiss fired timer notification after 30 seconds
  useEffect(() => {
    if (!firedTimer) return
    autoDismissRef.current = setTimeout(() => {
      actions.dismissTimer()
    }, 30_000)
    return () => {
      if (autoDismissRef.current) clearTimeout(autoDismissRef.current)
    }
  }, [firedTimer, actions])

  const handleCancel = useCallback((id: string) => {
    actions.cancelTimer(id)
  }, [actions])

  const handleSnooze = useCallback((id: string) => {
    actions.snoozeTimer(id, 5)
    actions.dismissTimer()
  }, [actions])

  // Nothing to show
  if (timers.length === 0 && !firedTimer) return null

  return (
    <div
      style={{
        position: 'fixed',
        top: 16,
        right: 16,
        zIndex: 55,
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        alignItems: 'flex-end',
      }}
    >
      {/* Fired timer notification */}
      <AnimatePresence>
        {firedTimer && (
          <motion.div
            key={`fired-${firedTimer.id}`}
            initial={{ y: -40, opacity: 0, scale: 0.95 }}
            animate={{ y: 0, opacity: 1, scale: 1 }}
            exit={{ y: -40, opacity: 0, scale: 0.95 }}
            transition={{ type: 'spring', stiffness: 300, damping: 28 }}
            style={{
              padding: '12px 16px',
              borderRadius: 16,
              background: `${accent}18`,
              backdropFilter: 'blur(20px)',
              WebkitBackdropFilter: 'blur(20px)',
              border: `1px solid ${accent}44`,
              boxShadow: `0 0 32px ${accent}22, 0 8px 24px rgba(0,0,0,0.3)`,
              color: '#fff',
              minWidth: 200,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <motion.div
                animate={{ scale: [1, 1.3, 1] }}
                transition={{ repeat: Infinity, duration: 1.5 }}
                style={{ color: accent, display: 'flex' }}
              >
                {firedTimer.type === 'alarm' ? (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
                    <path d="M13.73 21a2 2 0 0 1-3.46 0" />
                  </svg>
                ) : (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10" />
                    <polyline points="12 6 12 12 16 14" />
                  </svg>
                )}
              </motion.div>
              <span style={{ fontSize: 14, fontWeight: 600, color: accent }}>
                {firedTimer.type === 'alarm' ? 'Alarm!' : 'Timer Done!'}
              </span>
            </div>
            {firedTimer.label && firedTimer.label !== 'Timer' && firedTimer.label !== 'Alarm' && (
              <div style={{ fontSize: 14, fontWeight: 500, color: '#ffffffcc', marginBottom: 10 }}>
                {firedTimer.label}
              </div>
            )}
            <div style={{ display: 'flex', gap: 6 }}>
              {firedTimer.type === 'alarm' && (
                <button
                  onClick={() => handleSnooze(firedTimer.id)}
                  style={{
                    flex: 1,
                    padding: '7px 12px',
                    borderRadius: 10,
                    border: `1px solid ${accent}44`,
                    background: `${accent}11`,
                    color: accent,
                    fontSize: 12,
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  Snooze
                </button>
              )}
              <button
                onClick={() => actions.dismissTimer()}
                style={{
                  flex: 1,
                  padding: '7px 12px',
                  borderRadius: 10,
                  border: '1px solid rgba(255,255,255,0.1)',
                  background: 'rgba(255,255,255,0.06)',
                  color: '#ffffffaa',
                  fontSize: 12,
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                Dismiss
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Active timers/alarms */}
      <AnimatePresence mode="popLayout">
        {timers.map(entry => (
          <TimerPill
            key={entry.id}
            entry={entry}
            accent={accent}
            onCancel={() => handleCancel(entry.id)}
            onSnooze={entry.type === 'alarm' ? () => handleSnooze(entry.id) : undefined}
            isFired={firedTimer?.id === entry.id}
          />
        ))}
      </AnimatePresence>
    </div>
  )
}
