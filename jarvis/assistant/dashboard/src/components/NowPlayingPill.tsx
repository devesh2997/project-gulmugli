/**
 * NowPlayingPill — compact now-playing indicator fixed at bottom center.
 * Wraps Pill with album art (or fallback) + song title.
 * Shares layoutId="now-playing" with NowPlayingExpanded for morph.
 */

import { motion } from 'framer-motion'
import type { NowPlaying } from '../types/assistant'
import { Pill } from './Pill'

interface NowPlayingPillProps {
  nowPlaying: NowPlaying
  onExpand: () => void
}

export function NowPlayingPill({ nowPlaying, onExpand }: NowPlayingPillProps) {
  return (
    <motion.div layoutId="now-playing" initial={{ y: 20, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 20, opacity: 0 }} transition={{ duration: 0.3 }}
      style={{ position: 'fixed', bottom: 24, left: '50%', translateX: '-50%', zIndex: 50 }}>
      <Pill label={nowPlaying.title} onClick={onExpand}>
        {nowPlaying.artUrl
          ? <img src={nowPlaying.artUrl} alt="" style={{ width: 20, height: 20, borderRadius: '50%', objectFit: 'cover', flexShrink: 0 }} />
          : <span style={{ width: 20, height: 20, borderRadius: '50%', background: 'rgba(255,255,255,0.08)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, fontSize: '0.65rem' }}>♫</span>
        }
        <span style={{ fontSize: '0.72rem', color: 'var(--personality-accent, var(--accent-primary))', opacity: 0.85, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 160 }}>
          {nowPlaying.title}
        </span>
      </Pill>
    </motion.div>
  )
}
