/**
 * MusicPlayer -- unified music component using the YouTube IFrame Player API.
 *
 * A SINGLE YT.Player instance is created and never destroyed while a song is active.
 * The player's container <div> is repositioned via CSS for each mode — the player
 * itself survives mode transitions without losing playback state.
 *
 * Modes:
 *   'compact'    — floating bottom bar (frosted glass, personality accent)
 *                  Player container positioned off-screen; audio still plays.
 *   'expanded'   — bottom sheet with video, controls, seek bar, volume
 *                  Player container moves into the sheet (visible video).
 *   'fullscreen' — edge-to-edge video with auto-hiding overlay controls
 *                  Player container fills viewport.
 *   'hidden'     — no UI, player destroyed
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion, PanInfo } from 'framer-motion'
import { VideoControls } from './video/VideoControls'
import { useLightMode } from '../hooks/useLightMode'
import type { NowPlaying, AssistantActions } from '../types/assistant'

declare global {
  interface Window {
    YT: any
    onYouTubeIframeAPIReady: () => void
  }
}

type PlayerMode = 'compact' | 'expanded' | 'fullscreen' | 'hidden'

interface MusicPlayerProps {
  nowPlaying: NowPlaying
  actions: AssistantActions
}

// ─── Helpers ───────────────────────────────────────────────

function fmt(s: number) {
  if (!s || s <= 0) return '0:00'
  return `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`
}

/** Marquee text that scrolls when content overflows. */
function MarqueeText({ text, style }: { text: string; style?: React.CSSProperties }) {
  const outerRef = useRef<HTMLDivElement>(null)
  const innerRef = useRef<HTMLSpanElement>(null)
  const [shouldScroll, setShouldScroll] = useState(false)

  useEffect(() => {
    const outer = outerRef.current
    const inner = innerRef.current
    if (!outer || !inner) return
    setShouldScroll(inner.scrollWidth > outer.clientWidth + 2)
  }, [text])

  return (
    <div
      ref={outerRef}
      style={{
        overflow: 'hidden',
        whiteSpace: 'nowrap',
        position: 'relative',
        maskImage: shouldScroll ? 'linear-gradient(90deg, transparent 0%, black 8%, black 88%, transparent 100%)' : undefined,
        WebkitMaskImage: shouldScroll ? 'linear-gradient(90deg, transparent 0%, black 8%, black 88%, transparent 100%)' : undefined,
        ...style,
      }}
    >
      <motion.span
        ref={innerRef}
        animate={shouldScroll
          ? { x: [0, -(innerRef.current?.scrollWidth ?? 0) - 30, 0] }
          : { x: 0 }
        }
        transition={shouldScroll
          ? { duration: Math.max(6, (text.length * 0.25)), repeat: Infinity, ease: 'linear', repeatDelay: 2 }
          : {}
        }
        style={{ display: 'inline-block' }}
      >
        {text}
        {shouldScroll && (
          <span style={{ paddingLeft: 30, opacity: 0.4 }}>
            {text}
          </span>
        )}
      </motion.span>
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

// ─── Main Component ────────────────────────────────────────

export function MusicPlayer({ nowPlaying, actions }: MusicPlayerProps) {
  const [mode, setMode] = useState<PlayerMode>('hidden')
  const isLight = useLightMode()
  const constraintsRef = useRef<HTMLDivElement>(null)

  // YT Player API
  const ytPlayerRef = useRef<any>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const [ytReady, setYtReady] = useState(!!window.YT?.Player)

  // Track position locally
  const [localPosition, setLocalPosition] = useState(0)
  const [localDuration, setLocalDuration] = useState(0)
  const [localPaused, setLocalPaused] = useState(false)

  // Seek optimistic update
  const [seekOverride, setSeekOverride] = useState<number | null>(null)
  const seekOverrideTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Volume debounce
  const volumeTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const debouncedSetVolume = useCallback((level: number) => {
    if (volumeTimer.current) clearTimeout(volumeTimer.current)
    volumeTimer.current = setTimeout(() => {
      actions.setVolume(level)
      // Also set volume on the YT player directly
      if (ytPlayerRef.current?.setVolume) {
        ytPlayerRef.current.setVolume(level)
      }
      volumeTimer.current = null
    }, 100)
  }, [actions])

  // Auto-collapse timer for expanded mode
  const collapseTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const resetCollapseTimer = useCallback(() => {
    if (collapseTimer.current) clearTimeout(collapseTimer.current)
    collapseTimer.current = setTimeout(() => {
      setMode(prev => prev === 'expanded' ? 'compact' : prev)
    }, 8000)
  }, [])

  // Track loaded videoId to avoid unnecessary reloads
  const loadedVideoIdRef = useRef<string | null>(null)

  // Position polling interval ref
  const positionPollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // ── Wait for YouTube IFrame API to load ──
  useEffect(() => {
    if (window.YT?.Player) {
      setYtReady(true)
      return
    }
    const prev = window.onYouTubeIframeAPIReady
    window.onYouTubeIframeAPIReady = () => {
      prev?.()
      setYtReady(true)
    }
    return () => {
      // Restore if we set it
      if (window.onYouTubeIframeAPIReady === arguments[0]) {
        window.onYouTubeIframeAPIReady = prev as any
      }
    }
  }, [])

  // ── Create / update the YT.Player when videoId changes ──
  useEffect(() => {
    if (!ytReady || !nowPlaying?.videoId) return

    const videoId = nowPlaying.videoId

    // If player exists and videoId is the same, skip
    if (ytPlayerRef.current && loadedVideoIdRef.current === videoId) return

    // If player exists but different video, just load the new video
    if (ytPlayerRef.current && loadedVideoIdRef.current !== videoId) {
      ytPlayerRef.current.loadVideoById(videoId)
      loadedVideoIdRef.current = videoId
      return
    }

    // No player yet — create one
    if (!containerRef.current) return

    // Create a child div for YT.Player to render into (it replaces the element)
    const playerDiv = document.createElement('div')
    playerDiv.id = 'yt-player-el'
    containerRef.current.innerHTML = ''
    containerRef.current.appendChild(playerDiv)

    ytPlayerRef.current = new window.YT.Player('yt-player-el', {
      videoId,
      playerVars: {
        autoplay: 1,
        controls: 0,
        modestbranding: 1,
        rel: 0,
        showinfo: 0,
        playsinline: 1,
        origin: window.location.origin,
      },
      events: {
        onReady: (event: any) => {
          event.target.playVideo()
          // Try to get duration
          const dur = event.target.getDuration?.()
          if (dur && dur > 0) setLocalDuration(dur)
        },
        onStateChange: (event: any) => {
          // 0=ended, 1=playing, 2=paused, 3=buffering
          if (event.data === 0) {
            actions.reportPlayerEnded()
            setMode('hidden')
          }
          if (event.data === 1) setLocalPaused(false)
          if (event.data === 2) setLocalPaused(true)
        },
      },
    })
    loadedVideoIdRef.current = videoId
  }, [ytReady, nowPlaying?.videoId, actions])

  // ── Position polling (every 1s from the player) ──
  useEffect(() => {
    if (positionPollRef.current) {
      clearInterval(positionPollRef.current)
      positionPollRef.current = null
    }

    if (mode === 'hidden') return

    positionPollRef.current = setInterval(() => {
      const player = ytPlayerRef.current
      if (!player?.getCurrentTime || !player?.getDuration) return

      const time = player.getCurrentTime()
      const dur = player.getDuration()

      if (typeof time === 'number' && seekOverride === null) {
        setLocalPosition(time)
      }
      if (typeof dur === 'number' && dur > 0) {
        setLocalDuration(dur)
      }
    }, 1000)

    return () => {
      if (positionPollRef.current) {
        clearInterval(positionPollRef.current)
        positionPollRef.current = null
      }
    }
  }, [mode, seekOverride])

  // ── When new song arrives, show compact ──
  useEffect(() => {
    if (nowPlaying?.videoId) {
      setMode('compact')
      setLocalPosition(0)
      setLocalDuration(nowPlaying.duration || 0)
      setLocalPaused(false)
    } else {
      setMode('hidden')
    }
  }, [nowPlaying?.videoId])

  // ── Sync paused state from backend ──
  useEffect(() => {
    setLocalPaused(nowPlaying.paused)
  }, [nowPlaying.paused])

  // ── Sync position from backend (when not seeking) ──
  useEffect(() => {
    if (seekOverride === null) {
      setLocalPosition(nowPlaying.position)
    }
    if (nowPlaying.duration > 0) {
      setLocalDuration(nowPlaying.duration)
    }
  }, [nowPlaying.position, nowPlaying.duration, seekOverride])

  // ── Listen for backend player_command events (voice commands) ──
  useEffect(() => {
    const handler = (e: Event) => {
      const cmd = (e as CustomEvent).detail
      if (!cmd) return
      const player = ytPlayerRef.current
      switch (cmd.command) {
        case 'pause':
          player?.pauseVideo?.()
          setLocalPaused(true)
          break
        case 'play':
          player?.playVideo?.()
          setLocalPaused(false)
          break
        case 'seek':
          if (typeof cmd.position === 'number') {
            player?.seekTo?.(cmd.position, true)
            setLocalPosition(cmd.position)
          }
          break
        case 'stop':
          player?.stopVideo?.()
          setMode('hidden')
          break
      }
    }
    window.addEventListener('jarvis-player-command', handler)
    return () => window.removeEventListener('jarvis-player-command', handler)
  }, [actions])

  // ── Position reporting to backend every 2s ──
  useEffect(() => {
    const interval = setInterval(() => {
      if (mode !== 'hidden' && localDuration > 0) {
        actions.reportPosition(localPosition, localDuration)
      }
    }, 2000)
    return () => clearInterval(interval)
  }, [mode, localPosition, localDuration, actions])

  // ── Destroy player when going hidden ──
  useEffect(() => {
    if (mode === 'hidden' && ytPlayerRef.current) {
      ytPlayerRef.current.destroy?.()
      ytPlayerRef.current = null
      loadedVideoIdRef.current = null
    }
  }, [mode])

  // ── Cleanup timers ──
  useEffect(() => {
    return () => {
      if (collapseTimer.current) clearTimeout(collapseTimer.current)
      if (seekOverrideTimer.current) clearTimeout(seekOverrideTimer.current)
      if (volumeTimer.current) clearTimeout(volumeTimer.current)
      if (positionPollRef.current) clearInterval(positionPollRef.current)
    }
  }, [])

  // ── Handlers ──
  const handlePlayPause = useCallback(() => {
    const player = ytPlayerRef.current
    if (localPaused) {
      player?.playVideo?.()
      actions.resume()
      setLocalPaused(false)
    } else {
      player?.pauseVideo?.()
      actions.pause()
      setLocalPaused(true)
    }
  }, [localPaused, actions])

  const handleSeek = useCallback((position: number) => {
    ytPlayerRef.current?.seekTo?.(position, true)
    actions.seek(position)
    setSeekOverride(position)
    if (seekOverrideTimer.current) clearTimeout(seekOverrideTimer.current)
    seekOverrideTimer.current = setTimeout(() => setSeekOverride(null), 2000)
  }, [actions])

  const handleStop = useCallback(() => {
    ytPlayerRef.current?.stopVideo?.()
    setMode('hidden')
    actions.stop()
  }, [actions])

  const handleCompactTap = useCallback(() => {
    setMode('expanded')
    resetCollapseTimer()
  }, [resetCollapseTimer])

  const handleCollapse = useCallback(() => {
    setMode('compact')
    if (collapseTimer.current) clearTimeout(collapseTimer.current)
  }, [])

  const handleToggleFullscreen = useCallback(() => {
    setMode(prev => prev === 'fullscreen' ? 'expanded' : 'fullscreen')
  }, [])

  const handleExpandedDragEnd = useCallback((_: MouseEvent | TouchEvent | PointerEvent, info: PanInfo) => {
    if (info.offset.y > 60) {
      handleCollapse()
    }
  }, [handleCollapse])

  // Expanded seek bar
  const barRef = useRef<HTMLDivElement>(null)
  const seekFromEvent = useCallback((clientX: number) => {
    if (!localDuration || !barRef.current) return
    const r = barRef.current.getBoundingClientRect()
    const ratio = Math.max(0, Math.min(1, (clientX - r.left) / r.width))
    handleSeek(ratio * localDuration)
    resetCollapseTimer()
  }, [localDuration, handleSeek, resetCollapseTimer])

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

  if (mode === 'hidden') return null

  const displayPosition = seekOverride !== null ? seekOverride : localPosition
  const pct = localDuration > 0 ? (displayPosition / localDuration) * 100 : 0
  const videoId = nowPlaying.videoId

  // Compute player container style based on mode
  const playerContainerStyle: React.CSSProperties = mode === 'compact'
    ? {
        position: 'fixed',
        left: -9999,
        top: -9999,
        width: 640,
        height: 360,
        zIndex: -1,
        pointerEvents: 'none',
      }
    : mode === 'expanded'
      ? {
          // Rendered inline inside the expanded sheet via a ref move
          width: '100%',
          aspectRatio: '16 / 9',
          borderRadius: 16,
          overflow: 'hidden',
          position: 'relative',
          flexShrink: 0,
          background: '#0a0a0a',
        }
      : mode === 'fullscreen'
        ? {
            width: '100%',
            height: '100%',
            position: 'absolute',
            inset: 0,
          }
        : {
            position: 'fixed',
            left: -9999,
            top: -9999,
            width: 640,
            height: 360,
            zIndex: -1,
            pointerEvents: 'none',
          }

  // We need to portal the container div into different layout positions.
  // Strategy: render the container in a fixed position wrapper always, and for
  // expanded/fullscreen modes, render a placeholder that we move the container into.
  // Actually, simpler: always render the container fixed/off-screen, and for
  // expanded/fullscreen just reposition it on-screen with proper styles.

  return (
    <>
      {/* Invisible drag constraints for compact mode */}
      <div
        ref={constraintsRef}
        style={{ position: 'fixed', inset: 0, pointerEvents: 'none', zIndex: 49 }}
      />

      {/* ── THE YT PLAYER CONTAINER ── always mounted, repositioned per mode */}
      {mode === 'compact' && (
        <div
          ref={containerRef}
          style={{
            position: 'fixed',
            left: -9999,
            top: -9999,
            width: 640,
            height: 360,
            zIndex: -1,
            pointerEvents: 'none',
          }}
        />
      )}

      {/* ── COMPACT MODE ── floating bottom bar */}
      <AnimatePresence>
        {mode === 'compact' && (
          <motion.div
            key="compact"
            data-gesture-ignore="true"
            initial={{ y: 20, opacity: 0, scale: 0.95 }}
            animate={{ y: 0, opacity: 1, scale: 1 }}
            exit={{ y: 20, opacity: 0, scale: 0.95 }}
            transition={{ type: 'spring', stiffness: 300, damping: 25 }}
            drag
            dragConstraints={constraintsRef}
            dragElastic={0.1}
            dragMomentum={false}
            whileDrag={{ scale: 1.04 }}
            onClick={handleCompactTap}
            style={{
              position: 'fixed',
              bottom: 28,
              left: '50%',
              translateX: '-50%',
              zIndex: 50,
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: '10px 16px 10px 12px',
              borderRadius: 20,
              background: isLight ? 'rgba(255, 255, 255, 0.75)' : 'rgba(18, 16, 24, 0.7)',
              backdropFilter: 'blur(24px) saturate(1.2)',
              WebkitBackdropFilter: 'blur(24px) saturate(1.2)',
              border: 'none',
              boxShadow: isLight
                ? '0 4px 24px rgba(0, 0, 0, 0.1), 0 1px 4px rgba(0, 0, 0, 0.06), inset 0 0.5px 0 rgba(255,255,255,0.6)'
                : `0 4px 24px rgba(0, 0, 0, 0.3), 0 0 24px rgba(var(--personality-accent-rgb), 0.1), inset 0 0.5px 0 rgba(255,255,255,0.04)`,
              cursor: 'pointer',
              userSelect: 'none',
              maxWidth: 280,
              minWidth: 180,
              transition: 'background 0.6s ease, box-shadow 0.6s ease',
            }}
          >
            {/* Thumbnail */}
            {videoId && (
              <div
                style={{
                  width: 64,
                  height: 36,
                  borderRadius: 8,
                  overflow: 'hidden',
                  flexShrink: 0,
                  position: 'relative',
                  boxShadow: isLight
                    ? '0 1px 4px rgba(0,0,0,0.1)'
                    : `0 1px 8px rgba(0,0,0,0.3), 0 0 6px rgba(var(--personality-accent-rgb), 0.08)`,
                }}
              >
                <img
                  src={`https://img.youtube.com/vi/${videoId}/mqdefault.jpg`}
                  alt=""
                  style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
                />
              </div>
            )}

            {/* Song info */}
            <div style={{ minWidth: 0, flex: 1, display: 'flex', flexDirection: 'column', gap: 2 }}>
              <MarqueeText
                text={nowPlaying.title}
                style={{
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  color: isLight ? 'rgba(30, 20, 10, 0.9)' : 'rgba(255, 255, 255, 0.9)',
                  maxWidth: 180,
                  letterSpacing: '0.01em',
                }}
              />
              {nowPlaying.artist && (
                <div style={{
                  fontSize: '0.62rem',
                  color: isLight ? '#4a3520' : 'var(--personality-accent)',
                  opacity: 0.8,
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  maxWidth: 180,
                  fontWeight: 500,
                }}>
                  {nowPlaying.artist}
                </div>
              )}
            </div>

            {/* Play/Pause button */}
            <motion.button
              whileTap={{ scale: 0.85 }}
              onClick={(e) => {
                e.stopPropagation()
                handlePlayPause()
              }}
              aria-label={localPaused ? 'Play' : 'Pause'}
              style={{
                width: 28,
                height: 28,
                borderRadius: '50%',
                background: 'rgba(var(--personality-accent-rgb), 0.15)',
                border: 'none',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
                color: isLight ? '#4a3520' : 'var(--personality-accent)',
              }}
            >
              {localPaused
                ? <svg width="10" height="10" viewBox="0 0 14 14" fill="currentColor"><path d="M4 2l8 5-8 5V2z" /></svg>
                : <svg width="10" height="10" viewBox="0 0 14 14" fill="currentColor"><rect x="2" y="1" width="3.5" height="12" rx="1" /><rect x="8.5" y="1" width="3.5" height="12" rx="1" /></svg>
              }
            </motion.button>

            {/* Living accent glow */}
            <motion.div
              animate={{ opacity: [0.04, 0.1, 0.04] }}
              transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
              style={{
                position: 'absolute',
                inset: 0,
                borderRadius: 20,
                background: isLight
                  ? 'radial-gradient(ellipse at 20% 50%, rgba(0,0,0,0.03) 0%, transparent 60%)'
                  : 'radial-gradient(ellipse at 15% 50%, rgba(var(--personality-accent-rgb), 0.15) 0%, transparent 60%)',
                pointerEvents: 'none',
              }}
            />

            {/* Progress line */}
            {localDuration > 0 && (
              <div
                style={{
                  position: 'absolute',
                  bottom: 0,
                  left: 0,
                  width: '100%',
                  height: 3,
                  borderRadius: '0 0 20px 20px',
                  overflow: 'hidden',
                  pointerEvents: 'none',
                  zIndex: 2,
                }}
              >
                <div
                  style={{
                    height: '100%',
                    width: `${Math.min(100, Math.max(0, pct))}%`,
                    background: 'var(--personality-accent)',
                    opacity: 0.6,
                    transition: 'width 1s linear',
                  }}
                />
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── EXPANDED MODE ── bottom sheet */}
      <AnimatePresence>
        {mode === 'expanded' && (
          <>
            {/* Backdrop */}
            <motion.div
              key="expanded-backdrop"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={handleCollapse}
              style={{
                position: 'fixed',
                inset: 0,
                background: 'rgba(0, 0, 0, 0.5)',
                zIndex: 59,
              }}
            />

            {/* Sheet */}
            <motion.div
              key="expanded-sheet"
              data-gesture-ignore="true"
              initial={{ y: '100%' }}
              animate={{ y: 0 }}
              exit={{ y: '100%' }}
              transition={{ type: 'spring', damping: 30, stiffness: 280, mass: 0.8 }}
              drag="y"
              dragConstraints={{ top: 0, bottom: 0 }}
              dragElastic={{ top: 0, bottom: 0.4 }}
              onDragEnd={handleExpandedDragEnd}
              onPointerDown={resetCollapseTimer}
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
              {/* Ambient personality wash */}
              <div style={{
                position: 'absolute',
                top: 0, left: 0, right: 0,
                height: 120,
                background: 'radial-gradient(ellipse at 50% -20%, rgba(var(--personality-accent-rgb), 0.1) 0%, transparent 70%)',
                pointerEvents: 'none',
              }} />

              {/* Drag handle */}
              <div style={{ display: 'flex', justifyContent: 'center', paddingBottom: 2 }}>
                <motion.div
                  animate={{ opacity: [0.2, 0.4, 0.2] }}
                  transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
                  style={{ width: 40, height: 4, borderRadius: 2, background: 'rgba(var(--personality-accent-rgb), 0.4)' }}
                />
              </div>

              {/* Video area — YT Player container (visible in expanded mode) */}
              {videoId && (
                <div
                  onClick={(e) => {
                    e.stopPropagation()
                    setMode('fullscreen')
                  }}
                  style={{
                    width: '100%',
                    aspectRatio: '16 / 9',
                    borderRadius: 16,
                    overflow: 'hidden',
                    position: 'relative',
                    cursor: 'pointer',
                    flexShrink: 0,
                    background: '#0a0a0a',
                  }}
                >
                  <div
                    ref={containerRef}
                    style={{
                      width: '100%',
                      height: '100%',
                      pointerEvents: 'none',
                    }}
                  />
                  {/* Fullscreen hint overlay */}
                  <div style={{
                    position: 'absolute',
                    inset: 0,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    background: 'rgba(0,0,0,0.15)',
                    opacity: 0.7,
                    pointerEvents: 'none',
                  }}>
                    <svg width="32" height="32" viewBox="0 0 24 24" fill="white" opacity={0.7}>
                      <path d="M4 4h4V2H2v6h2V4zm16 0v4h2V2h-6v2h4zM4 20v-4H2v6h6v-2H4zm16 0h-4v2h6v-6h-2v4z" />
                    </svg>
                  </div>
                </div>
              )}

              {/* Art + info */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 16, position: 'relative' }}>
                {nowPlaying.artUrl
                  ? <div style={{ position: 'relative', flexShrink: 0 }}>
                      <div style={{
                        position: 'absolute', inset: -8, borderRadius: 18,
                        background: 'rgba(var(--personality-accent-rgb), 0.12)', filter: 'blur(16px)',
                      }} />
                      <img
                        src={nowPlaying.artUrl}
                        alt=""
                        style={{
                          width: 72, height: 72, borderRadius: 14, objectFit: 'cover',
                          position: 'relative', boxShadow: '0 4px 16px rgba(0, 0, 0, 0.4)',
                        }}
                      />
                    </div>
                  : videoId
                    ? <div style={{ position: 'relative', flexShrink: 0 }}>
                        <div style={{
                          position: 'absolute', inset: -8, borderRadius: 18,
                          background: 'rgba(var(--personality-accent-rgb), 0.12)', filter: 'blur(16px)',
                        }} />
                        <img
                          src={`https://img.youtube.com/vi/${videoId}/mqdefault.jpg`}
                          alt=""
                          style={{
                            width: 72, height: 72, borderRadius: 14, objectFit: 'cover',
                            position: 'relative', boxShadow: '0 4px 16px rgba(0, 0, 0, 0.4)',
                          }}
                        />
                      </div>
                    : <div style={{
                        width: 72, height: 72, borderRadius: 14,
                        background: 'rgba(var(--personality-accent-rgb), 0.08)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: '1.8rem', color: 'var(--personality-accent)', flexShrink: 0,
                      }}>
                        &#9835;
                      </div>
                }
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div style={{
                    fontSize: '1.05rem', fontWeight: 600, color: 'var(--text-primary)',
                    whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', letterSpacing: '0.01em',
                  }}>
                    {nowPlaying.title}
                  </div>
                  <div style={{
                    fontSize: '0.82rem', color: 'var(--personality-accent)', opacity: 0.85,
                    marginTop: 3, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', fontWeight: 500,
                  }}>
                    {nowPlaying.artist}
                  </div>
                  {nowPlaying.album && (
                    <div style={{
                      fontSize: '0.7rem', color: 'var(--text-tertiary)', marginTop: 2,
                      whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                    }}>
                      {nowPlaying.album}
                    </div>
                  )}
                </div>
              </div>

              {/* Progress bar */}
              {localDuration > 0 && (
                <div>
                  <div
                    ref={barRef}
                    onPointerDown={handleSeekPointerDown}
                    role="slider"
                    aria-label="Seek"
                    aria-valuenow={displayPosition}
                    aria-valuemax={localDuration}
                    style={{
                      width: '100%', height: 14, borderRadius: 9999,
                      background: 'rgba(255, 255, 255, 0.06)', cursor: 'pointer',
                      position: 'relative', display: 'flex', alignItems: 'center', touchAction: 'none',
                    }}
                  >
                    <motion.div
                      style={{
                        height: 4, borderRadius: 9999,
                        background: `linear-gradient(90deg, rgba(var(--personality-accent-rgb), 0.6), var(--personality-accent))`,
                        width: `${pct}%`, position: 'absolute', top: '50%', left: 0, transform: 'translateY(-50%)',
                      }}
                      transition={{ duration: 0.5 }}
                    />
                    <motion.div
                      style={{
                        position: 'absolute', top: '50%', left: `${pct}%`,
                        width: 14, height: 14, borderRadius: '50%',
                        background: 'var(--personality-accent)', transform: 'translate(-50%, -50%)',
                        boxShadow: '0 0 12px rgba(var(--personality-accent-rgb), 0.4)',
                      }}
                    />
                  </div>
                  <div style={{
                    display: 'flex', justifyContent: 'space-between', marginTop: 6,
                    fontSize: '0.6rem', color: 'var(--text-tertiary)',
                    fontFamily: 'var(--font-mono)', letterSpacing: '0.04em',
                  }}>
                    <span>{fmt(displayPosition)}</span>
                    <span>{fmt(localDuration)}</span>
                  </div>
                </div>
              )}

              {/* Playback controls */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 20 }}>
                <ControlBtn onClick={() => { handleStop(); resetCollapseTimer() }} label="Stop">
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor">
                    <rect x="2" y="2" width="10" height="10" rx="2" />
                  </svg>
                </ControlBtn>

                <ControlBtn
                  onClick={() => { handlePlayPause(); resetCollapseTimer() }}
                  label={localPaused ? 'Play' : 'Pause'}
                  primary
                  size={56}
                >
                  {localPaused
                    ? <svg width="20" height="20" viewBox="0 0 18 18" fill="currentColor"><path d="M4 2l13 7-13 7V2z" /></svg>
                    : <svg width="18" height="18" viewBox="0 0 16 16" fill="currentColor"><rect x="2.5" y="1" width="4" height="14" rx="1.5" /><rect x="9.5" y="1" width="4" height="14" rx="1.5" /></svg>
                  }
                </ControlBtn>

                <ControlBtn onClick={() => { actions.skip(); resetCollapseTimer() }} label="Skip">
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
                  onChange={e => { debouncedSetVolume(Number(e.target.value)); resetCollapseTimer() }}
                  aria-label="Volume"
                  style={{ flex: 1, accentColor: 'var(--personality-accent)', cursor: 'pointer', height: 4 }}
                />
                <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor" style={{ color: 'var(--text-tertiary)', flexShrink: 0 }}>
                  <path d="M2 5h2.5L8 2v10L4.5 9H2a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1z" />
                  <path d="M10 4.5a3.5 3.5 0 0 1 0 5M12 3a5.5 5.5 0 0 1 0 8" stroke="currentColor" strokeWidth={1.2} fill="none" strokeLinecap="round" />
                </svg>
              </div>

              {/* Close button */}
              <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 4 }}>
                <motion.button
                  whileTap={{ scale: 0.9 }}
                  onClick={handleStop}
                  style={{
                    background: 'rgba(255,255,255,0.04)',
                    border: 'none',
                    borderRadius: 12,
                    padding: '6px 20px',
                    cursor: 'pointer',
                    fontSize: '0.7rem',
                    color: 'var(--text-tertiary)',
                    fontWeight: 500,
                    letterSpacing: '0.04em',
                  }}
                >
                  Close
                </motion.button>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {/* ── FULLSCREEN MODE ── edge-to-edge video with overlay controls */}
      <AnimatePresence>
        {mode === 'fullscreen' && (
          <motion.div
            key="fullscreen"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={{ type: 'spring', damping: 25, stiffness: 280 }}
            style={{
              position: 'fixed',
              inset: 0,
              zIndex: 102,
              background: '#0a0a0a',
              overflow: 'hidden',
            }}
          >
            {/* YT Player container — visible fullscreen */}
            <div
              ref={containerRef}
              style={{
                width: '100%',
                height: '100%',
                pointerEvents: 'none',
              }}
            />

            {/* VideoControls overlay */}
            <VideoControls
              title={nowPlaying.title}
              artist={nowPlaying.artist}
              paused={localPaused}
              duration={localDuration}
              position={displayPosition}
              isFullscreen={true}
              onPlayPause={handlePlayPause}
              onSeek={handleSeek}
              onClose={handleStop}
              onMinimize={() => setMode('expanded')}
              onToggleFullscreen={handleToggleFullscreen}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
