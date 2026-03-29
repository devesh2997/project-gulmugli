/**
 * UpcomingTimeline -- vertical timeline of all scheduled reminders, timers, and alarms.
 *
 * Shows a personality-accent left line with event cards branching off it.
 * Events sorted by fire time (nearest first). Live countdown for timers.
 * Staggered spring entry animations. Subtle cancel buttons per event.
 */

import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useTokens } from '../context/TokenProvider'
import type { ReminderData, TimerData, AssistantActions } from '../types/assistant'

interface UpcomingTimelineProps {
  reminders: ReminderData[]
  timers: TimerData[]
  actions: AssistantActions
}

/** Unified event type for sorting */
interface TimelineEvent {
  id: string
  kind: 'reminder' | 'timer' | 'alarm'
  fireTime: number // unix ms
  label: string
  repeat: string
  createdAt: string | number
  raw: ReminderData | TimerData
}

function buildEvents(reminders: ReminderData[], timers: TimerData[]): TimelineEvent[] {
  const events: TimelineEvent[] = []

  for (const r of reminders) {
    if (!r.active) continue
    events.push({
      id: r.id,
      kind: 'reminder',
      fireTime: new Date(r.remind_at).getTime(),
      label: r.text,
      repeat: r.repeat,
      createdAt: r.created_at,
      raw: r,
    })
  }

  for (const t of timers) {
    if (!t.active) continue
    events.push({
      id: t.id,
      kind: t.type === 'alarm' ? 'alarm' : 'timer',
      fireTime: t.target_time * 1000,
      label: t.label,
      repeat: t.repeat,
      createdAt: t.created_at,
      raw: t,
    })
  }

  events.sort((a, b) => a.fireTime - b.fireTime)
  return events
}

function formatEventTime(ms: number): string {
  const d = new Date(ms)
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const tomorrow = new Date(today.getTime() + 86400000)
  const eventDay = new Date(d.getFullYear(), d.getMonth(), d.getDate())

  const time = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

  if (eventDay.getTime() === today.getTime()) return `Today at ${time}`
  if (eventDay.getTime() === tomorrow.getTime()) return `Tomorrow at ${time}`

  const month = d.toLocaleDateString([], { month: 'short', day: 'numeric' })
  return `${month} at ${time}`
}

function formatCountdown(targetMs: number): string {
  const remaining = Math.max(0, Math.floor((targetMs - Date.now()) / 1000))
  const h = Math.floor(remaining / 3600)
  const m = Math.floor((remaining % 3600) / 60)
  const s = remaining % 60
  if (h > 0) return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
}

function formatCreatedAt(val: string | number): string {
  try {
    const d = typeof val === 'number' ? new Date(val * 1000) : new Date(val)
    return `Created ${d.toLocaleDateString([], { month: 'short', day: 'numeric' })}`
  } catch {
    return ''
  }
}

/* ---- Icons ---- */

function BellIcon({ color }: { color: string }) {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </svg>
  )
}

function ClockIcon({ color }: { color: string }) {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  )
}

function AlarmIcon({ color }: { color: string }) {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="13" r="8" />
      <path d="M12 9v4l2 2" />
      <path d="M5 3 2 6" />
      <path d="m22 6-3-3" />
    </svg>
  )
}

/* ---- Timeline Event Card ---- */

