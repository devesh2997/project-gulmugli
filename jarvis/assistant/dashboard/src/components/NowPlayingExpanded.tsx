/**
 * NowPlayingExpanded -- full-width bottom sheet with frosted glass.
 *
 * Features:
 *   - Bottom sheet (slides up from bottom) with frosted glass
 *   - Large visualiser at the top
 *   - Song title + artist prominently displayed
 *   - Progress bar with seek
 *   - Playback controls (prev, play/pause, skip, stop) as clean icon buttons
 *   - Volume slider
 *   - Close button or swipe down to collapse
 *   - Personality accent for all highlights
 *
 * Shares layoutId="now-playing" with NowPlayingCompact for morph animation.
 * Auto-collapses after 6 seconds of no interaction.
 */

import { useCallback, useEffect, useRef } from 'react'
import { motion, PanInfo } from 'framer-motion'
import type { NowPlaying, AssistantActions } from '../types/assistant'

interface NowPlayingExpandedProps {
  nowPlaying: NowPlaying
  actions: AssistantActions
  onCollapse: () => void
}

function fmt(s: number) {
  if (!s || s <= 0) return '0:00'
  return `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`
}

/** Large animated visualiser bars */
function Visualiser({ paused }: { paused: boolean }) {
  const barCount = 24
  const bars = Array.from({ length: barCount }, (_, i) => {
    const phase = i * 0.4
    return {
      heights: [
        8 + Math.sin(phase) * 16,
        8 + Math.sin(phase + 1.2) * 20,
        8 + Math.sin(phase + 2.4) * 14,
        8 + Math.sin(phase + 3.6) * 18,
        8 + Math.sin(phase) * 16,
      ],
      delay: i * 0.04,
    }
  })

  return (
    <div style={{
      display: 'flex',
      alignItems: 'flex-end',
      justifyContent: 'center',
      gap: 2,
      height: 40,
      width: '100%',
      padding: '0 8px',
    }}>
      {bars.map((bar, i) => (
        <motion.div
          key={i}
          style={{
            width: 3,
            borderRadius: 1.5,
            background: 'var(--personality-accent)',
            flexShrink: 0,
          }}
          animate={paused
            ? { height: 3, opacity: 0.2 }
            : { height: bar.heights, opacity: [0.3, 0.7, 0.4, 0.65, 0.3] }
          }
          transition={paused
            ? { duration: 0.4 }
            : { duration: 1.2, repeat: Infinity, delay: bar.delay, ease: 'easeInOut' }
          }
        />
      ))}
    </div>
  )
}

/** Clean icon button for controls */
function ControlBtn({ onClick, label, primary = false, size = 40, children }: {
  onClick: () => void
  label: string
  primary?: boolean
  size?: number
  children: React.ReactNode
}) {
  return (
    <motion.button
      whileHover={{ scale: 1.08 }}
      whileTap={{ scale: 0.92 }}
      onClick={onClick}
      aria-label={label}
      style={{
        width: size,
        height: size,
        borderRadius: '50%',
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
        background: primary
          ? 'rgba(var(--personality-accent-rgb), 0.15)'
          : 'var(--surface-subtle)',
        border: primary
          ? '1px solid rgba(var(--personality-accent-rgb), 0.3)'
          : '1px solid var(--border-subtle)',
        color: primary
          ? 'var(--personality-accent)'
          : 'var(--text-secondary)',
      }}
    >
      {children}
    </motion.button>
  )
}

