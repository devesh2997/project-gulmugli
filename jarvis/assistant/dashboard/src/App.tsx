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
import { PillCluster } from './components/PillCluster'
import { NowPlayingPill } from './components/NowPlayingPill'
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

  // ── Avatar size: responsive clamp ──
  const avatarSize = Math.max(120, Math.min(window.innerWidth * 0.2, 260))

  return (
    <div className="fixed inset-0 overflow-hidden">
      <Canvas />

      {/* Center column: avatar + pills + clock */}
      <div className="absolute inset-0 flex flex-col items-center justify-center z-10">
        {/* Pills emerge above the avatar */}
        <div style={{ position: 'relative', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <div style={{ position: 'absolute', bottom: '100%', marginBottom: 8 }}>
            <PillCluster intents={assistant.intents} />
          </div>
          <TransitionDissolver personality={assistant.personality}>
            <Avatar size={avatarSize} state={assistant.state} mood={assistant.mood} />
          </TransitionDissolver>
        </div>

        <Clock />
      </div>

      <StatusDot connected={assistant.connected} />

      {/* Now Playing */}
      <AnimatePresence>
        {assistant.nowPlaying && !nowPlayingExpanded && (
          <NowPlayingPill
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
        <SettingsPanel />
      </SlidePanel>
      <SlidePanel isOpen={openPanel === 'lights'} onClose={() => setOpenPanel(null)} direction="right">
        <LightsPanel />
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
