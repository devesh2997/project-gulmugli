/**
 * JARVIS Dashboard -- layered full-screen composition.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
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
import { ControlsPanel } from './components/ControlsPanel'
import { EdgeHints } from './components/EdgeHints'
import { VideoPlayer } from './components/VideoPlayer'
import type { VideoMode } from './components/VideoPlayer'

type PanelId = 'transcript' | 'settings' | 'controls' | null

function AppContent() {
  const { updateToken, setPersonality, currentPersonality } = useTokens()

  // Stable ref for updateToken to avoid re-creating useAssistant
  const updateTokenRef = useRef(updateToken)
  updateTokenRef.current = updateToken
  const stableUpdateToken = useCallback((path: string, value: any) => {
    updateTokenRef.current(path, value)
  }, [])

  const assistant = useAssistant('ws://localhost:8765', stableUpdateToken)

  // Sync personality from backend -> TokenProvider on connect/change
  useEffect(() => {
    if (assistant.personality && assistant.personality !== currentPersonality) {
      setPersonality(assistant.personality)
    }
  }, [assistant.personality, currentPersonality, setPersonality])

  useTimeOfDay()

  // -- Panel state --
  const [openPanel, setOpenPanel] = useState<PanelId>(null)

  // Stable gesture callback
  const openPanelRef = useRef(openPanel)
  openPanelRef.current = openPanel
  const handleGesture = useCallback((direction: 'up' | 'down' | 'left' | 'right') => {
    if (openPanelRef.current) {
      if (direction === 'down') setOpenPanel(null)
    } else {
      if (direction === 'up') setOpenPanel('transcript')
      if (direction === 'left') setOpenPanel('controls')
      if (direction === 'right') setOpenPanel('settings')
    }
  }, [])

  useGesture(handleGesture)

  // -- Now-playing expanded/collapsed --
  const [nowPlayingExpanded, setNowPlayingExpanded] = useState(false)

  // -- Video player mode (managed here so NowPlayingCompact can drive it) --
  const [videoMode, setVideoMode] = useState<VideoMode>('full')

  const hasVideo = !!assistant.nowPlaying?.videoId

  // When a new videoId arrives, auto-show in full mode
  const prevVideoIdRef = useRef<string | null>(null)
  useEffect(() => {
    const currentVideoId = assistant.nowPlaying?.videoId ?? null
    if (currentVideoId && currentVideoId !== prevVideoIdRef.current) {
      setVideoMode('full')
    }
    prevVideoIdRef.current = currentVideoId
  }, [assistant.nowPlaying?.videoId])

  // Handle NowPlayingCompact tap: if video is active, expand video; otherwise expand audio
  const handleCompactExpand = useCallback(() => {
    if (hasVideo) {
      setVideoMode('full')
    } else {
      setNowPlayingExpanded(true)
    }
  }, [hasVideo])

  // Handle video mode changes from VideoPlayer
  const handleVideoModeChange = useCallback((mode: VideoMode) => {
    setVideoMode(mode)
  }, [])

  // -- Fullscreen toggle (F11 / Cmd+F) --
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

  // -- Avatar size: responsive to viewport, generous for 5.5" screens --
  const vh = typeof window !== 'undefined' ? window.innerHeight : 540
  const vw = typeof window !== 'undefined' ? window.innerWidth : 960
  const smallerDim = Math.min(vh, vw)
  const avatarSize = Math.max(120, Math.min(smallerDim * 0.3, 280))

  // -- Track avatar center for thought orbit positions --
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

  // Determine whether to show NowPlayingCompact: show when music is playing AND
  // video is not in full mode (mini/hidden video still shows compact widget)
  const showCompact = !!assistant.nowPlaying && !nowPlayingExpanded && videoMode !== 'full'
  // NowPlayingExpanded (audio sheet): only when no video is active
  const showExpanded = !!assistant.nowPlaying && nowPlayingExpanded && !hasVideo

  return (
    <div className="fixed inset-0 overflow-hidden">
      <Canvas />

      {/* Sleep mode dim wrapper */}
      <motion.div
        animate={{ opacity: assistant.sleepMode ? 0.2 : 1 }}
        transition={{
          duration: assistant.sleepMode ? 1.5 : 1,
          ease: assistant.sleepMode ? 'easeInOut' : 'easeOut',
        }}
        style={{ position: 'absolute', inset: 0 }}
      >
        {/* Center column: avatar -> clock */}
        <div className="absolute inset-0 flex flex-col items-center justify-center z-10" style={{ gap: 0 }}>
          <div
            ref={avatarRef}
            onClick={() => assistant.actions.sendText('__wake__')}
            style={{
              width: avatarSize, height: avatarSize,
              position: 'relative', overflow: 'visible', flexShrink: 0,
              cursor: 'pointer',
            }}
          >
            <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)' }}>
              <TransitionDissolver personality={assistant.personality}>
                <Avatar size={avatarSize} state={assistant.state} mood={assistant.mood} />
              </TransitionDissolver>
            </div>
          </div>

          <div style={{ paddingTop: Math.max(32, avatarSize * 0.35) }}>
            <Clock />
          </div>
        </div>

        {/* Thought manifestations */}
        <ThoughtManifest
          intents={assistant.intents}
          avatarCenter={avatarCenter}
          avatarSize={avatarSize}
        />

        <StatusDot connected={assistant.connected} />

        <EdgeHints visible={openPanel === null} />

        {/* Now Playing: compact widget + audio expanded sheet */}
        <AnimatePresence>
          {showCompact && (
            <NowPlayingCompact
              nowPlaying={assistant.nowPlaying!}
              onExpand={handleCompactExpand}
              hasVideo={hasVideo}
            />
          )}
          {showExpanded && (
            <NowPlayingExpanded
              nowPlaying={assistant.nowPlaying!}
              actions={assistant.actions}
              onCollapse={() => setNowPlayingExpanded(false)}
            />
          )}
        </AnimatePresence>

        {/* Slide Panels */}
        <SlidePanel isOpen={openPanel === 'transcript'} onClose={() => setOpenPanel(null)} direction="bottom">
          <Transcript messages={assistant.transcript} onSendText={assistant.actions.sendText} />
        </SlidePanel>
        <SlidePanel isOpen={openPanel === 'controls'} onClose={() => setOpenPanel(null)} direction="left">
          <ControlsPanel store={assistant} />
        </SlidePanel>
        <SlidePanel isOpen={openPanel === 'settings'} onClose={() => setOpenPanel(null)} direction="right">
          <SettingsPanel store={assistant} />
        </SlidePanel>
      </motion.div>

      {/* Floating video player -- always mounted when videoId exists, mode controls visibility */}
      {hasVideo && assistant.nowPlaying && (
        <VideoPlayer
          nowPlaying={assistant.nowPlaying}
          actions={assistant.actions}
          mode={videoMode}
          onModeChange={handleVideoModeChange}
        />
      )}

      {/* Sleep mode tap-to-wake overlay */}
      <AnimatePresence>
        {assistant.sleepMode && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
            onClick={() => assistant.actions.wake()}
            style={{
              position: 'absolute',
              inset: 0,
              zIndex: 50,
              cursor: 'pointer',
            }}
          />
        )}
      </AnimatePresence>
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
