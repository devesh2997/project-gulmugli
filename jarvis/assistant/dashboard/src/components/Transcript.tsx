/**
 * Transcript — conversation view with text command input.
 *
 * Redesigned from a generic chat list to a personal conversation flow:
 *   - Messages float with personality-coloured accents
 *   - User messages are right-aligned with subtle accent bubble
 *   - Assistant messages are left-aligned with frosted glass bubble
 *   - Timestamps shown for time gaps > 5 minutes
 *   - Text input at the bottom for typing commands when voice isn't convenient
 *   - Auto-scrolls to newest message
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { TranscriptEntry } from '../types/assistant'

interface TranscriptProps {
  messages?: TranscriptEntry[]
  onSendText?: (text: string) => void
}

/** Format a timestamp (epoch ms or ISO string) for display */
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

export default function Transcript({ messages = [], onSendText }: TranscriptProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const [inputValue, setInputValue] = useState('')
  const [inputFocused, setInputFocused] = useState(false)

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages.length])

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
      {/* Header */}
      <div style={{
        padding: '16px 20px 12px',
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        borderBottom: '1px solid rgba(var(--personality-accent-rgb), 0.08)',
      }}>
        {/* Animated pulse dot */}
        <motion.div
          style={{
            width: 8, height: 8, borderRadius: '50%',
            background: 'var(--personality-accent)',
            boxShadow: '0 0 6px rgba(var(--personality-accent-rgb), 0.4)',
          }}
          animate={{ scale: [1, 1.3, 1], opacity: [0.7, 1, 0.7] }}
          transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
        />
        <span style={{
          fontSize: 12, fontWeight: 600,
          letterSpacing: '0.08em',
          color: 'rgba(255,255,255,0.5)',
        }}>
          Conversation
        </span>
        <span style={{
          fontSize: 10, color: 'rgba(255,255,255,0.2)', marginLeft: 'auto',
        }}>
          {messages.length > 0 ? `${messages.length} messages` : ''}
        </span>
      </div>

      {/* Messages area */}
      <div
        ref={scrollRef}
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '12px 16px',
          display: 'flex',
          flexDirection: 'column',
          gap: 6,
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
            gap: 12,
            opacity: 0.4,
          }}>
            {/* Mic icon */}
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none"
              stroke="var(--personality-accent)" strokeWidth="1.5" strokeLinecap="round">
              <rect x="9" y="1" width="6" height="12" rx="3" />
              <path d="M5 10a7 7 0 0 0 14 0" />
              <line x1="12" y1="17" x2="12" y2="21" />
              <line x1="8" y1="21" x2="16" y2="21" />
            </svg>
            <p style={{
              fontSize: 13, color: 'rgba(255,255,255,0.35)',
              textAlign: 'center', lineHeight: 1.5, margin: 0,
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
                  {/* Timestamp divider */}
                  {showTimestamp && msg.timestamp && (
                    <motion.div
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      style={{
                        textAlign: 'center',
                        padding: '8px 0 4px',
                        fontSize: 10,
                        color: 'rgba(255,255,255,0.2)',
                        letterSpacing: '0.05em',
                      }}
                    >
                      {formatTime(msg.timestamp)}
                    </motion.div>
                  )}

                  {/* Message bubble */}
                  <motion.div
                    initial={{ opacity: 0, y: 8, scale: 0.95 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    transition={{ duration: 0.25, ease: 'easeOut' }}
                    style={{
                      display: 'flex',
                      justifyContent: isUser ? 'flex-end' : 'flex-start',
                      padding: '2px 0',
                    }}
                  >
                    <div style={{
                      maxWidth: '82%',
                      padding: '8px 14px',
                      borderRadius: isUser ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
                      background: isUser
                        ? 'rgba(var(--personality-accent-rgb), 0.15)'
                        : 'rgba(255, 255, 255, 0.05)',
                      border: `1px solid ${isUser
                        ? 'rgba(var(--personality-accent-rgb), 0.2)'
                        : 'rgba(255, 255, 255, 0.06)'}`,
                      backdropFilter: 'blur(8px)',
                    }}>
                      <p style={{
                        margin: 0,
                        fontSize: 13,
                        lineHeight: 1.5,
                        color: isUser
                          ? 'var(--personality-accent)'
                          : 'rgba(255, 255, 255, 0.75)',
                        wordBreak: 'break-word',
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
        borderTop: '1px solid rgba(var(--personality-accent-rgb), 0.06)',
      }}>
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
                padding: '10px 14px',
                borderRadius: 20,
                border: `1px solid ${inputFocused
                  ? 'rgba(var(--personality-accent-rgb), 0.3)'
                  : 'rgba(255,255,255,0.08)'}`,
                background: inputFocused
                  ? 'rgba(var(--personality-accent-rgb), 0.06)'
                  : 'rgba(255,255,255,0.04)',
                color: 'rgba(255,255,255,0.85)',
                fontSize: 13,
                outline: 'none',
                fontFamily: 'inherit',
                boxSizing: 'border-box',
                transition: 'border-color 0.2s, background 0.2s, box-shadow 0.2s',
                boxShadow: inputFocused
                  ? '0 0 12px rgba(var(--personality-accent-rgb), 0.15)'
                  : 'none',
              }}
            />
          </div>

          {/* Send button */}
          <motion.button
            onClick={handleSend}
            whileHover={{ scale: 1.08 }}
            whileTap={{ scale: 0.92 }}
            style={{
              width: 36, height: 36, borderRadius: 18,
              background: inputValue.trim()
                ? 'var(--personality-accent)'
                : 'rgba(255,255,255,0.06)',
              border: 'none',
              cursor: inputValue.trim() ? 'pointer' : 'default',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              transition: 'background 0.2s',
              boxShadow: inputValue.trim()
                ? '0 2px 10px rgba(var(--personality-accent-rgb), 0.3)'
                : 'none',
              flexShrink: 0,
            }}
          >
            {/* Arrow up icon */}
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
              stroke={inputValue.trim() ? '#fff' : 'rgba(255,255,255,0.2)'}
              strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
            >
              <line x1="12" y1="19" x2="12" y2="5" />
              <polyline points="5 12 12 5 19 12" />
            </svg>
          </motion.button>
        </div>
      </div>
    </div>
  )
}
