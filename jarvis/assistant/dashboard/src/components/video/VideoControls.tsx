/**
 * VideoControls -- Apple TV-style overlay controls for the floating video player.
 *
 * Renders on top of the YouTube iframe with:
 *   - Top bar: song title + artist (left), close X button (right)
 *   - Center: large play/pause button with 10s skip flanking
 *   - Bottom: thin progress bar with timestamps
 *
 * Auto-hides after 4s of no interaction. Tap anywhere to toggle.
 * Uses semi-transparent gradient overlays for readability.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

interface VideoControlsProps {
  title: string
  artist: string
  paused: boolean
  duration: number
  position: number
  onPlayPause: () => void
  onSeek: (position: number) => void
  onClose: () => void
  onMinimize: () => void
}

function fmt(s: number) {
  if (!s || s <= 0) return '0:00'
  return `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`
}

export function VideoControls({
  title,
  artist,
  paused,
  duration,
  position,
  onPlayPause,
  onSeek,
  onClose,
  onMinimize,
}: VideoControlsProps) {
  const [visible, setVisible] = useState(true)
  const hideTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const barRef = useRef<HTMLDivElement>(null)

  const resetHideTimer = useCallback(() => {
    if (hideTimer.current) clearTimeout(hideTimer.current)
    setVisible(true)
    hideTimer.current = setTimeout(() => setVisible(false), 4000)
  }, [])

  useEffect(() => {
    resetHideTimer()
    return () => {
      if (hideTimer.current) clearTimeout(hideTimer.current)
    }
  }, [resetHideTimer])

  // Show controls when paused
  useEffect(() => {
    if (paused) {
      setVisible(true)
      if (hideTimer.current) clearTimeout(hideTimer.current)
    } else {
      resetHideTimer()
    }
  }, [paused, resetHideTimer])

  const handleToggle = useCallback(() => {
    if (visible) {
      setVisible(false)
      if (hideTimer.current) clearTimeout(hideTimer.current)
    } else {
      resetHideTimer()
    }
  }, [visible, resetHideTimer])

  const handleInteraction = useCallback(() => {
    resetHideTimer()
  }, [resetHideTimer])

  const seekFromEvent = useCallback((clientX: number) => {
    if (!duration || !barRef.current) return
    const r = barRef.current.getBoundingClientRect()
    const ratio = Math.max(0, Math.min(1, (clientX - r.left) / r.width))
    onSeek(ratio * duration)
    resetHideTimer()
  }, [duration, onSeek, resetHideTimer])

  const handleSeekPointerDown = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    e.stopPropagation()
    const target = e.currentTarget
    target.setPointerCapture(e.pointerId)
    seekFromEvent(e.clientX)

    const onMove = (ev: PointerEvent) => seekFromEvent(ev.clientX)
    const onUp = () => {
      target.removeEventListener('pointermove', onMove)
      target.removeEventListener('pointerup', onUp)
    }
    target.addEventListener('pointermove', onMove)
    target.addEventListener('pointerup', onUp)
  }, [seekFromEvent])

  const pct = duration > 0 ? (position / duration) * 100 : 0

  return (
    <div
      onClick={handleToggle}
      onPointerMove={handleInteraction}
      style={{
        position: 'absolute',
        inset: 0,
        borderRadius: 'inherit',
        overflow: 'hidden',
        zIndex: 2,
        cursor: 'pointer',
      }}
    >
      <AnimatePresence>
        {visible && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
            style={{ position: 'absolute', inset: 0 }}
          >
            {/* Top gradient overlay */}
            <div style={{
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              height: 100,
              background: 'linear-gradient(to bottom, rgba(0,0,0,0.7) 0%, transparent 100%)',
              borderRadius: '24px 24px 0 0',
              pointerEvents: 'none',
            }} />

            {/* Bottom gradient overlay */}
            <div style={{
              position: 'absolute',
              bottom: 0,
              left: 0,
              right: 0,
              height: 120,
              background: 'linear-gradient(to top, rgba(0,0,0,0.7) 0%, transparent 100%)',
              borderRadius: '0 0 24px 24px',
              pointerEvents: 'none',
            }} />

            {/* Top bar: title + close */}
            <div
              onClick={e => e.stopPropagation()}
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                right: 0,
                padding: '16px 20px',
                display: 'flex',
                alignItems: 'flex-start',
                justifyContent: 'space-between',
                gap: 12,
              }}
            >
              <div style={{ minWidth: 0, flex: 1 }}>
                <div style={{
                  fontSize: '0.95rem',
                  fontWeight: 600,
                  color: '#fff',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  textShadow: '0 1px 4px rgba(0,0,0,0.5)',
                }}>
                  {title}
                </div>
                <div style={{
                  fontSize: '0.78rem',
                  color: 'rgba(255,255,255,0.7)',
                  marginTop: 2,
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  textShadow: '0 1px 4px rgba(0,0,0,0.5)',
                }}>
                  {artist}
                </div>
              </div>

              <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
                {/* Minimize button */}
                <motion.button
                  whileHover={{ scale: 1.1 }}
                  whileTap={{ scale: 0.88 }}
                  onClick={(e) => { e.stopPropagation(); onMinimize() }}
                  aria-label="Minimize to mini player"
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: '50%',
                    background: 'rgba(255,255,255,0.1)',
                    border: 'none',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: 'rgba(255,255,255,0.8)',
                    backdropFilter: 'blur(8px)',
                  }}
                >
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
                    <path d="M2 12h10" />
                    <path d="M5 8l2 2 2-2" />
                  </svg>
                </motion.button>

                {/* Close button */}
                <motion.button
                  whileHover={{ scale: 1.1, background: 'rgba(var(--personality-accent-rgb), 0.2)' }}
                  whileTap={{ scale: 0.88 }}
                  onClick={(e) => { e.stopPropagation(); onClose() }}
                  aria-label="Close video"
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: '50%',
                    background: 'rgba(255,255,255,0.1)',
                    border: 'none',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: 'rgba(255,255,255,0.8)',
                    backdropFilter: 'blur(8px)',
                  }}
                >
                  <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                    <path d="M2 2l8 8M10 2l-8 8" />
                  </svg>
                </motion.button>
              </div>
            </div>

            {/* Center: play/pause + skip buttons */}
            <div
              onClick={e => e.stopPropagation()}
              style={{
                position: 'absolute',
                top: '50%',
                left: '50%',
                transform: 'translate(-50%, -50%)',
                display: 'flex',
                alignItems: 'center',
                gap: 32,
              }}
            >
              {/* Skip backward 10s */}
              <motion.button
                whileHover={{ scale: 1.1 }}
                whileTap={{ scale: 0.85 }}
                onClick={() => { onSeek(Math.max(0, position - 10)); resetHideTimer() }}
                aria-label="Skip back 10 seconds"
                style={{
                  width: 44,
                  height: 44,
                  borderRadius: '50%',
                  background: 'rgba(0,0,0,0.3)',
                  backdropFilter: 'blur(8px)',
                  border: 'none',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'rgba(255,255,255,0.85)',
                }}
              >
                <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                  <path d="M9 3V1L5 4l4 3V5a5 5 0 1 1-4.9 5.9" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" fill="none" />
                  <text x="8" y="12.5" fill="currentColor" fontSize="6" fontWeight="600" textAnchor="middle">10</text>
                </svg>
              </motion.button>

              {/* Play/Pause */}
              <motion.button
                whileHover={{ scale: 1.08 }}
                whileTap={{ scale: 0.9 }}
                onClick={() => { onPlayPause(); resetHideTimer() }}
                aria-label={paused ? 'Play' : 'Pause'}
                style={{
                  width: 60,
                  height: 60,
                  borderRadius: '50%',
                  background: 'rgba(0,0,0,0.35)',
                  backdropFilter: 'blur(12px)',
                  border: '2px solid rgba(var(--personality-accent-rgb), 0.3)',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#fff',
                  boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
                }}
              >
                {paused
                  ? <svg width="24" height="24" viewBox="0 0 18 18" fill="currentColor"><path d="M4 2l13 7-13 7V2z" /></svg>
                  : <svg width="22" height="22" viewBox="0 0 16 16" fill="currentColor"><rect x="2.5" y="1" width="4" height="14" rx="1.5" /><rect x="9.5" y="1" width="4" height="14" rx="1.5" /></svg>
                }
              </motion.button>

              {/* Skip forward 10s */}
              <motion.button
                whileHover={{ scale: 1.1 }}
                whileTap={{ scale: 0.85 }}
                onClick={() => { onSeek(Math.min(duration, position + 10)); resetHideTimer() }}
                aria-label="Skip forward 10 seconds"
                style={{
                  width: 44,
                  height: 44,
                  borderRadius: '50%',
                  background: 'rgba(0,0,0,0.3)',
                  backdropFilter: 'blur(8px)',
                  border: 'none',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'rgba(255,255,255,0.85)',
                }}
              >
                <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                  <path d="M9 3V1l4 3-4 3V5a5 5 0 1 0 4.9 5.9" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" fill="none" />
                  <text x="9" y="12.5" fill="currentColor" fontSize="6" fontWeight="600" textAnchor="middle">10</text>
                </svg>
              </motion.button>
            </div>

            {/* Bottom: progress bar + timestamps */}
            <div
              onClick={e => e.stopPropagation()}
              style={{
                position: 'absolute',
                bottom: 0,
                left: 0,
                right: 0,
                padding: '0 20px 16px',
              }}
            >
              {duration > 0 && (
                <>
                  <div
                    ref={barRef}
                    onPointerDown={handleSeekPointerDown}
                    role="slider"
                    aria-label="Seek"
                    aria-valuenow={position}
                    aria-valuemax={duration}
                    style={{
                      width: '100%',
                      height: 16,
                      cursor: 'pointer',
                      position: 'relative',
                      display: 'flex',
                      alignItems: 'center',
                      touchAction: 'none',
                    }}
                  >
                    {/* Track background */}
                    <div style={{
                      position: 'absolute',
                      left: 0,
                      right: 0,
                      height: 3,
                      borderRadius: 9999,
                      background: 'rgba(255,255,255,0.15)',
                      top: '50%',
                      transform: 'translateY(-50%)',
                    }} />
                    {/* Track fill */}
                    <motion.div
                      style={{
                        position: 'absolute',
                        left: 0,
                        height: 3,
                        borderRadius: 9999,
                        background: 'var(--personality-accent)',
                        top: '50%',
                        transform: 'translateY(-50%)',
                        width: `${pct}%`,
                      }}
                      transition={{ duration: 0.3 }}
                    />
                    {/* Seek knob */}
                    <motion.div
                      style={{
                        position: 'absolute',
                        top: '50%',
                        left: `${pct}%`,
                        width: 12,
                        height: 12,
                        borderRadius: '50%',
                        background: '#fff',
                        transform: 'translate(-50%, -50%)',
                        boxShadow: '0 0 8px rgba(0,0,0,0.4), 0 0 12px rgba(var(--personality-accent-rgb), 0.3)',
                      }}
                    />
                  </div>
                  <div style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    marginTop: 4,
                    fontSize: '0.6rem',
                    color: 'rgba(255,255,255,0.5)',
                    fontFamily: 'var(--font-mono)',
                    letterSpacing: '0.04em',
                  }}>
                    <span>{fmt(position)}</span>
                    <span>{fmt(duration)}</span>
                  </div>
                </>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
