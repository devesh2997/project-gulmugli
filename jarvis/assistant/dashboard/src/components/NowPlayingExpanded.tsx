/**
 * NowPlayingExpanded — floating overlay with full playback controls.
 *
 * Shares layoutId="now-playing" with NowPlayingPill for morph animation.
 * Auto-collapses after 5 seconds of no interaction.
 */

import { useCallback, useEffect, useRef } from 'react'
import { motion } from 'framer-motion'
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

function Btn({ onClick, label, active = false, size = 36, accent, children }: {
  onClick: () => void; label: string; active?: boolean; size?: number; accent: string; children: React.ReactNode
}) {
  return (
    <motion.button whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.95 }} onClick={onClick} aria-label={label} style={{
      width: size, height: size, borderRadius: '50%', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
      background: active ? `${accent}22` : 'var(--bg-elevated)',
      border: `1px solid ${active ? `${accent}40` : 'var(--border-subtle)'}`,
      color: active ? accent : 'var(--text-secondary)',
    }}>
      {children}
    </motion.button>
  )
}

export function NowPlayingExpanded({ nowPlaying, actions, onCollapse }: NowPlayingExpandedProps) {
  const barRef = useRef<HTMLDivElement>(null)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const accent = 'var(--personality-accent, var(--accent-primary))'

  const reset = useCallback(() => {
    if (timer.current) clearTimeout(timer.current)
    timer.current = setTimeout(onCollapse, 5000)
  }, [onCollapse])

  useEffect(() => { reset(); return () => { if (timer.current) clearTimeout(timer.current) } }, [reset])

  const seek = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!nowPlaying.duration || !barRef.current) return
    const r = barRef.current.getBoundingClientRect()
    actions.seek(Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)) * nowPlaying.duration)
    reset()
  }

  const pct = nowPlaying.duration > 0 ? (nowPlaying.position / nowPlaying.duration) * 100 : 0

  return (
    <motion.div layoutId="now-playing" initial={{ opacity: 0, scale: 0.92 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.92 }} transition={{ duration: 0.3 }}
      style={{ position: 'fixed', top: '50%', left: '50%', translateX: '-50%', translateY: '-50%', zIndex: 60, width: 320, padding: 24, borderRadius: 'var(--radius-xl)', background: 'rgba(14,14,14,0.92)', backdropFilter: 'blur(24px)', WebkitBackdropFilter: 'blur(24px)', display: 'flex', flexDirection: 'column', gap: 16 }}>

      {/* Close */}
      <button onClick={onCollapse} aria-label="Collapse" style={{ position: 'absolute', top: 12, right: 12, background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', fontSize: '1.1rem', lineHeight: 1, padding: 4 }}>×</button>

      {/* Art + info */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
        {nowPlaying.artUrl
          ? <img src={nowPlaying.artUrl} alt="" style={{ width: 64, height: 64, borderRadius: 8, objectFit: 'cover', flexShrink: 0 }} />
          : <div style={{ width: 64, height: 64, borderRadius: 8, background: 'rgba(255,255,255,0.06)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.6rem', flexShrink: 0 }}>♫</div>
        }
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{nowPlaying.title}</div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: 2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{nowPlaying.artist}</div>
          {nowPlaying.album && <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: 2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{nowPlaying.album}</div>}
        </div>
      </div>

      {/* Progress */}
      {nowPlaying.duration > 0 && (
        <div>
          <div ref={barRef} onClick={seek} role="slider" aria-label="Seek" aria-valuenow={nowPlaying.position} aria-valuemax={nowPlaying.duration}
            style={{ width: '100%', height: 4, borderRadius: 'var(--radius-full)', background: 'var(--border-default)', cursor: 'pointer' }}>
            <motion.div style={{ height: '100%', borderRadius: 'var(--radius-full)', background: accent, width: `${pct}%` }} transition={{ duration: 0.5 }} />
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4, fontSize: '0.62rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
            <span>{fmt(nowPlaying.position)}</span><span>{fmt(nowPlaying.duration)}</span>
          </div>
        </div>
      )}

      {/* Controls */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 12 }}>
        <Btn onClick={() => { actions.stop(); reset() }} label="Stop" accent={accent}>
          <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor"><rect x="1" y="1" width="10" height="10" rx="1"/></svg>
        </Btn>
        <Btn onClick={() => { nowPlaying.paused ? actions.resume() : actions.pause(); reset() }} label={nowPlaying.paused ? 'Play' : 'Pause'} active size={46} accent={accent}>
          {nowPlaying.paused
            ? <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M3 2l12 6-12 6V2z"/></svg>
            : <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor"><rect x="2" y="1" width="3.5" height="12" rx="1"/><rect x="8.5" y="1" width="3.5" height="12" rx="1"/></svg>
          }
        </Btn>
        <Btn onClick={() => { actions.skip(); reset() }} label="Skip" accent={accent}>
          <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor"><path d="M2 2l7 5-7 5V2z"/><rect x="10" y="2" width="2" height="10" rx=".5"/></svg>
        </Btn>
      </div>

      {/* Volume */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor" style={{ color: 'var(--text-muted)', flexShrink: 0 }}>
          <path d="M1 4h2.5L6.5 1.5v9L3.5 8H1V4z"/>
        </svg>
        <input type="range" min={0} max={100} defaultValue={50} onChange={e => { actions.setVolume(Number(e.target.value)); reset() }}
          aria-label="Volume" style={{ flex: 1, accentColor: accent, cursor: 'pointer', height: 4 }} />
      </div>
    </motion.div>
  )
}
