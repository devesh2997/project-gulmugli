/**
 * ReminderNotification -- slide-in notification when a reminder fires.
 *
 * Appears from the top of the screen with a spring animation.
 * Shows the reminder text, time, and snooze/dismiss controls.
 * Auto-dismisses after 30 seconds if not interacted with.
 * Uses the active personality's accent color for the glow.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { useTokens } from '../context/TokenProvider'
import type { ReminderData, AssistantActions } from '../types/assistant'

interface ReminderNotificationProps {
  reminder: ReminderData | null
  actions: AssistantActions
}

const SNOOZE_OPTIONS = [
  { label: '15 min', minutes: 15 },
  { label: '30 min', minutes: 30 },
  { label: '1 hour', minutes: 60 },
]

export function ReminderNotification({ reminder, actions }: ReminderNotificationProps) {
  const { getToken } = useTokens()
  const [showSnooze, setShowSnooze] = useState(false)
  const autoDismissTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Personality accent color for the glow
  const accent = (getToken('color.accent') as string) || '#6366f1'

  // Auto-dismiss after 30 seconds
  useEffect(() => {
    if (!reminder) return
    setShowSnooze(false)

    autoDismissTimer.current = setTimeout(() => {
      actions.dismissReminder()
    }, 30_000)

    return () => {
      if (autoDismissTimer.current) clearTimeout(autoDismissTimer.current)
    }
  }, [reminder, actions])

  const handleDismiss = useCallback(() => {
    if (autoDismissTimer.current) clearTimeout(autoDismissTimer.current)
    actions.dismissReminder()
  }, [actions])

  const handleSnooze = useCallback((minutes: number) => {
    if (autoDismissTimer.current) clearTimeout(autoDismissTimer.current)
    if (reminder) {
      actions.snoozeReminder(reminder.id, minutes)
    }
    actions.dismissReminder()
  }, [reminder, actions])

  const formatTime = (isoStr: string) => {
    try {
      const d = new Date(isoStr)
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    } catch {
      return ''
    }
  }

  return (
    <AnimatePresence>
      {reminder && (
        <motion.div
          key={reminder.id}
          initial={{ y: -120, opacity: 0, scale: 0.95 }}
          animate={{ y: 0, opacity: 1, scale: 1 }}
          exit={{ y: -80, opacity: 0, scale: 0.95 }}
          transition={{ type: 'spring', stiffness: 300, damping: 28 }}
          style={{
            position: 'fixed',
            top: 24,
            left: '50%',
            transform: 'translateX(-50%)',
            zIndex: 60,
            width: 'min(420px, calc(100vw - 32px))',
          }}
        >
          <div
            style={{
              background: 'rgba(15, 15, 25, 0.92)',
              backdropFilter: 'blur(24px)',
              WebkitBackdropFilter: 'blur(24px)',
              borderRadius: 20,
              border: `1px solid ${accent}33`,
              boxShadow: `0 0 40px ${accent}22, 0 8px 32px rgba(0,0,0,0.4)`,
              padding: '20px 24px',
              color: '#fff',
            }}
          >
            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
              <div
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: 10,
                  background: `${accent}22`,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 16,
                  flexShrink: 0,
                }}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={accent} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
                  <path d="M13.73 21a2 2 0 0 1-3.46 0" />
                </svg>
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 11, color: '#ffffff66', fontWeight: 500, letterSpacing: 0.5, textTransform: 'uppercase' }}>
                  Reminder
                </div>
              </div>
              <div style={{ fontSize: 12, color: '#ffffff55' }}>
                {formatTime(reminder.remind_at)}
              </div>
            </div>

            {/* Reminder text */}
            <div style={{
              fontSize: 16,
              fontWeight: 500,
              lineHeight: 1.4,
              marginBottom: 16,
              color: '#ffffffdd',
            }}>
              {reminder.text}
            </div>

            {/* Repeat badge */}
            {reminder.repeat !== 'none' && (
              <div style={{
                display: 'inline-block',
                fontSize: 11,
                color: accent,
                background: `${accent}15`,
                borderRadius: 6,
                padding: '2px 8px',
                marginBottom: 12,
                fontWeight: 500,
              }}>
                Repeats {reminder.repeat}
              </div>
            )}

            {/* Action buttons */}
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                onClick={() => setShowSnooze(prev => !prev)}
                style={{
                  flex: 1,
                  padding: '10px 16px',
                  borderRadius: 12,
                  border: `1px solid ${accent}44`,
                  background: `${accent}11`,
                  color: accent,
                  fontSize: 13,
                  fontWeight: 600,
                  cursor: 'pointer',
                  transition: 'background 0.2s',
                }}
                onMouseEnter={e => (e.currentTarget.style.background = `${accent}22`)}
                onMouseLeave={e => (e.currentTarget.style.background = `${accent}11`)}
              >
                Snooze
              </button>
              <button
                onClick={handleDismiss}
                style={{
                  flex: 1,
                  padding: '10px 16px',
                  borderRadius: 12,
                  border: '1px solid rgba(255,255,255,0.1)',
                  background: 'rgba(255,255,255,0.06)',
                  color: '#ffffffaa',
                  fontSize: 13,
                  fontWeight: 600,
                  cursor: 'pointer',
                  transition: 'background 0.2s',
                }}
                onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.12)')}
                onMouseLeave={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.06)')}
              >
                Dismiss
              </button>
            </div>

            {/* Snooze options */}
            <AnimatePresence>
              {showSnooze && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.2 }}
                  style={{ overflow: 'hidden' }}
                >
                  <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
                    {SNOOZE_OPTIONS.map(opt => (
                      <button
                        key={opt.minutes}
                        onClick={() => handleSnooze(opt.minutes)}
                        style={{
                          flex: 1,
                          padding: '8px 12px',
                          borderRadius: 10,
                          border: `1px solid ${accent}33`,
                          background: `${accent}0a`,
                          color: '#ffffffbb',
                          fontSize: 12,
                          fontWeight: 500,
                          cursor: 'pointer',
                          transition: 'all 0.15s',
                        }}
                        onMouseEnter={e => {
                          e.currentTarget.style.background = `${accent}22`
                          e.currentTarget.style.color = '#fff'
                        }}
                        onMouseLeave={e => {
                          e.currentTarget.style.background = `${accent}0a`
                          e.currentTarget.style.color = '#ffffffbb'
                        }}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