export function NowPlayingExpanded({ nowPlaying, actions, onCollapse }: NowPlayingExpandedProps) {
  const barRef = useRef<HTMLDivElement>(null)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const reset = useCallback(() => {
    if (timer.current) clearTimeout(timer.current)
    timer.current = setTimeout(onCollapse, 6000)
  }, [onCollapse])

  useEffect(() => {
    reset()
    return () => { if (timer.current) clearTimeout(timer.current) }
  }, [reset])

  const seekFromEvent = useCallback((clientX: number) => {
    if (!nowPlaying.duration || !barRef.current) return
    const r = barRef.current.getBoundingClientRect()
    const ratio = Math.max(0, Math.min(1, (clientX - r.left) / r.width))
    actions.seek(ratio * nowPlaying.duration)
    reset()
  }, [nowPlaying.duration, actions, reset])

  const handleSeekPointerDown = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    e.stopPropagation() // prevent sheet drag
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

  const handleDragEnd = (_: MouseEvent | TouchEvent | PointerEvent, info: PanInfo) => {
    if (info.offset.y > 60) {
      onCollapse()
    }
  }

  const pct = nowPlaying.duration > 0 ? (nowPlaying.position / nowPlaying.duration) * 100 : 0

  return (
    <>
      {/* Backdrop overlay */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onCollapse}
        style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(0, 0, 0, 0.4)',
          zIndex: 59,
        }}
      />

      {/* Bottom sheet */}
      <motion.div
        layoutId="now-playing"
        data-gesture-ignore="true"
        initial={{ y: '100%' }}
        animate={{ y: 0 }}
        exit={{ y: '100%' }}
        transition={{ type: 'spring', damping: 28, stiffness: 300 }}
        drag="y"
        dragConstraints={{ top: 0, bottom: 0 }}
        dragElastic={{ top: 0, bottom: 0.4 }}
        onDragEnd={handleDragEnd}
        onPointerDown={() => reset()}
        style={{
          position: 'fixed',
          bottom: 0,
          left: 0,
          right: 0,
          zIndex: 60,
          padding: '16px 24px 32px',
          borderRadius: '20px 20px 0 0',
          background: 'rgba(14, 14, 14, 0.88)',
          backdropFilter: 'blur(32px)',
          WebkitBackdropFilter: 'blur(32px)',
          border: '1px solid var(--border-subtle)',
          borderBottom: 'none',
          boxShadow: '0 -4px 32px rgba(0, 0, 0, 0.4), 0 0 24px rgba(var(--personality-accent-rgb), 0.05)',
          display: 'flex',
          flexDirection: 'column',
          gap: 20,
          maxWidth: 480,
          marginLeft: 'auto',
          marginRight: 'auto',
        }}
      >
        {/* Drag handle */}
        <div style={{ display: 'flex', justifyContent: 'center', paddingBottom: 4 }}>
          <div style={{
            width: 36,
            height: 4,
            borderRadius: 2,
            background: 'var(--text-tertiary)',
          }} />
        </div>

        {/* Visualiser */}
        <Visualiser paused={nowPlaying.paused} />

        {/* Art + info */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          {nowPlaying.artUrl
            ? <img
                src={nowPlaying.artUrl}
                alt=""
                style={{
                  width: 72,
                  height: 72,
                  borderRadius: 12,
                  objectFit: 'cover',
                  flexShrink: 0,
                  boxShadow: '0 4px 12px rgba(0, 0, 0, 0.3)',
                }}
              />
            : <div style={{
                width: 72,
                height: 72,
                borderRadius: 12,
                background: 'rgba(var(--personality-accent-rgb), 0.08)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '1.8rem',
                color: 'var(--personality-accent)',
                flexShrink: 0,
              }}>
                &#9835;
              </div>
          }
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{
              fontSize: '1.05rem',
              fontWeight: 600,
              color: 'var(--text-primary)',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}>
              {nowPlaying.title}
            </div>
            <div style={{
              fontSize: '0.82rem',
              color: 'var(--personality-accent)',
              opacity: 0.75,
              marginTop: 3,
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}>
              {nowPlaying.artist}
            </div>
            {nowPlaying.album && (
              <div style={{
                fontSize: '0.7rem',
                color: 'var(--text-tertiary)',
                marginTop: 2,
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}>
                {nowPlaying.album}
              </div>
            )}
          </div>
        </div>

        {/* Progress bar */}
        {nowPlaying.duration > 0 && (
          <div>
            <div
              ref={barRef}
              onPointerDown={handleSeekPointerDown}
              role="slider"
              aria-label="Seek"
              aria-valuenow={nowPlaying.position}
              aria-valuemax={nowPlaying.duration}
              style={{
                width: '100%',
                height: 12,  /* larger hit target for touch */
                borderRadius: 9999,
                background: 'var(--surface-subtle)',
                cursor: 'pointer',
                position: 'relative',
                display: 'flex',
                alignItems: 'center',
                touchAction: 'none',
              }}
            >
              <motion.div
                style={{
                  height: '100%',
                  borderRadius: 9999,
                  background: 'var(--personality-accent)',
                  width: `${pct}%`,
                  boxShadow: '0 0 6px rgba(var(--personality-accent-rgb), 0.3)',
                }}
                transition={{ duration: 0.5 }}
              />
              {/* Seek knob */}
              <motion.div
                style={{
                  position: 'absolute',
                  top: -4,
                  left: `${pct}%`,
                  width: 12,
                  height: 12,
                  borderRadius: '50%',
                  background: 'var(--personality-accent)',
                  transform: 'translateX(-50%)',
                  boxShadow: '0 0 8px rgba(var(--personality-accent-rgb), 0.4)',
                  opacity: 0.9,
                }}
              />
            </div>
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              marginTop: 6,
              fontSize: '0.62rem',
              color: 'var(--text-tertiary)',
              fontFamily: 'ui-monospace, "SF Mono", "Cascadia Mono", monospace',
            }}>
              <span>{fmt(nowPlaying.position)}</span>
              <span>{fmt(nowPlaying.duration)}</span>
            </div>
          </div>
        )}

        {/* Playback controls */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 16 }}>
          {/* Stop */}
          <ControlBtn onClick={() => { actions.stop(); reset() }} label="Stop">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor">
              <rect x="2" y="2" width="10" height="10" rx="1.5" />
            </svg>
          </ControlBtn>

          {/* Play / Pause */}
          <ControlBtn
            onClick={() => { nowPlaying.paused ? actions.resume() : actions.pause(); reset() }}
            label={nowPlaying.paused ? 'Play' : 'Pause'}
            primary
            size={52}
          >
            {nowPlaying.paused
              ? <svg width="18" height="18" viewBox="0 0 18 18" fill="currentColor"><path d="M4 2l13 7-13 7V2z" /></svg>
              : <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><rect x="2.5" y="1" width="4" height="14" rx="1.2" /><rect x="9.5" y="1" width="4" height="14" rx="1.2" /></svg>
            }
          </ControlBtn>

          {/* Skip */}
          <ControlBtn onClick={() => { actions.skip(); reset() }} label="Skip">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor">
              <path d="M2 2l7 5-7 5V2z" /><rect x="10" y="2" width="2" height="10" rx=".5" />
            </svg>
          </ControlBtn>
        </div>

        {/* Volume */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '0 4px' }}>
          <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor" style={{ color: 'var(--text-tertiary)', flexShrink: 0 }}>
            <path d="M2 5h2.5L8 2v10L4.5 9H2a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1z" />
            <path d="M10 5.5a2.5 2.5 0 0 1 0 3" stroke="currentColor" strokeWidth={1.2} fill="none" strokeLinecap="round" />
          </svg>
          <input
            type="range"
            min={0}
            max={100}
            defaultValue={50}
            onChange={e => { actions.setVolume(Number(e.target.value)); reset() }}
            aria-label="Volume"
            style={{
              flex: 1,
              accentColor: 'var(--personality-accent)',
              cursor: 'pointer',
              height: 4,
            }}
          />
          <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor" style={{ color: 'var(--text-tertiary)', flexShrink: 0 }}>
            <path d="M2 5h2.5L8 2v10L4.5 9H2a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1z" />
            <path d="M10 4.5a3.5 3.5 0 0 1 0 5M12 3a5.5 5.5 0 0 1 0 8" stroke="currentColor" strokeWidth={1.2} fill="none" strokeLinecap="round" />
          </svg>
        </div>
      </motion.div>
    </>
  )
}
