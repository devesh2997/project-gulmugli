/**
 * NowPlayingExpanded -- immersive full-width bottom sheet music experience.
 *
 * Redesigned to feel purpose-built:
 *   - Organic visualiser with smooth sine-wave motion and personality gradient
 *   - Large album art with personality-colored glow halo
 *   - Custom progress bar with fluid seek knob
 *   - Borderless control buttons with personality accent fills
 *   - Custom volume slider matching the visual language
 *   - Ambient personality color wash behind everything
 *
 * Shares layoutId="now-playing" with NowPlayingCompact for morph animation.
 * Auto-collapses after 6 seconds of no interaction.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { motion, PanInfo } from 'framer-motion'
import type { NowPlaying, AssistantActions } from '../types/assistant'

interface NowPlayingExpandedProps {
  nowPlaying: NowPlaying
  actions: AssistantActions
  onCollapse: () => void
  /** YouTube videoId for embedded peek video (empty string = no video) */
  videoId?: string | null
  /** Callback when the video area is tapped — expands to full video player */
  onExpandVideo?: () => void
}

function fmt(s: number) {
  if (!s || s <= 0) return '0:00'
  return `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`
}

/** Organic visualiser with sine-wave interpolation */
function Visualiser({ paused }: { paused: boolean }) {
  const barCount = 32
  const bars = Array.from({ length: barCount }, (_, i) => {
    const center = barCount / 2
    const dist = Math.abs(i - center) / center
    const amplitude = 1 - dist * 0.6
    const phase = i * 0.35
    return {
      heights: [
        6 + Math.sin(phase) * 18 * amplitude,
        6 + Math.sin(phase + 1.0) * 22 * amplitude,
        6 + Math.sin(phase + 2.0) * 14 * amplitude,
        6 + Math.sin(phase + 3.0) * 20 * amplitude,
        6 + Math.sin(phase) * 18 * amplitude,
      ],
      delay: i * 0.03,
      opacity: 0.3 + amplitude * 0.5,
    }
  })

  return (
    <div style={{
      display: 'flex',
      alignItems: 'flex-end',
      justifyContent: 'center',
      gap: 1.5,
      height: 48,
      width: '100%',
      padding: '0 12px',
    }}>
      {bars.map((bar, i) => (
        <motion.div
          key={i}
          style={{
            width: 2.5,
            borderRadius: 2,
            background: 'var(--personality-accent)',
            flexShrink: 0,
          }}
          animate={paused
            ? { height: 2, opacity: 0.12 }
            : { height: bar.heights, opacity: bar.opacity }
          }
          transition={paused
            ? { duration: 0.5, ease: 'easeOut' }
            : { duration: 1.0 + (i % 3) * 0.2, repeat: Infinity, delay: bar.delay, ease: 'easeInOut' }
          }
        />
      ))}
    </div>
  )
}

/** Borderless control button with personality accent */
function ControlBtn({ onClick, label, primary = false, size = 42, children }: {
  onClick: () => void
  label: string
  primary?: boolean
  size?: number
  children: React.ReactNode
}) {
  return (
    <motion.button
      whileHover={{ scale: 1.1 }}
      whileTap={{ scale: 0.88 }}
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
          ? 'rgba(var(--personality-accent-rgb), 0.2)'
          : 'rgba(255, 255, 255, 0.04)',
        border: 'none',
        color: primary
          ? 'var(--personality-accent)'
          : 'var(--text-secondary)',
        transition: 'background 0.2s ease',
      }}
    >
      {children}
    </motion.button>
  )
}

