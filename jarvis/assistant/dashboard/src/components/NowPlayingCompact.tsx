/**
 * NowPlayingCompact -- floating glass card with organic waveform + marquee.
 *
 * Redesigned to feel purpose-built:
 *   - Organic waveform with sine-wave interpolation (not just fixed-height bars)
 *   - Personality accent color used as a living glow, not just a border
 *   - Glass card with warm personality tint bleeding through
 *   - Marquee scrolling for overflow text
 *   - Draggable, tappable to expand
 *
 * Shares layoutId="now-playing" with NowPlayingExpanded for morph.
 */

import { useRef, useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { useLightMode } from '../hooks/useLightMode'
import type { NowPlaying } from '../types/assistant'

interface NowPlayingCompactProps {
  nowPlaying: NowPlaying
  onExpand: () => void
  /** YouTube videoId for mini thumbnail (empty string = no video) */
  videoId?: string | null
  /** Callback when the video thumbnail is tapped — expands to full video player */
  onExpandVideo?: () => void
}

/** Organic waveform with more bars and sine-wave motion */
function Waveform({ paused, isLight }: { paused: boolean; isLight?: boolean }) {
  const barCount = 7
  const bars = Array.from({ length: barCount }, (_, i) => {
    const phase = (i / barCount) * Math.PI * 2
    return {
      heights: [
        5 + Math.sin(phase) * 5,
        5 + Math.sin(phase + 1) * 7,
        5 + Math.sin(phase + 2) * 4,
        5 + Math.sin(phase + 3) * 8,
        5 + Math.sin(phase + 4) * 5,
      ],
      delay: i * 0.08,
    }
  })

  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 1.5, height: 18, flexShrink: 0 }}>
      {bars.map((bar, i) => (
        <motion.div
          key={i}
          style={{
            width: 2,
            borderRadius: 1,
            background: isLight ? '#4a3520' : 'var(--personality-accent)',
          }}
          animate={paused
            ? { height: 3, opacity: 0.3 }
            : { height: bar.heights, opacity: [0.4, 0.9, 0.5, 0.85, 0.4] }
          }
          transition={paused
            ? { duration: 0.4, ease: 'easeOut' }
            : { duration: 0.9 + i * 0.1, repeat: Infinity, delay: bar.delay, ease: 'easeInOut' }
          }
        />
      ))}
    </div>
  )
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

export function NowPlayingCompact({ nowPlaying, onExpand, videoId, onExpandVideo }: NowPlayingCompactProps) {
  const constraintsRef = useRef<HTMLDivElement>(null)
  const isLight = useLightMode()
  const hasVideo = !!videoId

  return (
    <>
      {/* Invisible drag constraints container */}
      <div
        ref={constraintsRef}
        style={{
          position: 'fixed',
          inset: 0,
          pointerEvents: 'none',
          zIndex: 49,
        }}
      />
      <motion.div
        layoutId="now-playing"
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
        onClick={onExpand}
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
        {/* Video thumbnail (left) or waveform */}
        {hasVideo ? (
          <div
            onClick={(e) => {
              e.stopPropagation()
              onExpandVideo?.()
            }}
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
              style={{
                width: '100%',
                height: '100%',
                objectFit: 'cover',
                display: 'block',
              }}
            />
            {/* Play icon overlay */}
            <div style={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'rgba(0,0,0,0.2)',
            }}>
              <svg width="14" height="14" viewBox="0 0 14 14" fill="white" opacity={0.85}>
                <path d="M4 2l8 5-8 5V2z" />
              </svg>
            </div>
          </div>
        ) : (
          <Waveform paused={nowPlaying.paused} isLight={isLight} />
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

        {/* Living accent glow — moves and breathes */}
        <motion.div
          animate={{
            opacity: [0.04, 0.1, 0.04],
          }}
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

        {/* Progress line — thin bar at bottom filling left to right */}
        {nowPlaying.duration > 0 && (
          <div
            style={{
              position: 'absolute',
              bottom: 0,
              left: 0,
              right: 0,
              height: 3,
              borderRadius: '0 0 20px 20px',
              overflow: 'hidden',
              pointerEvents: 'none',
            }}
          >
            <motion.div
              style={{
                height: '100%',
                background: 'var(--personality-accent)',
                opacity: 0.6,
                borderRadius: 'inherit',
              }}
              animate={{ width: `${(nowPlaying.position / nowPlaying.duration) * 100}%` }}
              transition={{ duration: 1, ease: 'linear' }}
            />
          </div>
        )}
      </motion.div>
    </>
  )
}
