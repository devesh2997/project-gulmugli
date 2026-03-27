/**
 * NowPlayingCompact — compact now-playing indicator fixed at bottom center.
 * Standalone component with album art (or fallback) + song title.
 * Shares layoutId="now-playing" with NowPlayingExpanded for morph.
 */

import { motion } from 'framer-motion'
import type { NowPlaying } from '../types/assistant'

interface NowPlayingCompactProps {
  nowPlaying: NowPlaying
  onExpand: () => void
}

export function NowPlayingCompact({ nowPlaying, onExpand }: NowPlayingCompactProps) {
  return (
    <motion.div
      layoutId="now-playing"
      initial={{ y: 20, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      exit={{ y: 20, opacity: 0 }}
      transition={{ duration: 0.3 }}
      onClick={onExpand}
      style={{
        position: 'fixed',
        bottom: 24,
        left: '50%',
        translateX: '-50%',
        zIndex: 50,
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        height: 36,
        padding: '6px 12px',
        borderRadius: 16,
        background: 'rgba(255, 255, 255, 0.05)',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        backdropFilter: 'blur(8px)',
        WebkitBackdropFilter: 'blur(8px)',
        cursor: 'pointer',
        userSelect: 'none',
      }}
    >
      {nowPlaying.artUrl
        ? <img src={nowPlaying.artUrl} alt="" style={{ width: 20, height: 20, borderRadius: '50%', objectFit: 'cover', flexShrink: 0 }} />
        : <span style={{ width: 20, height: 20, borderRadius: '50%', background: 'rgba(255,255,255,0.08)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, fontSize: '0.65rem' }}>&#9835;</span>
      }
      <span style={{
        fontSize: '0.72rem',
        color: 'var(--personality-accent)',
        opacity: 0.85,
        whiteSpace: 'nowrap',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        maxWidth: 160,
      }}>
        {nowPlaying.title}
      </span>
    </motion.div>
  )
}
