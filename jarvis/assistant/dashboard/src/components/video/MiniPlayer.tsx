/**
 * MiniPlayer -- PiP floating video thumbnail in the corner.
 *
 * 180x101px (16:9), draggable, snaps to nearest corner on release.
 * Tap to expand back to full player, swipe off any edge to dismiss.
 * Subtle personality-accent border pulse while playing.
 * Uses CSS transform scale to shrink the YouTube iframe.
 */

import { useCallback, useRef, useState } from 'react'
import { motion, PanInfo, useMotionValue, useTransform } from 'framer-motion'

interface MiniPlayerProps {
  videoId: string
  title: string
  paused: boolean
  onExpand: () => void
  onDismiss: () => void
}

const MINI_W = 180
const MINI_H = 101
const EDGE_MARGIN = 16

// The iframe is rendered at a larger size and scaled down for quality
const IFRAME_W = 640
const IFRAME_H = 360
const SCALE = MINI_W / IFRAME_W

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

export function MiniPlayer({ videoId, title, paused, onExpand, onDismiss }: MiniPlayerProps) {
  const [corner, setCorner] = useState<Corner>('bottom-right')
  const [hovered, setHovered] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  const pos = getCornerPosition(corner)

  const x = useMotionValue(0)
  const y = useMotionValue(0)
  const opacity = useTransform(
    [x, y],
    ([latestX, latestY]: number[]) => {
      const absX = Math.abs(latestX)
      const absY = Math.abs(latestY)
      const maxDist = Math.max(absX, absY)
      return maxDist > 80 ? Math.max(0.3, 1 - (maxDist - 80) / 120) : 1
    }
  )

  const handleDragEnd = useCallback((_: MouseEvent | TouchEvent | PointerEvent, info: PanInfo) => {
    const absX = Math.abs(info.offset.x)
    const absY = Math.abs(info.offset.y)

    // Swipe off edge to dismiss
    if (absX > 120 || absY > 120) {
      onDismiss()
      return
    }

    // Snap to nearest corner
    const currentPos = getCornerPosition(corner)
    const newX = currentPos.x + info.offset.x
    const newY = currentPos.y + info.offset.y
    const nearest = findNearestCorner(newX, newY)
    setCorner(nearest)
  }, [corner, onDismiss])

  return (
    <motion.div
      ref={containerRef}
      initial={{ scale: 0.5, opacity: 0 }}
      animate={{
        x: pos.x,
        y: pos.y,
        scale: 1,
        opacity: 1,
      }}
      exit={{ scale: 0.3, opacity: 0 }}
      transition={{ type: 'spring', damping: 25, stiffness: 300, mass: 0.8 }}
      drag
      dragMomentum={false}
      style={{
        x,
        y,
        opacity,
        position: 'fixed',
        top: 0,
        left: 0,
        width: MINI_W,
        height: MINI_H,
        borderRadius: 14,
        overflow: 'hidden',
        cursor: 'pointer',
        zIndex: 101,
        boxShadow: '0 8px 32px rgba(0,0,0,0.6), 0 0 20px rgba(var(--personality-accent-rgb), 0.08)',
      }}
      onDragEnd={handleDragEnd}
      onHoverStart={() => setHovered(true)}
      onHoverEnd={() => setHovered(false)}
      onClick={onExpand}
    >
      {/* Playing border pulse animation */}
      {!paused && (
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

      {/* Scaled-down iframe container */}
      <div style={{
        width: IFRAME_W,
        height: IFRAME_H,
        transform: `scale(${SCALE})`,
        transformOrigin: 'top left',
        pointerEvents: 'none',
      }}>
        <iframe
          src={`https://www.youtube.com/embed/${videoId}?autoplay=1&controls=0&modestbranding=1&rel=0&showinfo=0&mute=1&enablejsapi=1`}
          allow="autoplay; encrypted-media"
          style={{
            width: '100%',
            height: '100%',
            border: 'none',
          }}
          title="Mini video player"
        />
      </div>

      {/* Hover/tap overlay: play icon + title */}
      <motion.div
        initial={false}
        animate={{ opacity: hovered ? 1 : 0 }}
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

      {/* Title bar at bottom */}
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
          {title}
        </div>
      </div>
    </motion.div>
  )
}
