/**
 * Central state management hook for the assistant.
 *
 * Connects to the assistant's WebSocket server and maintains all UI state.
 * Auto-reconnects with exponential backoff on disconnection.
 */

import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import type {
  AssistantState,
  AssistantStore,
  AssistantActions,
  AssistantMood,
  AudioState,
  IntentBadge,
  SettingSchema,
  TranscriptEntry,
  NowPlaying,
  LightsState,
  PersonalityInfo,
  ServerMessage,
  UIAction,
  QuizState,
} from '../types/assistant'

interface InternalState {
  connected: boolean
  state: AssistantState
  personality: string
  personalities: PersonalityInfo[]
  transcript: TranscriptEntry[]
  nowPlaying: NowPlaying | null
  lights: LightsState | null
  volume: number
  audio: AudioState
  intents: IntentBadge[]
  mood: AssistantMood
  settings: SettingSchema[]
  sleepMode: boolean
  quiz: QuizState
  youtubeBrowseUrl: string | null
}

const DEFAULT_STATE: InternalState = {
  connected: false,
  state: 'idle',
  personality: 'jarvis',
  personalities: [],
  transcript: [],
  nowPlaying: null,
  lights: null,
  volume: 50,
  audio: { volume: 50, outputs: [], bluetoothScanning: false, bluetoothDevices: [] },
  intents: [],
  mood: 'neutral',
  settings: [],
  sleepMode: false,
  quiz: { active: false, question: null, lastResult: null, score: { correct: 0, total: 0 }, outcomes: [], showStats: false },
  youtubeBrowseUrl: null,
}

const MAX_TRANSCRIPT = 50

