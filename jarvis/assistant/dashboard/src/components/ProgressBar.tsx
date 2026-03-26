/**
 * Seekable progress bar for audio playback.
 *
 * Click or drag to seek. Shows mm:ss time labels.
 */

import { useRef } from 'react'

interface ProgressBarProps {
  current: number   // seconds
  total: number     // seconds
  onSeek?: (position: number) => void
}

function fmt(s: number): string {
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return `${m}:${sec.toString().padStart(2, '0')}`
}

export default function ProgressBar({ current, total, onSeek }: ProgressBarProps) {
  const barRef = useRef<HTMLDivElement>(null)
  const fraction = total > 0 ? Math.min(current / total, 1) : 0

  const seekFromEvent = (clientX: number) => {
    if (!onSeek || !barRef.current) return
    const rect = barRef.current.getBoundingClientRect()
    const pos = Math.max(0, Math.min((clientX - rect.left) / rect.width, 1))
    onSeek(pos * total)
  }

  const onMouseDown = (e: React.MouseEvent) => {
    seekFromEvent(e.clientX)
    const onMove = (ev: MouseEvent) => seekFromEvent(ev.clientX)
    const onUp = () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }

  const onTouchStart = (e: React.TouchEvent) => {
    seekFromEvent(e.touches[0].clientX)
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.45)', minWidth: 32, textAlign: 'right' }}>
        {fmt(current)}
      </span>

      <div
        ref={barRef}
        onMouseDown={onMouseDown}
        onTouchStart={onTouchStart}
        style={{
          flex: 1, height: 3, borderRadius: 2,
          background: 'rgba(255,255,255,0.08)',
          cursor: onSeek ? 'pointer' : 'default',
          position: 'relative',
        }}
      >
        <div
          style={{
            position: 'absolute', top: 0, left: 0,
            height: '100%', borderRadius: 2,
            width: `${fraction * 100}%`,
            background: 'var(--personality-accent)',
            opacity: 0.6,
            transition: 'width 0.5s linear',
          }}
        />
      </div>

      <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.3)', minWidth: 32 }}>
        {fmt(total)}
      </span>
    </div>
  )
}
