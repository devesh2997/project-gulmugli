/**
 * Conversation transcript panel.
 *
 * Renders inside a SlidePanel — no outer card or border styling.
 * User messages in personality accent color, assistant messages in muted white.
 * Auto-scrolls to bottom on new messages.
 */

import { useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { TranscriptEntry } from '../types/assistant'

interface TranscriptProps {
  messages?: TranscriptEntry[]
}

export default function Transcript({ messages = [] }: TranscriptProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length])

  if (messages.length === 0) {
    return (
      <div
        style={{
          padding: 32,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100%',
        }}
      >
        <p style={{ color: 'var(--text-muted)', fontStyle: 'italic', fontSize: 14 }}>
          Say something to get started...
        </p>
      </div>
    )
  }

  return (
    <div
      style={{
        padding: '20px 16px',
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        boxSizing: 'border-box',
      }}
    >
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          paddingBottom: 12,
          marginBottom: 12,
          borderBottom: '1px solid rgba(255,255,255,0.08)',
        }}
      >
        <div
          style={{
            width: 8, height: 8, borderRadius: '50%',
            background: 'var(--personality-accent)',
          }}
        />
        <span
          style={{
            fontSize: 11,
            fontWeight: 500,
            textTransform: 'uppercase',
            letterSpacing: '0.1em',
            color: 'rgba(255,255,255,0.4)',
          }}
        >
          Conversation
        </span>
      </div>

      {/* Messages */}
      <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 12 }}>
        <AnimatePresence initial={false}>
          {messages.map((msg, i) => {
            const isUser = msg.role === 'user'
            const isRecent = i >= messages.length - 3
            return (
              <motion.div
                key={msg.timestamp + i}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: isRecent ? 1 : 0.45, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.25 }}
                style={{
                  display: 'flex',
                  justifyContent: isUser ? 'flex-end' : 'flex-start',
                }}
              >
                <p
                  style={{
                    maxWidth: '85%',
                    margin: 0,
                    fontSize: 'clamp(0.8rem, 1.5vw, 0.9rem)',
                    lineHeight: 1.55,
                    color: isUser ? 'var(--personality-accent)' : 'rgba(255,255,255,0.75)',
                  }}
                >
                  {msg.text}
                </p>
              </motion.div>
            )
          })}
        </AnimatePresence>
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
