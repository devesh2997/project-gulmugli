/**
 * VideoPlayer -- premium floating YouTube video window.
 *
 * Renders when nowPlaying.videoId is set. Manages three modes:
 *   'full'   — large floating window (~80% viewport, 16:9), draggable, with controls overlay
 *   'mini'   — PiP thumbnail in corner, draggable, snap-to-corners
 *   'closed' — nothing rendered
 *
 * Entry: spring scale-up from center with overshoot.
 * Exit:  spring scale-down with fade.
 * Swipe down on full player -> mini mode.
 * Tap mini player -> full mode.
 * Close/dismiss -> notifies backend.
 *
 * The YouTube iframe handles both audio and video (mpv is paused during video mode).
 * This is the "fallback" approach from the plan — simpler, reliable for v1.
 */

import { useCallback, useState } from 'react'
import { AnimatePresence, motion, PanInfo } from 'framer-motion'
import { VideoControls } from './video/VideoControls'
import { MiniPlayer } from './video/MiniPlayer'
import type { NowPlaying, AssistantActions } from '../types/assistant'

type VideoMode = 'full' | 'mini' | 'closed'

interface VideoPlayerProps {
  nowPlaying: NowPlaying
  actions: AssistantActions
}

export function VideoPlayer({ nowPlaying, actions }: VideoPlayerProps) {
  const [mode, setMode] = useState<VideoMode>('full')
  const videoId = nowPlaying.videoId

  const handleClose = useCallback(() => {
    setMode('closed')
    actions.closeVideo()
  }, [actions])

  const handleMinimize = useCallback(() => {
    setMode('mini')
  }, [])

  const handleExpand = useCallback(() => {
    setMode('full')
  }, [])

  const handlePlayPause = useCallback(() => {
    if (nowPlaying.paused) {
      actions.resume()
    } else {
      actions.pause()
    }
  }, [nowPlaying.paused, actions])

  const handleDragEnd = useCallback((_: MouseEvent | TouchEvent | PointerEvent, info: PanInfo) => {
    // Swipe down -> minimize to PiP
    if (info.offset.y > 100) {
      setMode('mini')
    }
  }, [])

  if (!videoId || mode === 'closed') return null

  // Calculate dimensions: ~80% viewport width, 16:9 aspect, centered
  const vw = typeof window !== 'undefined' ? window.innerWidth : 960
  const vh = typeof window !== 'undefined' ? window.innerHeight : 540
  const playerW = Math.min(vw * 0.8, 960)
  const playerH = playerW * (9 / 16)
  const playerX = (vw - playerW) / 2
  const playerY = (vh - playerH) / 2

  return (
    <>
      {/* Full player mode */}
      <AnimatePresence>
        {mode === 'full' && (
          <>
            {/* Background overlay — tap to dismiss */}
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

            {/* Floating video window */}
            <motion.div
              key="video-full"
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: [0.8, 1.03, 1], opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0, y: 20 }}
              transition={{
                type: 'spring',
                damping: 22,
                stiffness: 260,
                mass: 0.8,
              }}
              drag
              dragMomentum={false}
              dragElastic={0.1}
              onDragEnd={handleDragEnd}
              style={{
                position: 'fixed',
                left: playerX,
                top: playerY,
                width: playerW,
                height: playerH,
                zIndex: 100,
                borderRadius: 24,
                overflow: 'hidden',
                background: '#0a0a0a',
                boxShadow: `
                  0 20px 60px rgba(0, 0, 0, 0.8),
                  0 0 40px rgba(var(--personality-accent-rgb), 0.08),
                  0 0 80px rgba(0, 0, 0, 0.4)
                `,
                cursor: 'grab',
              }}
              whileDrag={{ cursor: 'grabbing' }}
            >
              {/* Subtle personality glow behind window */}
              <div style={{
                position: 'absolute',
                inset: -4,
                borderRadius: 28,
                background: 'radial-gradient(ellipse at center, rgba(var(--personality-accent-rgb), 0.04) 0%, transparent 70%)',
                pointerEvents: 'none',
                zIndex: -1,
              }} />

              {/* YouTube iframe */}
              <iframe
                src={`https://www.youtube.com/embed/${videoId}?autoplay=1&controls=0&modestbranding=1&rel=0&showinfo=0&enablejsapi=1`}
                allow="autoplay; encrypted-media"
                style={{
                  width: '100%',
                  height: '100%',
                  border: 'none',
                  borderRadius: 24,
                  display: 'block',
                }}
                title="Video player"
              />

              {/* Custom controls overlay */}
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
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {/* Mini player mode */}
      <AnimatePresence>
        {mode === 'mini' && (
          <MiniPlayer
            key="video-mini"
            videoId={videoId}
            title={nowPlaying.title}
            paused={nowPlaying.paused}
            onExpand={handleExpand}
            onDismiss={handleClose}
          />
        )}
      </AnimatePresence>
    </>
  )
}
