/**
 * Transcript — AI conversation view with personality-themed messages,
 * plus an "Upcoming" tab showing scheduled reminders/timers/alarms.
 *
 * Redesigned to feel like conversing with a character:
 *   - User messages: right-aligned with personality accent tint, small "You" label
 *   - Assistant messages: left-aligned with frosted glass, personality accent left bar
 *   - Timestamp dividers styled as thin centered lines with time in the middle
 *   - Empty state shows breathing personality orb instead of plain icon
 *   - Text input has personality glow when focused
 *   - Messages animate in with staggered spring physics
 *   - Tab bar: "Conversation" | "Upcoming" with sliding accent underline
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { TranscriptEntry, ReminderData, TimerData, AssistantActions } from '../types/assistant'
import UpcomingTimeline from './UpcomingTimeline'

export type TranscriptTab = 'conversation' | 'upcoming'

interface TranscriptProps {
  messages?: TranscriptEntry[]
  onSendText?: (text: string) => void
  reminders?: ReminderData[]
  timers?: TimerData[]
  actions?: AssistantActions
  /** Externally controlled active tab */
  activeTab?: TranscriptTab
  onTabChange?: (tab: TranscriptTab) => void
}

/** Format a timestamp for display */
function formatTime(ts: number | string): string {
  try {
    const d = typeof ts === 'number' ? new Date(ts) : new Date(ts)
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  } catch {
    return ''
  }
}

/** Check if two timestamps are > 5 minutes apart */
function isTimegap(a: number | string, b: number | string): boolean {
  try {
    const ta = typeof a === 'number' ? a : new Date(a).getTime()
    const tb = typeof b === 'number' ? b : new Date(b).getTime()
    return Math.abs(tb - ta) > 5 * 60 * 1000
  } catch {
    return false
  }
}

const TABS: { id: TranscriptTab; label: string }[] = [
  { id: 'conversation', label: 'Conversation' },
  { id: 'upcoming', label: 'Upcoming' },
]

