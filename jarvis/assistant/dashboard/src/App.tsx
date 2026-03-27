/**
 * JARVIS Dashboard — layered full-screen composition.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { AnimatePresence } from 'framer-motion'
import { TokenProvider, useTokens } from './context/TokenProvider'
import { useAssistant } from './hooks/useAssistant'
import { useGesture } from './hooks/useGesture'
import { useTimeOfDay } from './hooks/useTimeOfDay'
import { Canvas } from './components/Canvas'
import { Avatar } from './components/Avatar'
import { Clock } from './components/Clock'
import { StatusDot } from './components/StatusDot'
import { ThoughtManifest } from './components/thoughts/ThoughtManifest'
import { NowPlayingCompact } from './components/NowPlayingCompact'
import { NowPlayingExpanded } from './components/NowPlayingExpanded'
import { TransitionDissolver } from './components/TransitionDissolver'
import SlidePanel from './components/SlidePanel'
import Transcript from './components/Transcript'
import { SettingsPanel } from './components/SettingsPanel'
import { LightsPanel } from './components/LightsPanel'

type PanelId = 'transcript' | 'settings' | 'lights' | null

function AppContent() {
  const { updateToken } = useTokens()

  // Stable ref for updateToken to avoid re-creating useAssistant
  const updateTokenRef = useRef(updateToken)
  updateTokenRef.current = updateToken
  const stableUpdateToken = useCallback((path: string, value: any) => {
    updateTokenRef.current(path, value)
  }, [])

  const assistant = useAssistant('ws://localhost:8765', stableUpdateToken)

  useTimeOfDay()

  // ── Panel state ──
  const [openPanel, setOpenPanel] = useState<PanelId>(null)

  // Stable gesture callback
  const openPanelRef = useRef(openPanel)
  openPanelRef.current = openPanel
  const handleGesture = useCallback((direction: 'up' | 'down' | 'left' | 'right') => {
    if (openPanelRef.current) {
      if (direction === 'down') setOpenPanel(null)
    } else {
      if (direction === 'up') setOpenPanel('transcript')
      if (direction === 'left') setOpenPanel('settings')
      if (direction === 'right') setOpenPanel('lights')
    }
  }, [])

  useGesture(handleGesture)

  // ── Now-playing expanded/collapsed ──
  const [nowPlayingExpanded, setNowPlayingExpanded] = useState(false)

  // ── Fullscreen toggle (F11 / Cmd+F) ──
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'F11' || (e.key === 'f' && e.metaKey)) {
        e.preventDefault()
        if (!document.fullscreenElement) {
          document.documentElement.requestFullscreen?.()
        } else {
          document.exitFullscreen?.()
        }
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  // ── Avatar size: responsive, capped so it doesn't overwhelm small screens ──
  const vh = typeof window !== 'undefined' ? window.innerHeight : 540
  const avatarSize = Math.max(80, Math.min(vh * 0.22, 200))

  // ── Track avatar center for thought orbit positions ──
  const avatarRef = useRef<HTMLDivElement>(null)
  const [avatarCenter, setAvatarCenter] = useState({ x: 0, y: 0 })

  useEffect(() => {
    const measure = () => {
      if (avatarRef.current) {
        const rect = avatarRef.current.getBoundingClientRect()
        setAvatarCenter({ x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 })
      }
    }
    measure()
    window.addEventListener('resize', measure)
    return () => window.removeEventListener('resize', measure)
  }, [avatarSize])

  return (
    <div className="fixed inset-0 overflow-hidden">
      <Canvas />

      {/* Center column: avatar → clock, stacked vertically */}
      <div className="absolute inset-0 flex flex-col items-center justify-center z-10" style={{ gap: 0 }}>
        {/* Avatar — overflow: visible so glow extends but doesn't push layout */}
        <div ref={avatarRef} style={{ width: avatarSize, height: avatarSize, position: 'relative', overflow: 'visible', flexShrink: 0 }}>
          <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)' }}>
            <TransitionDissolver personality={assistant.personality}>
              <Avatar size={avatarSize} state={assistant.state} mood={assistant.mood} />
            </TransitionDissolver>
          </div>
        </div>

        {/* Clock — below avatar with dynamic spacing to clear the glow */}
        <div style={{ paddingTop: Math.max(32, avatarSize * 0.35) }}>
          <Clock />
        </div>
      </div>

      {/* Thought manifestations — orbiting the avatar */}
      <ThoughtManifest
        intents={assistant.intents}
        avatarCenter={avatarCenter}
        avatarSize={avatarSize}
      />

      <StatusDot connected={assistant.connected} />

      {/* Now Playing */}
      <AnimatePresence>
        {assistant.nowPlaying && !nowPlayingExpanded && (
          <NowPlayingCompact
            nowPlaying={assistant.nowPlaying}
            onExpand={() => setNowPlayingExpanded(true)}
          />
        )}
        {assistant.nowPlaying && nowPlayingExpanded && (
          <NowPlayingExpanded
            nowPlaying={assistant.nowPlaying}
            actions={assistant.actions}
            onCollapse={() => setNowPlayingExpanded(false)}
          />
        )}
      </AnimatePresence>

      {/* Slide Panels */}
      <SlidePanel isOpen={openPanel === 'transcript'} onClose={() => setOpenPanel(null)} direction="bottom">
        <Transcript messages={assistant.transcript} />
      </SlidePanel>
      <SlidePanel isOpen={openPanel === 'settings'} onClose={() => setOpenPanel(null)} direction="left">
        <SettingsPanel store={assistant} />
      </SlidePanel>
      <SlidePanel isOpen={openPanel === 'lights'} onClose={() => setOpenPanel(null)} direction="right">
        <LightsPanel store={assistant} />
      </SlidePanel>
    </div>
  )
}

export function App() {
  return (
    <TokenProvider>
      <AppContent />
    </TokenProvider>
  )
}

export default App
