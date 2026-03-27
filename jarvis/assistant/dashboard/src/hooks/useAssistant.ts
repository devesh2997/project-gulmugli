/**
 * Central state management hook for the assistant.
 *
 * Connects to the assistant's WebSocket server and maintains all UI state.
 * Auto-reconnects with exponential backoff on disconnection.
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import type {
  AssistantState,
  AssistantStore,
  AssistantActions,
  AssistantMood,
  IntentBadge,
  SettingSchema,
  TranscriptEntry,
  NowPlaying,
  LightsState,
  PersonalityInfo,
  ServerMessage,
  UIAction,
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
  intents: IntentBadge[]
  mood: AssistantMood
  settings: SettingSchema[]
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
  intents: [],
  mood: 'neutral',
  settings: [],
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
          } : null,
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
        setState(prev => ({ ...prev, volume: msg.level ?? prev.volume }))
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

      case 'token_update':
        onTokenUpdateRef.current?.(msg.path, msg.value)
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
    if (wsRef.current?.readyState === WebSocket.OPEN) return

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

  const actions: AssistantActions = {
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
  }

  useEffect(() => {
    connect()
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [connect])

  return { ...state, actions, sendAction }
}