export function useAssistant(wsUrl?: string, onTokenUpdate?: (path: string, value: any) => void): AssistantStore {
  const [state, setState] = useState<InternalState>(DEFAULT_STATE)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const reconnectDelay = useRef(1000)

  // Stable ref for reconnect — avoids circular useCallback deps
  const connectRef = useRef<() => void>(() => {})

  // Stable ref for onTokenUpdate — avoids recreating the WebSocket on every callback change
  const onTokenUpdateRef = useRef(onTokenUpdate)
  useEffect(() => {
    onTokenUpdateRef.current = onTokenUpdate
  }, [onTokenUpdate])

  const url = wsUrl ?? (() => {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${proto}//${window.location.host}/ws`
  })()

  const handleMessage = useCallback((msg: ServerMessage) => {
    switch (msg.type) {
      case 'state':
        setState(prev => ({ ...prev, state: msg.state }))
        break

      case 'personality':
        setState(prev => ({ ...prev, personality: msg.id }))
        break

      case 'personalities':
        setState(prev => ({ ...prev, personalities: msg.list }))
        break

      case 'transcript':
        setState(prev => ({
          ...prev,
          transcript: [
            ...prev.transcript.slice(-MAX_TRANSCRIPT),
            { role: msg.role, text: msg.text, timestamp: Date.now() },
          ],
        }))
        break

      case 'now_playing':
        setState(prev => ({
          ...prev,
          nowPlaying: msg.data ? {
            title: msg.data.title || '',
            artist: msg.data.artist || '',
            album: msg.data.album || '',
            artUrl: msg.data.art_url || null,
            duration: msg.data.duration || 0,
            position: msg.data.position || 0,
            paused: msg.paused ?? false,
            videoId: msg.data.video_id || null,
          } : null,
        }))
        break

      case 'playback_position':
        setState(prev => ({
          ...prev,
          nowPlaying: prev.nowPlaying
            ? { ...prev.nowPlaying, position: (msg as any).position, duration: (msg as any).duration }
            : null,
        }))
        break

      case 'music_stopped':
        setState(prev => ({ ...prev, nowPlaying: null }))
        break

      case 'music_paused':
        setState(prev => ({
          ...prev,
          nowPlaying: prev.nowPlaying
            ? { ...prev.nowPlaying, paused: msg.paused }
            : null,
        }))
        break

      case 'lights':
        setState(prev => ({
          ...prev,
          lights: {
            on: msg.on ?? true,
            color: msg.color || '#ffffff',
            brightness: msg.brightness ?? 100,
            scene: msg.scene || null,
          },
        }))
        break

      case 'volume':
        setState(prev => ({
          ...prev,
          volume: msg.level ?? prev.volume,
          audio: { ...prev.audio, volume: msg.level ?? prev.audio.volume },
        }))
        break

      case 'audio_outputs':
        setState(prev => ({ ...prev, audio: { ...prev.audio, outputs: msg.outputs } }))
        break

      case 'bt_scan_result':
        setState(prev => ({
          ...prev,
          audio: {
            ...prev.audio,
            bluetoothScanning: msg.scanning,
            bluetoothDevices: msg.devices,
          },
        }))
        break

      case 'bt_pair_result':
        // Mark the device as connected in our local state
        if (msg.success) {
          setState(prev => ({
            ...prev,
            audio: {
              ...prev.audio,
              bluetoothDevices: prev.audio.bluetoothDevices.map(d =>
                d.mac === msg.mac ? { ...d, paired: true, connected: true } : d
              ),
            },
          }))
        }
        break

      case 'intents':
        setState(prev => ({ ...prev, intents: msg.intents }))
        break

      case 'intent_update':
        setState(prev => ({
          ...prev,
          intents: prev.intents.map(intent =>
            intent.id === msg.id
              ? { ...intent, status: msg.status, ...(msg.detail !== undefined ? { detail: msg.detail } : {}) }
              : intent
          ),
        }))
        break

      case 'mood':
        setState(prev => ({ ...prev, mood: msg.mood }))
        break

      case 'settings':
        setState(prev => ({ ...prev, settings: msg.settings }))
        break

      case 'setting_result':
        // Could show toast notification here in the future
        break

      case 'sleep_mode':
        setState(prev => ({ ...prev, sleepMode: msg.active }))
        break

      case 'token_update':
        onTokenUpdateRef.current?.(msg.path, msg.value)
        break

      case 'quiz_show':
        setState(prev => ({
          ...prev,
          quiz: {
            ...prev.quiz,
            active: true,
            showStats: false,
            lastResult: null,
            question: {
              question: msg.data.question,
              category: msg.data.category,
              difficulty: msg.data.difficulty,
              questionNumber: msg.data.question_number,
              totalQuestions: msg.data.total_questions,
              timeLimit: msg.data.time_limit,
              options: msg.data.options,
            },
          },
        }))
        break

      case 'quiz_update':
        setState(prev => ({
          ...prev,
          quiz: {
            ...prev.quiz,
            lastResult: {
              correct: msg.state.correct,
              correctAnswer: msg.state.correct_answer,
              explanation: msg.state.explanation,
              reaction: msg.state.reaction,
            },
            score: msg.state.score,
            outcomes: [
              ...prev.quiz.outcomes,
              msg.state.correct ? 'correct' : 'wrong',
            ],
            // If we've answered all questions, show stats
            showStats: msg.state.score.total >= (prev.quiz.question?.totalQuestions ?? Infinity),
          },
        }))
        break

      case 'quiz_close':
        setState(prev => ({
          ...prev,
          quiz: { active: false, question: null, lastResult: null, score: { correct: 0, total: 0 }, outcomes: [], showStats: false },
        }))
        break

      case 'youtube_browse':
        setState(prev => ({ ...prev, youtubeBrowseUrl: msg.url }))
        break

      case 'video_control':
        // Forward to App.tsx via custom event (avoids prop drilling)
        window.dispatchEvent(new CustomEvent('jarvis-video-control', { detail: (msg as any).action }))
        break

      default:
        console.debug('[WS] Unknown message type:', msg)
    }
  }, [])

  const scheduleReconnect = useCallback(() => {
    if (reconnectTimer.current) return
    const delay = reconnectDelay.current
    reconnectTimer.current = setTimeout(() => {
      reconnectTimer.current = null
      reconnectDelay.current = Math.min(delay * 2, 10000)
      connectRef.current()
    }, delay)
  }, [])

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN ||
        wsRef.current?.readyState === WebSocket.CONNECTING) return

    try {
      const ws = new WebSocket(url)

      ws.onopen = () => {
        console.log('[WS] Connected to assistant')
        reconnectDelay.current = 1000
        setState(prev => ({ ...prev, connected: true }))
      }

      ws.onmessage = (event: MessageEvent) => {
        try {
          const msg = JSON.parse(event.data) as ServerMessage
          handleMessage(msg)
        } catch {
          console.warn('[WS] Invalid message:', event.data)
        }
      }

      ws.onclose = () => {
        console.log('[WS] Disconnected, will reconnect...')
        setState(prev => ({ ...prev, connected: false }))
        scheduleReconnect()
      }

      ws.onerror = () => {
        ws.close()
      }

      wsRef.current = ws
    } catch {
      scheduleReconnect()
    }
  }, [url, handleMessage, scheduleReconnect])

  // Keep ref in sync so scheduleReconnect can call the latest connect
  useEffect(() => {
    connectRef.current = connect
  }, [connect])

  const sendAction = useCallback((action: UIAction) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(action))
    }
  }, [])

  const actions: AssistantActions = useMemo(() => ({
    pause: () => sendAction({ action: 'music_control', params: { action: 'pause' } }),
    resume: () => sendAction({ action: 'music_control', params: { action: 'resume' } }),
    skip: () => sendAction({ action: 'music_control', params: { action: 'skip' } }),
    stop: () => sendAction({ action: 'music_control', params: { action: 'stop' } }),
    seek: (position: number) => sendAction({ action: 'seek', params: { position } }),
    setVolume: (level: number) => sendAction({ action: 'volume', params: { level } }),
    setLights: (params: Record<string, unknown>) => sendAction({ action: 'light_control', params }),
    switchPersonality: (id: string) => sendAction({ action: 'switch_personality', params: { personality: id } }),
    sendText: (text: string) => sendAction({ action: 'text_input', params: { text } }),
    sendGesture: (gesture: string, target?: string) => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'gesture', gesture, target: target ?? null }))
      }
    },
    updateSetting: (path: string, value: any) => sendAction({ action: 'update_setting', params: { path, value } }),
    requestSettings: () => sendAction({ action: 'get_settings', params: {} }),
    wake: () => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'ui_action', action: 'wake' }))
      }
    },
    // Audio controls — use ui_action type for backend routing
    listOutputs: () => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'ui_action', action: 'audio_list_outputs' }))
      }
    },
    setOutput: (device: string) => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'ui_action', action: 'audio_set_output', device }))
      }
    },
    btScan: () => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'ui_action', action: 'bt_scan' }))
      }
    },
    btPair: (mac: string) => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'ui_action', action: 'bt_pair', mac }))
      }
    },
    btDisconnect: (mac: string) => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'ui_action', action: 'bt_disconnect', mac }))
      }
    },
    closeVideo: () => {
      // Clear videoId locally and notify backend
      setState(prev => ({
        ...prev,
        nowPlaying: prev.nowPlaying ? { ...prev.nowPlaying, videoId: null } : null,
      }))
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'ui_action', action: 'close_video' }))
      }
    },
    closeBrowse: () => {
      setState(prev => ({ ...prev, youtubeBrowseUrl: null }))
    },
    // Quiz controls
    quizAnswer: (answer: string) => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'ui_action', action: 'quiz_answer', answer }))
      }
    },
    quizHint: () => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'ui_action', action: 'quiz_hint' }))
      }
    },
    quizQuit: () => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'ui_action', action: 'quiz_quit' }))
      }
    },
  }), [sendAction])

  useEffect(() => {
    connect()
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [connect])

  return { ...state, actions, sendAction }
}
