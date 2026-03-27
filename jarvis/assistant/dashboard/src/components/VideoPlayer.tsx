/**
 * VideoPlayer -- premium floating YouTube video window with a SINGLE persistent iframe.
 *
 * The iframe is mounted ONCE and never unmounted while videoId is set.
 * Mode transitions (full ↔ mini ↔ hidden) are pure CSS transforms via framer-motion,
 * so YouTube never loses playback state.
 *
 * Modes:
 *   'full'   — large floating window (~80% viewport, 16:9), draggable, with controls overlay
 *   'mini'   — PiP thumbnail in corner (same iframe, CSS-scaled), draggable, snap-to-corners
 *   'hidden' — iframe is off-screen (preserves playback), used when compact widget is shown
 *
 * Play/pause uses YouTube IFrame API postMessage — no iframe reload.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion, PanInfo, useMotionValue, useTransform } from 'framer-motion'
import { VideoControls } from './video/VideoControls'
import type { NowPlaying, AssistantActions } from '../types/assistant'

export type VideoMode = 'full' | 'mini' | 'hidden'

interface VideoPlayerProps {
  nowPlaying: NowPlaying
  actions: AssistantActions
  mode: VideoMode
  onModeChange: (mode: VideoMode) => void
  /** When set, the player opens in browse mode — full iframe navigating to this URL */
  browseUrl?: string | null
  /** Called when the user closes browse mode */
  onCloseBrowse?: () => void
}

// Mini player constants
const MINI_W = 180
const MINI_H = 101
const EDGE_MARGIN = 16

type Corner = 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right'

function getCornerPosition(corner: Corner): { x: number; y: number } {
  const vw = window.innerWidth
  const vh = window.innerHeight
  switch (corner) {
    case 'top-left':
      return { x: EDGE_MARGIN, y: EDGE_MARGIN }
    case 'top-right':
      return { x: vw - MINI_W - EDGE_MARGIN, y: EDGE_MARGIN }
    case 'bottom-left':
      return { x: EDGE_MARGIN, y: vh - MINI_H - EDGE_MARGIN }
    case 'bottom-right':
      return { x: vw - MINI_W - EDGE_MARGIN, y: vh - MINI_H - EDGE_MARGIN }
  }
}

function findNearestCorner(x: number, y: number): Corner {
  const vw = window.innerWidth
  const vh = window.innerHeight
  const cx = x + MINI_W / 2
  const cy = y + MINI_H / 2
  const isRight = cx > vw / 2
  const isBottom = cy > vh / 2
  if (isRight && isBottom) return 'bottom-right'
  if (isRight && !isBottom) return 'top-right'
  if (!isRight && isBottom) return 'bottom-left'
  return 'top-left'
}

