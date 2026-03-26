/**
 * JARVIS Dashboard — layered full-screen composition.
 *
 * Single responsive layout built from stacked layers:
 *   Layer 1: Canvas (time-of-day gradient background)
 *   Layer 2: Avatar + Clock + PillCluster (center column)
 *   Layer 3: StatusDot (top-right), NowPlaying (bottom-center)
 *   Layer 4: SlidePanel overlays (transcript, settings, lights)
 *
 * The entire UI is optional — the assistant works without it.
 */

import { useCallback, useEffect, useState } from 'react'
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
  const assistant = useAssistant('ws://localhost:8765', updateToken)

  useTimeOfDay()

  // ── Panel state (slide panels) ──
  const [openPanel, setOpenPanel] = useState<PanelId>(null)

  useGesture((direction) => {
    if (openPanel) {
      if (direction === 'down') setOpenPanel(null)
    } else {
      if (direction === 'up') setOpenPanel('transcript')
      if (direction === 'left') setOpenPanel('settings')
      if (direction === 'right') setOpenPanel('lights')
    }
  })

  // ── Now-playing expanded/collapsed ──
  const [nowPlayingExpanded, setNowPlayingExpanded] = useState(false)

  // ── Fullscreen toggle (F11 / Cmd+F) ──
  const toggleFullscreen = useCallback(() => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen?.()
    } else {
      document.exitFullscreen?.()
    }
  }, [])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'F11' || (e.key === 'f' && e.metaKey)) {
        e.preventDefault()
        toggleFullscreen()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [toggleFullscreen])

  // ── Avatar size: responsive clamp ──
  const avatarSize = Math.max(120, Math.min(window.innerWidth * 0.2, 260))

  return (
    <div className="fixed inset-0 overflow-hidden">
      <Canvas />

      {/* Center column: avatar + pills + clock */}
      <div className="absolute inset-0 flex flex-col items-center justify-center z-10">
        <TransitionDissolver personality={assistant.personality}>
          <Avatar size={avatarSize} state={assistant.state} mood={assistant.mood} />
        </TransitionDissolver>

        <PillCluster intents={assistant.intents} />

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
