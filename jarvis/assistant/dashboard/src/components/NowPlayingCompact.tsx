/**
 * NowPlayingCompact -- floating glass card at bottom center with waveform + marquee.
 *
 * Features:
 *   - Frosted glass card (no border pill)
 *   - Animated waveform bars on the left in personality accent colour
 *   - Marquee scrolling for long song titles
 *   - Artist name in smaller text below title
 *   - Subtle personality accent glow
 *   - Tappable to expand (already wired)
 *   - Draggable via framer-motion drag prop
 *
 * Shares layoutId="now-playing" with NowPlayingExpanded for morph.
 */

import { useRef, useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import type { NowPlaying } from '../types/assistant'

interface NowPlayingCompactProps {
  nowPlaying: NowPlaying
  onExpand: () => void
}

/** Animated waveform bars using personality accent. */
function Waveform({ paused }: { paused: boolean }) {
  const barHeights = [
    [6, 14, 8, 12, 6],
    [10, 5, 13, 7, 10],
    [8, 12, 5, 14, 8],
    [12, 7, 11, 5, 12],
  ]

  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 1.5, height: 16, flexShrink: 0 }}>
      {barHeights.map((heights, i) => (
        <motion.div
          key={i}
          style={{
            width: 2,
            borderRadius: 1,
            background: 'var(--personality-accent)',
          }}
          animate={paused
            ? { height: 4, opacity: 0.4 }
            : { height: heights, opacity: [0.5, 0.85, 0.6, 0.8, 0.5] }
          }
          transition={paused
            ? { duration: 0.3 }
            : { duration: 1, repeat: Infinity, delay: i * 0.12, ease: 'easeInOut' }
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

export function NowPlayingCompact({ nowPlaying, onExpand }: NowPlayingCompactProps) {
  const constraintsRef = useRef<HTMLDivElement>(null)

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
        initial={{ y: 20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        exit={{ y: 20, opacity: 0 }}
        transition={{ duration: 0.3 }}
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
          padding: '8px 16px 8px 12px',
          borderRadius: 16,
          background: 'rgba(18, 18, 18, 0.65)',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          border: '1px solid rgba(255, 255, 255, 0.06)',
          boxShadow: '0 4px 24px rgba(0, 0, 0, 0.3), 0 0 16px rgba(var(--personality-accent-rgb), 0.08)',
          cursor: 'pointer',
          userSelect: 'none',
          maxWidth: 280,
          minWidth: 180,
        }}
      >
        {/* Waveform */}
        <Waveform paused={nowPlaying.paused} />

        {/* Song info */}
        <div style={{ minWidth: 0, flex: 1, display: 'flex', flexDirection: 'column', gap: 1 }}>
          <MarqueeText
            text={nowPlaying.title}
            style={{
              fontSize: '0.75rem',
              fontWeight: 600,
              color: 'rgba(255, 255, 255, 0.9)',
              maxWidth: 180,
            }}
          />
          {nowPlaying.artist && (
            <div style={{
              fontSize: '0.62rem',
              color: 'var(--personality-accent)',
              opacity: 0.7,
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              maxWidth: 180,
            }}>
              {nowPlaying.artist}
            </div>
          )}
        </div>

        {/* Subtle accent glow overlay */}
        <div style={{
          position: 'absolute',
          inset: 0,
          borderRadius: 16,
          background: 'radial-gradient(ellipse at 20% 50%, rgba(var(--personality-accent-rgb), 0.06) 0%, transparent 70%)',
          pointerEvents: 'none',
        }} />
      </motion.div>
    </>
  )
}