export default function Transcript({
  messages = [],
  onSendText,
  reminders = [],
  timers = [],
  actions,
  activeTab: controlledTab,
  onTabChange,
}: TranscriptProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const [inputValue, setInputValue] = useState('')
  const [inputFocused, setInputFocused] = useState(false)
  const [internalTab, setInternalTab] = useState<TranscriptTab>('conversation')

  const currentTab = controlledTab ?? internalTab
  const setTab = (tab: TranscriptTab) => {
    if (onTabChange) onTabChange(tab)
    else setInternalTab(tab)
  }

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current && currentTab === 'conversation') {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages.length, currentTab])

  const handleSend = useCallback(() => {
    const text = inputValue.trim()
    if (!text || !onSendText) return
    onSendText(text)
    setInputValue('')
  }, [inputValue, onSendText])

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }, [handleSend])

  // Count for upcoming badge
  const upcomingCount = reminders.filter(r => r.active).length + timers.filter(t => t.active).length

  return (
    <div
      data-gesture-ignore="true"
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        boxSizing: 'border-box',
      }}
    >
      {/* Header with tab bar */}
      <div style={{
        padding: '16px 20px 0',
        position: 'relative',
      }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 0,
          position: 'relative',
        }}>
          {TABS.map(tab => (
            <button
              key={tab.id}
              onClick={() => setTab(tab.id)}
              style={{
                background: 'none',
                border: 'none',
                padding: '6px 14px 12px',
                cursor: 'pointer',
                fontSize: 11,
                fontWeight: 600,
                letterSpacing: '0.12em',
                textTransform: 'uppercase',
                color: currentTab === tab.id
                  ? 'rgba(var(--personality-accent-rgb), 0.7)'
                  : 'rgba(var(--personality-accent-rgb), 0.25)',
                transition: 'color 0.25s ease',
                position: 'relative',
                fontFamily: 'inherit',
                display: 'flex',
                alignItems: 'center',
                gap: 6,
              }}
            >
              {tab.label}
              {/* Badge on Upcoming tab */}
              {tab.id === 'upcoming' && upcomingCount > 0 && (
                <span style={{
                  fontSize: 9,
                  fontWeight: 700,
                  minWidth: 16,
                  height: 16,
                  borderRadius: 8,
                  background: 'rgba(var(--personality-accent-rgb), 0.15)',
                  color: 'var(--personality-accent)',
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  padding: '0 4px',
                  letterSpacing: 0,
                  fontVariantNumeric: 'tabular-nums',
                }}>
                  {upcomingCount}
                </span>
              )}
            </button>
          ))}

          {/* Sliding accent underline */}
          <motion.div
            layout
            animate={{
              x: currentTab === 'conversation' ? 0 : undefined,
            }}
            style={{
              position: 'absolute',
              bottom: 0,
              left: currentTab === 'conversation' ? 14 : undefined,
              right: currentTab === 'upcoming' ? 14 : undefined,
              width: currentTab === 'conversation' ? 82 : 64,
              height: 2,
              borderRadius: 1,
              background: 'var(--personality-accent)',
              opacity: 0.5,
            }}
            transition={{ type: 'spring', stiffness: 400, damping: 30 }}
          />

          {/* Message count — only for conversation tab */}
          {currentTab === 'conversation' && (
            <span style={{
              fontSize: 10, color: 'var(--text-tertiary)', marginLeft: 'auto',
              fontFamily: 'var(--font-mono)',
            }}>
              {messages.length > 0 ? `${messages.length}` : ''}
            </span>
          )}
        </div>

        {/* Breathing accent line under header */}
        <motion.div
          animate={{ scaleX: [0.2, 0.5, 0.2], opacity: [0.15, 0.3, 0.15] }}
          transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut' }}
          style={{
            height: 1,
            marginTop: 0,
            background: 'var(--personality-accent)',
            transformOrigin: 'center',
          }}
        />
      </div>

      {/* Tab content */}
      <AnimatePresence mode="wait" initial={false}>
        {currentTab === 'conversation' ? (
          <motion.div
            key="conversation"
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
            style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}
          >
            {/* Messages area */}
            <div
              ref={scrollRef}
              style={{
                flex: 1,
                overflowY: 'auto',
                padding: '16px 16px',
                display: 'flex',
                flexDirection: 'column',
                gap: 8,
                scrollBehavior: 'smooth',
              }}
            >
              {messages.length === 0 ? (
                <div style={{
                  flex: 1,
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 16,
                }}>
                  {/* Breathing personality orb */}
                  <motion.div
                    animate={{
                      scale: [1, 1.1, 1],
                      opacity: [0.15, 0.3, 0.15],
                    }}
                    transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
                    style={{
                      width: 48,
                      height: 48,
                      borderRadius: '50%',
                      background: 'radial-gradient(circle, rgba(var(--personality-accent-rgb), 0.3) 0%, transparent 70%)',
                    }}
                  />
                  <p style={{
                    fontSize: 12, color: 'var(--text-tertiary)',
                    textAlign: 'center', lineHeight: 1.6, margin: 0,
                    fontWeight: 400,
                    letterSpacing: '0.02em',
                  }}>
                    Say something or type below
                  </p>
                </div>
              ) : (
                <AnimatePresence initial={false}>
                  {messages.map((msg, i) => {
                    const isUser = msg.role === 'user'
                    const showTimestamp = i === 0 || (
                      messages[i - 1] && isTimegap(messages[i - 1].timestamp, msg.timestamp)
                    )

                    return (
                      <motion.div key={`${msg.timestamp}-${i}`}>
                        {/* Timestamp divider — centered line with time */}
                        {showTimestamp && msg.timestamp && (
                          <div style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 12,
                            padding: '12px 0 6px',
                          }}>
                            <div style={{
                              flex: 1, height: 1,
                              background: 'rgba(var(--personality-accent-rgb), 0.08)',
                            }} />
                            <span style={{
                              fontSize: 9,
                              color: 'var(--text-tertiary)',
                              letterSpacing: '0.08em',
                              fontFamily: 'var(--font-mono)',
                              fontWeight: 500,
                            }}>
                              {formatTime(msg.timestamp)}
                            </span>
                            <div style={{
                              flex: 1, height: 1,
                              background: 'rgba(var(--personality-accent-rgb), 0.08)',
                            }} />
                          </div>
                        )}

                        {/* Message bubble */}
                        <motion.div
                          initial={{ opacity: 0, y: 10, scale: 0.97 }}
                          animate={{ opacity: 1, y: 0, scale: 1 }}
                          transition={{
                            type: 'spring',
                            stiffness: 400,
                            damping: 30,
                            delay: 0.02,
                          }}
                          style={{
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: isUser ? 'flex-end' : 'flex-start',
                            padding: '2px 0',
                          }}
                        >
                          {/* Role label */}
                          <span style={{
                            fontSize: 9,
                            fontWeight: 600,
                            letterSpacing: '0.08em',
                            textTransform: 'uppercase',
                            color: isUser
                              ? 'rgba(var(--personality-accent-rgb), 0.4)'
                              : 'var(--text-tertiary)',
                            marginBottom: 3,
                            paddingLeft: isUser ? 0 : 12,
                            paddingRight: isUser ? 12 : 0,
                          }}>
                            {isUser ? 'You' : 'Assistant'}
                          </span>

                          <div style={{
                            maxWidth: '82%',
                            padding: '10px 14px',
                            borderRadius: isUser ? '18px 18px 4px 18px' : '18px 18px 18px 4px',
                            background: isUser
                              ? 'rgba(var(--personality-accent-rgb), 0.12)'
                              : 'rgba(255, 255, 255, 0.04)',
                            border: 'none',
                            backdropFilter: isUser ? undefined : 'blur(8px)',
                            position: 'relative',
                            overflow: 'hidden',
                          }}>
                            {/* Accent bar on assistant messages */}
                            {!isUser && (
                              <div style={{
                                position: 'absolute',
                                left: 0,
                                top: 6,
                                bottom: 6,
                                width: 2,
                                borderRadius: 1,
                                background: 'rgba(var(--personality-accent-rgb), 0.3)',
                              }} />
                            )}
                            <p style={{
                              margin: 0,
                              fontSize: 13,
                              lineHeight: 1.6,
                              color: isUser
                                ? 'var(--personality-accent)'
                                : 'var(--text-primary)',
                              wordBreak: 'break-word',
                              letterSpacing: '0.01em',
                            }}>
                              {msg.text}
                            </p>
                          </div>
                        </motion.div>
                      </motion.div>
                    )
                  })}
                </AnimatePresence>
              )}
            </div>

            {/* Text input bar */}
            <div style={{
              padding: '12px 16px 16px',
              position: 'relative',
            }}>
              {/* Subtle glow line above input */}
              <motion.div
                animate={{
                  opacity: inputFocused ? 0.5 : 0.1,
                  scaleX: inputFocused ? 1 : 0.4,
                }}
                transition={{ type: 'spring', stiffness: 300, damping: 25 }}
                style={{
                  position: 'absolute',
                  top: 0,
                  left: '15%',
                  right: '15%',
                  height: 1,
                  background: 'var(--personality-accent)',
                  transformOrigin: 'center',
                }}
              />

              <div style={{
                display: 'flex',
                gap: 8,
                alignItems: 'center',
              }}>
                <div style={{
                  flex: 1,
                  position: 'relative',
                }}>
                  <input
                    ref={inputRef}
                    type="text"
                    value={inputValue}
                    onChange={e => setInputValue(e.target.value)}
                    onKeyDown={handleKeyDown}
                    onFocus={() => setInputFocused(true)}
                    onBlur={() => setInputFocused(false)}
                    placeholder="Type a command..."
                    style={{
                      width: '100%',
                      padding: '10px 16px',
                      borderRadius: 22,
                      border: 'none',
                      background: inputFocused
                        ? 'rgba(var(--personality-accent-rgb), 0.06)'
                        : 'rgba(255, 255, 255, 0.04)',
                      color: 'var(--text-primary)',
                      fontSize: 13,
                      outline: 'none',
                      fontFamily: 'inherit',
                      boxSizing: 'border-box',
                      transition: 'background 0.3s ease, box-shadow 0.3s ease',
                      boxShadow: inputFocused
                        ? '0 0 16px rgba(var(--personality-accent-rgb), 0.12), inset 0 0 0 1px rgba(var(--personality-accent-rgb), 0.15)'
                        : 'inset 0 0 0 1px rgba(255,255,255,0.06)',
                      letterSpacing: '0.01em',
                    }}
                  />
                </div>

                {/* Send button */}
                <motion.button
                  onClick={handleSend}
                  whileHover={{ scale: 1.08 }}
                  whileTap={{ scale: 0.9 }}
                  animate={{
                    background: inputValue.trim()
                      ? 'var(--personality-accent)'
                      : 'rgba(255, 255, 255, 0.04)',
                  }}
                  transition={{ type: 'spring', stiffness: 400, damping: 25 }}
                  style={{
                    width: 36, height: 36, borderRadius: 18,
                    border: 'none',
                    cursor: inputValue.trim() ? 'pointer' : 'default',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    boxShadow: inputValue.trim()
                      ? '0 2px 12px rgba(var(--personality-accent-rgb), 0.3)'
                      : 'none',
                    flexShrink: 0,
                  }}
                >
                  {/* Arrow up icon */}
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
                    stroke={inputValue.trim() ? '#fff' : 'var(--text-tertiary)'}
                    strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
                  >
                    <line x1="12" y1="19" x2="12" y2="5" />
                    <polyline points="5 12 12 5 19 12" />
                  </svg>
                </motion.button>
              </div>
            </div>
          </motion.div>
        ) : (
          <motion.div
            key="upcoming"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 20 }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
            style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}
          >
            {actions ? (
              <UpcomingTimeline
                reminders={reminders}
                timers={timers}
                actions={actions}
              />
            ) : (
              <div style={{
                flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: 'var(--text-tertiary)', fontSize: 12,
              }}>
                No actions available
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