export function VideoPlayer({ nowPlaying, actions, mode, onModeChange, browseUrl, onCloseBrowse }: VideoPlayerProps) {
  const videoId = nowPlaying.videoId
  const isBrowseMode = !!browseUrl
  const iframeRef = useRef<HTMLIFrameElement>(null)
  const [miniCorner, setMiniCorner] = useState<Corner>('bottom-right')
  const [miniHovered, setMiniHovered] = useState(false)

  // Track which videoId is loaded to avoid re-setting src unnecessarily
  const loadedVideoIdRef = useRef<string | null>(null)

  // ── YouTube postMessage controls ──
  const postCommand = useCallback((func: string) => {
    if (iframeRef.current?.contentWindow) {
      iframeRef.current.contentWindow.postMessage(
        JSON.stringify({ event: 'command', func, args: '' }),
        '*'
      )
    }
  }, [])

  const handleClose = useCallback(() => {
    if (isBrowseMode) {
      onCloseBrowse?.()
    } else {
      onModeChange('hidden')
      actions.closeVideo()
    }
  }, [actions, onModeChange, isBrowseMode, onCloseBrowse])

  const handleMinimize = useCallback(() => {
    onModeChange('mini')
  }, [onModeChange])

  const handleExpand = useCallback(() => {
    onModeChange('full')
  }, [onModeChange])

  const handlePlayPause = useCallback(() => {
    if (nowPlaying.paused) {
      postCommand('playVideo')
      actions.resume()
    } else {
      postCommand('pauseVideo')
      actions.pause()
    }
  }, [nowPlaying.paused, actions, postCommand])

  // ── Full-mode drag → minimize on swipe down ──
  const handleFullDragEnd = useCallback((_: MouseEvent | TouchEvent | PointerEvent, info: PanInfo) => {
    if (info.offset.y > 100) {
      onModeChange('mini')
    }
  }, [onModeChange])

  // ── Mini-mode drag → snap-to-corner or dismiss ──
  const miniDragX = useMotionValue(0)
  const miniDragY = useMotionValue(0)
  const miniDragOpacity = useTransform(
    [miniDragX, miniDragY],
    ([latestX, latestY]: number[]) => {
      const maxDist = Math.max(Math.abs(latestX), Math.abs(latestY))
      return maxDist > 80 ? Math.max(0.3, 1 - (maxDist - 80) / 120) : 1
    }
  )

  const handleMiniDragEnd = useCallback((_: MouseEvent | TouchEvent | PointerEvent, info: PanInfo) => {
    const absX = Math.abs(info.offset.x)
    const absY = Math.abs(info.offset.y)

    if (absX > 120 || absY > 120) {
      handleClose()
      return
    }

    const currentPos = getCornerPosition(miniCorner)
    const newX = currentPos.x + info.offset.x
    const newY = currentPos.y + info.offset.y
    setMiniCorner(findNearestCorner(newX, newY))
  }, [miniCorner, handleClose])

  // ── Compute layout for both modes ──
  const vw = typeof window !== 'undefined' ? window.innerWidth : 960
  const vh = typeof window !== 'undefined' ? window.innerHeight : 540

  // Full mode dimensions
  const fullW = Math.min(vw * 0.8, 960)
  const fullH = fullW * (9 / 16)
  const fullX = (vw - fullW) / 2
  const fullY = (vh - fullH) / 2

  // Mini mode dimensions
  const miniPos = getCornerPosition(miniCorner)

  if (!videoId && !isBrowseMode) return null

  // Determine iframe src
  let iframeSrc: string | undefined
  if (isBrowseMode) {
    // Browse mode: load the browse URL directly
    iframeSrc = browseUrl ?? undefined
  } else if (videoId && loadedVideoIdRef.current !== videoId) {
    iframeSrc = `https://www.youtube.com/embed/${videoId}?autoplay=1&controls=0&modestbranding=1&rel=0&showinfo=0&enablejsapi=1&origin=${window.location.origin}`
  }

  // Update tracking ref (only for video mode)
  if (!isBrowseMode && videoId && loadedVideoIdRef.current !== videoId) {
    loadedVideoIdRef.current = videoId
  }

  return (
    <>
      {/* Background overlay — only in full mode */}
      <AnimatePresence>
        {mode === 'full' && (
          <motion.div
            key="video-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
            onClick={handleMinimize}
            style={{
              position: 'fixed',
              inset: 0,
              background: 'rgba(0, 0, 0, 0.3)',
              zIndex: 99,
            }}
          />
        )}
      </AnimatePresence>

      {/* SINGLE iframe container — mode transitions are CSS only */}
      <motion.div
        animate={
          mode === 'full'
            ? {
                x: fullX,
                y: fullY,
                width: fullW,
                height: fullH,
                borderRadius: 24,
                opacity: 1,
                scale: 1,
              }
            : mode === 'mini'
              ? {
                  x: miniPos.x,
                  y: miniPos.y,
                  width: MINI_W,
                  height: MINI_H,
                  borderRadius: 14,
                  opacity: 1,
                  scale: 1,
                }
              : {
                  // Hidden: push off-screen to preserve iframe state
                  x: -9999,
                  y: -9999,
                  width: fullW,
                  height: fullH,
                  borderRadius: 24,
                  opacity: 0,
                  scale: 1,
                }
        }
        transition={{
          type: 'spring',
          damping: 25,
          stiffness: 280,
          mass: 0.8,
        }}
        drag={mode !== 'hidden'}
        dragMomentum={false}
        dragElastic={0.1}
        onDragEnd={mode === 'full' ? handleFullDragEnd : mode === 'mini' ? handleMiniDragEnd : undefined}
        onClick={mode === 'mini' ? handleExpand : undefined}
        onHoverStart={mode === 'mini' ? () => setMiniHovered(true) : undefined}
        onHoverEnd={mode === 'mini' ? () => setMiniHovered(false) : undefined}
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          zIndex: mode === 'hidden' ? -1 : mode === 'mini' ? 101 : 100,
          overflow: 'hidden',
          background: '#0a0a0a',
          boxShadow: mode === 'full'
            ? `0 20px 60px rgba(0, 0, 0, 0.8), 0 0 40px rgba(var(--personality-accent-rgb), 0.08), 0 0 80px rgba(0, 0, 0, 0.4)`
            : mode === 'mini'
              ? '0 8px 32px rgba(0,0,0,0.6), 0 0 20px rgba(var(--personality-accent-rgb), 0.08)'
              : 'none',
          cursor: mode === 'full' ? 'grab' : mode === 'mini' ? 'pointer' : 'default',
          pointerEvents: mode === 'hidden' ? 'none' : 'auto',
          ...(mode === 'mini' ? { x: miniDragX, y: miniDragY, opacity: miniDragOpacity } : {}),
        }}
        whileDrag={mode === 'full' ? { cursor: 'grabbing' } : undefined}
      >
        {/* Personality glow (full mode only) */}
        {mode === 'full' && (
          <div style={{
            position: 'absolute',
            inset: -4,
            borderRadius: 28,
            background: 'radial-gradient(ellipse at center, rgba(var(--personality-accent-rgb), 0.04) 0%, transparent 70%)',
            pointerEvents: 'none',
            zIndex: -1,
          }} />
        )}

        {/* THE single YouTube iframe — never unmounted while videoId exists */}
        <iframe
          ref={iframeRef}
          src={iframeSrc}
          allow="autoplay; encrypted-media"
          sandbox={isBrowseMode ? 'allow-scripts allow-same-origin allow-forms allow-popups' : undefined}
          style={{
            width: '100%',
            height: '100%',
            border: 'none',
            borderRadius: 'inherit',
            display: 'block',
            pointerEvents: mode === 'mini' ? 'none' : 'auto',
          }}
          title={isBrowseMode ? 'YouTube Browse' : 'Video player'}
        />

        {/* Controls overlay — full mode only, not in browse mode */}
        {mode === 'full' && !isBrowseMode && (
          <VideoControls
            title={nowPlaying.title}
            artist={nowPlaying.artist}
            paused={nowPlaying.paused}
            duration={nowPlaying.duration}
            position={nowPlaying.position}
            onPlayPause={handlePlayPause}
            onSeek={actions.seek}
            onClose={handleClose}
            onMinimize={handleMinimize}
          />
        )}

        {/* Browse mode: close button */}
        {isBrowseMode && mode === 'full' && (
          <motion.button
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.9 }}
            onClick={(e) => {
              e.stopPropagation()
              handleClose()
            }}
            style={{
              position: 'absolute',
              top: 12,
              right: 12,
              zIndex: 10,
              width: 36,
              height: 36,
              borderRadius: '50%',
              background: 'rgba(0, 0, 0, 0.6)',
              backdropFilter: 'blur(8px)',
              border: '1px solid rgba(255,255,255,0.1)',
              color: 'white',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
            }}
            aria-label="Close browse"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
              <path d="M4.646 4.646a.5.5 0 01.708 0L8 7.293l2.646-2.647a.5.5 0 01.708.708L8.707 8l2.647 2.646a.5.5 0 01-.708.708L8 8.707l-2.646 2.647a.5.5 0 01-.708-.708L7.293 8 4.646 5.354a.5.5 0 010-.708z" />
            </svg>
          </motion.button>
        )}

        {/* Mini mode: playing border pulse */}
        {mode === 'mini' && !nowPlaying.paused && (
          <motion.div
            animate={{
              boxShadow: [
                'inset 0 0 0 1.5px rgba(var(--personality-accent-rgb), 0.15)',
                'inset 0 0 0 1.5px rgba(var(--personality-accent-rgb), 0.35)',
                'inset 0 0 0 1.5px rgba(var(--personality-accent-rgb), 0.15)',
              ],
            }}
            transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
            style={{
              position: 'absolute',
              inset: 0,
              borderRadius: 14,
              zIndex: 3,
              pointerEvents: 'none',
            }}
          />
        )}

        {/* Mini mode: hover overlay */}
        {mode === 'mini' && (
          <motion.div
            initial={false}
            animate={{ opacity: miniHovered ? 1 : 0 }}
            transition={{ duration: 0.2 }}
            style={{
              position: 'absolute',
              inset: 0,
              background: 'rgba(0,0,0,0.4)',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              zIndex: 2,
              borderRadius: 14,
              pointerEvents: 'none',
            }}
          >
            <svg width="24" height="24" viewBox="0 0 24 24" fill="white" opacity={0.9}>
              <path d="M8 5v14l11-7z" />
            </svg>
          </motion.div>
        )}

        {/* Mini mode: title bar at bottom */}
        {mode === 'mini' && (
          <div style={{
            position: 'absolute',
            bottom: 0,
            left: 0,
            right: 0,
            padding: '12px 8px 6px',
            background: 'linear-gradient(to top, rgba(0,0,0,0.7) 0%, transparent 100%)',
            zIndex: 2,
            pointerEvents: 'none',
          }}>
            <div style={{
              fontSize: '0.58rem',
              color: 'rgba(255,255,255,0.8)',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              lineHeight: 1.2,
            }}>
              {nowPlaying.title}
            </div>
          </div>
        )}
      </motion.div>
    </>
  )
}