function EventCard({
  event,
  accent,
  index,
  onCancel,
}: {
  event: TimelineEvent
  accent: string
  index: number
  onCancel: () => void
}) {
  const [countdown, setCountdown] = useState(() => formatCountdown(event.fireTime))

  // Live countdown for timers
  useEffect(() => {
    if (event.kind !== 'timer') return
    const tick = () => setCountdown(formatCountdown(event.fireTime))
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [event.kind, event.fireTime])

  const icon =
    event.kind === 'reminder' ? <BellIcon color={accent} /> :
    event.kind === 'alarm' ? <AlarmIcon color={accent} /> :
    <ClockIcon color={accent} />

  const kindLabel =
    event.kind === 'reminder' ? 'Reminder' :
    event.kind === 'alarm' ? 'Alarm' : 'Timer'

  const displayLabel =
    event.label && event.label !== 'Timer' && event.label !== 'Alarm'
      ? event.label
      : null

  return (
    <motion.div
      initial={{ opacity: 0, x: -16, scale: 0.96 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      exit={{ opacity: 0, x: 16, scale: 0.95 }}
      transition={{
        type: 'spring',
        stiffness: 380,
        damping: 28,
        delay: index * 0.06,
      }}
      style={{
        display: 'flex',
        gap: 12,
        alignItems: 'flex-start',
      }}
    >
      {/* Timeline dot */}
      <div style={{
        width: 10,
        height: 10,
        borderRadius: '50%',
        background: `${accent}33`,
        border: `2px solid ${accent}66`,
        flexShrink: 0,
        marginTop: 6,
      }} />

      {/* Card */}
      <div style={{
        flex: 1,
        padding: '12px 14px',
        borderRadius: 14,
        background: 'rgba(255, 255, 255, 0.03)',
        border: '1px solid rgba(255, 255, 255, 0.06)',
        position: 'relative',
        overflow: 'hidden',
      }}>
        {/* Accent bar */}
        <div style={{
          position: 'absolute',
          left: 0,
          top: 8,
          bottom: 8,
          width: 2,
          borderRadius: 1,
          background: `${accent}33`,
        }} />

        {/* Header row */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          marginBottom: displayLabel ? 6 : 0,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', flexShrink: 0 }}>
            {icon}
          </div>

          <span style={{
            fontSize: 10,
            fontWeight: 600,
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
            color: 'rgba(255, 255, 255, 0.35)',
          }}>
            {kindLabel}
          </span>

          {/* Repeat badge */}
          {event.repeat !== 'none' && (
            <span style={{
              fontSize: 9,
              fontWeight: 500,
              color: accent,
              background: `${accent}15`,
              borderRadius: 4,
              padding: '1px 6px',
              letterSpacing: '0.04em',
            }}>
              {event.repeat}
            </span>
          )}

          {/* Cancel button */}
          <motion.button
            onClick={onCancel}
            whileHover={{ scale: 1.15, background: 'rgba(255,255,255,0.08)' }}
            whileTap={{ scale: 0.9 }}
            style={{
              marginLeft: 'auto',
              width: 22,
              height: 22,
              borderRadius: 7,
              border: 'none',
              background: 'transparent',
              color: 'rgba(255, 255, 255, 0.2)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              flexShrink: 0,
              transition: 'color 0.15s',
            }}
            onMouseEnter={e => { e.currentTarget.style.color = 'rgba(255,255,255,0.5)' }}
            onMouseLeave={e => { e.currentTarget.style.color = 'rgba(255,255,255,0.2)' }}
          >
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </motion.button>
        </div>

        {/* Label text */}
        {displayLabel && (
          <div style={{
            fontSize: 13,
            fontWeight: 500,
            color: 'rgba(255, 255, 255, 0.8)',
            lineHeight: 1.4,
            marginBottom: 6,
            paddingLeft: 2,
          }}>
            {displayLabel}
          </div>
        )}

        {/* Time row */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          paddingLeft: 2,
        }}>
          {event.kind === 'timer' ? (
            <span style={{
              fontSize: 15,
              fontWeight: 600,
              fontVariantNumeric: 'tabular-nums',
              color: accent,
              fontFamily: 'var(--font-mono)',
            }}>
              {countdown}
            </span>
          ) : (
            <span style={{
              fontSize: 12,
              fontWeight: 500,
              color: 'rgba(255, 255, 255, 0.5)',
            }}>
              {formatEventTime(event.fireTime)}
            </span>
          )}

          <span style={{
            fontSize: 9,
            color: 'rgba(255, 255, 255, 0.2)',
            marginLeft: 'auto',
            fontFamily: 'var(--font-mono)',
          }}>
            {formatCreatedAt(event.createdAt)}
          </span>
        </div>
      </div>
    </motion.div>
  )
}

/* ---- Main Component ---- */

export default function UpcomingTimeline({ reminders, timers, actions }: UpcomingTimelineProps) {
  const { getToken } = useTokens()
  const accent = (getToken('color.accent') as string) || '#6366f1'

  const events = buildEvents(reminders, timers)

  const handleCancel = (event: TimelineEvent) => {
    if (event.kind === 'reminder') {
      actions.cancelReminder(event.id)
    } else {
      actions.cancelTimer(event.id)
    }
  }

  if (events.length === 0) {
    return (
      <div style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 16,
        padding: 32,
      }}>
        <motion.div
          animate={{
            scale: [1, 1.08, 1],
            opacity: [0.12, 0.22, 0.12],
          }}
          transition={{ duration: 3.5, repeat: Infinity, ease: 'easeInOut' }}
          style={{
            width: 44,
            height: 44,
            borderRadius: '50%',
            background: `radial-gradient(circle, ${accent}33 0%, transparent 70%)`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <ClockIcon color={`${accent}66`} />
        </motion.div>
        <div style={{ textAlign: 'center' }}>
          <p style={{
            fontSize: 13,
            color: 'var(--text-tertiary)',
            margin: '0 0 6px 0',
            fontWeight: 500,
          }}>
            No upcoming events
          </p>
          <p style={{
            fontSize: 11,
            color: 'rgba(255, 255, 255, 0.2)',
            margin: 0,
            lineHeight: 1.6,
          }}>
            Say &lsquo;remind me to...&rsquo; or &lsquo;set timer for...&rsquo; to get started
          </p>
        </div>
      </div>
    )
  }

  return (
    <div style={{
      flex: 1,
      overflowY: 'auto',
      padding: '16px 16px 16px 12px',
      scrollBehavior: 'smooth',
    }}>
      {/* Timeline line */}
      <div style={{ position: 'relative', paddingLeft: 4 }}>
        {/* Vertical accent line */}
        <div style={{
          position: 'absolute',
          left: 8,
          top: 8,
          bottom: 8,
          width: 2,
          borderRadius: 1,
          background: `linear-gradient(to bottom, ${accent}33, ${accent}0a)`,
        }} />

        {/* Events */}
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 10,
          paddingLeft: 6,
        }}>
          <AnimatePresence mode="popLayout">
            {events.map((event, i) => (
              <EventCard
                key={event.id}
                event={event}
                accent={accent}
                index={i}
                onCancel={() => handleCancel(event)}
              />
            ))}
          </AnimatePresence>
        </div>
      </div>
    </div>
  )
}