export function NowPlayingExpanded({ nowPlaying, actions, onCollapse, videoId, onExpandVideo }: NowPlayingExpandedProps) {
  const barRef = useRef<HTMLDivElement>(null)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Seek optimistic update: override position locally for 2s after seeking
  const [seekOverride, setSeekOverride] = useState<number | null>(null)
  const seekOverrideTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Volume debounce: only send every 100ms
  const volumeTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const debouncedSetVolume = useCallback((level: number) => {
    if (volumeTimer.current) clearTimeout(volumeTimer.current)
    volumeTimer.current = setTimeout(() => {
      actions.setVolume(level)
      volumeTimer.current = null
    }, 100)
  }, [actions])

  const reset = useCallback(() => {
    if (timer.current) clearTimeout(timer.current)
    timer.current = setTimeout(onCollapse, 6000)
  }, [onCollapse])

  useEffect(() => {
    reset()
    return () => {
      if (timer.current) clearTimeout(timer.current)
      if (seekOverrideTimer.current) clearTimeout(seekOverrideTimer.current)
      if (volumeTimer.current) clearTimeout(volumeTimer.current)
    }
  }, [reset])

  const seekFromEvent = useCallback((clientX: number) => {
    if (!nowPlaying.duration || !barRef.current) return
    const r = barRef.current.getBoundingClientRect()
    const ratio = Math.max(0, Math.min(1, (clientX - r.left) / r.width))
    const newPos = ratio * nowPlaying.duration
    actions.seek(newPos)
    // Optimistic: show the new position immediately and block poll updates for 2s
    setSeekOverride(newPos)
    if (seekOverrideTimer.current) clearTimeout(seekOverrideTimer.current)
    seekOverrideTimer.current = setTimeout(() => setSeekOverride(null), 2000)
    reset()
  }, [nowPlaying.duration, actions, reset])

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

  const handleDragEnd = (_: MouseEvent | TouchEvent | PointerEvent, info: PanInfo) => {
    if (info.offset.y > 60) {
      onCollapse()
    }
  }

  const displayPosition = seekOverride !== null ? seekOverride : nowPlaying.position
  const pct = nowPlaying.duration > 0 ? (displayPosition / nowPlaying.duration) * 100 : 0

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
          background: 'rgba(0, 0, 0, 0.5)',
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
        transition={{ type: 'spring', damping: 30, stiffness: 280, mass: 0.8 }}
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
          padding: '12px 24px 36px',
          borderRadius: '28px 28px 0 0',
          background: 'rgba(12, 10, 18, 0.92)',
          backdropFilter: 'blur(40px) saturate(1.4)',
          WebkitBackdropFilter: 'blur(40px) saturate(1.4)',
          border: 'none',
          boxShadow: '0 -4px 40px rgba(0, 0, 0, 0.4), 0 0 40px rgba(var(--personality-accent-rgb), 0.06)',
          display: 'flex',
          flexDirection: 'column',
          gap: 18,
          maxWidth: 480,
          marginLeft: 'auto',
          marginRight: 'auto',
          overflow: 'hidden',
        }}
      >
        {/* Ambient personality wash at the top */}
        <div style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          height: 120,
          background: 'radial-gradient(ellipse at 50% -20%, rgba(var(--personality-accent-rgb), 0.1) 0%, transparent 70%)',
          pointerEvents: 'none',
        }} />

        {/* Drag handle */}
        <div style={{ display: 'flex', justifyContent: 'center', paddingBottom: 2 }}>
          <motion.div
            animate={{ opacity: [0.2, 0.4, 0.2] }}
            transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
            style={{
              width: 40,
              height: 4,
              borderRadius: 2,
              background: 'rgba(var(--personality-accent-rgb), 0.4)',
            }}
          />
        </div>

        {/* Video peek area — muted iframe showing current video */}
        {videoId && (
          <div
            onClick={(e) => {
              e.stopPropagation()
              onExpandVideo?.()
            }}
            style={{
              width: '100%',
              aspectRatio: '16 / 9',
              borderRadius: 16,
              overflow: 'hidden',
              position: 'relative',
              cursor: 'pointer',
              flexShrink: 0,
            }}
          >
            <iframe
              src={`https://www.youtube.com/embed/${videoId}?autoplay=0&controls=0&mute=1&modestbranding=1`}
              allow="autoplay; encrypted-media"
              style={{
                width: '100%',
                height: '100%',
                border: 'none',
                display: 'block',
                pointerEvents: 'none',
              }}
              title="Video peek"
            />
            {/* Tap-to-expand overlay hint */}
            <div style={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'rgba(0,0,0,0.15)',
              opacity: 0.7,
              transition: 'opacity 0.2s',
            }}>
              <svg width="32" height="32" viewBox="0 0 24 24" fill="white" opacity={0.7}>
                <path d="M4 4h4V2H2v6h2V4zm16 0v4h2V2h-6v2h4zM4 20v-4H2v6h6v-2H4zm16 0h-4v2h6v-6h-2v4z" />
              </svg>
            </div>
          </div>
        )}

        {/* Visualiser */}
        <Visualiser paused={nowPlaying.paused} />

        {/* Art + info */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, position: 'relative' }}>
          {nowPlaying.artUrl
            ? <div style={{ position: 'relative', flexShrink: 0 }}>
                {/* Glow behind art */}
                <div style={{
                  position: 'absolute',
                  inset: -8,
                  borderRadius: 18,
                  background: 'rgba(var(--personality-accent-rgb), 0.12)',
                  filter: 'blur(16px)',
                }} />
                <img
                  src={nowPlaying.artUrl}
                  alt=""
                  style={{
                    width: 72,
                    height: 72,
                    borderRadius: 14,
                    objectFit: 'cover',
                    position: 'relative',
                    boxShadow: '0 4px 16px rgba(0, 0, 0, 0.4)',
                  }}
                />
              </div>
            : <div style={{
                width: 72,
                height: 72,
                borderRadius: 14,
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
              letterSpacing: '0.01em',
            }}>
              {nowPlaying.title}
            </div>
            <div style={{
              fontSize: '0.82rem',
              color: 'var(--personality-accent)',
              opacity: 0.85,
              marginTop: 3,
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              fontWeight: 500,
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
                height: 14,
                borderRadius: 9999,
                background: 'rgba(255, 255, 255, 0.06)',
                cursor: 'pointer',
                position: 'relative',
                display: 'flex',
                alignItems: 'center',
                touchAction: 'none',
              }}
            >
              {/* Track fill with gradient */}
              <motion.div
                style={{
                  height: 4,
                  borderRadius: 9999,
                  background: `linear-gradient(90deg, rgba(var(--personality-accent-rgb), 0.6), var(--personality-accent))`,
                  width: `${pct}%`,
                  position: 'absolute',
                  top: '50%',
                  left: 0,
                  transform: 'translateY(-50%)',
                }}
                transition={{ duration: 0.5 }}
              />
              {/* Seek knob */}
              <motion.div
                style={{
                  position: 'absolute',
                  top: '50%',
                  left: `${pct}%`,
                  width: 14,
                  height: 14,
                  borderRadius: '50%',
                  background: 'var(--personality-accent)',
                  transform: 'translate(-50%, -50%)',
                  boxShadow: '0 0 12px rgba(var(--personality-accent-rgb), 0.4)',
                }}
              />
            </div>
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              marginTop: 6,
              fontSize: '0.6rem',
              color: 'var(--text-tertiary)',
              fontFamily: 'var(--font-mono)',
              letterSpacing: '0.04em',
            }}>
              <span>{fmt(displayPosition)}</span>
              <span>{fmt(nowPlaying.duration)}</span>
            </div>
          </div>
        )}

        {/* Playback controls */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 20 }}>
          {/* Stop */}
          <ControlBtn onClick={() => { actions.stop(); reset() }} label="Stop">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor">
              <rect x="2" y="2" width="10" height="10" rx="2" />
            </svg>
          </ControlBtn>

          {/* Play / Pause — larger primary */}
          <ControlBtn
            onClick={() => { nowPlaying.paused ? actions.resume() : actions.pause(); reset() }}
            label={nowPlaying.paused ? 'Play' : 'Pause'}
            primary
            size={56}
          >
            {nowPlaying.paused
              ? <svg width="20" height="20" viewBox="0 0 18 18" fill="currentColor"><path d="M4 2l13 7-13 7V2z" /></svg>
              : <svg width="18" height="18" viewBox="0 0 16 16" fill="currentColor"><rect x="2.5" y="1" width="4" height="14" rx="1.5" /><rect x="9.5" y="1" width="4" height="14" rx="1.5" /></svg>
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
            onChange={e => { debouncedSetVolume(Number(e.target.value)); reset() }}
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
