/**
 * Type definitions for the assistant's WebSocket protocol.
 *
 * These types define the contract between the Python backend (ui/server.py)
 * and the React dashboard. If you add a new message type in Python,
 * add it here too — TypeScript will flag any mismatches.
 */

// ─── Assistant States ─────────────────────────────────────────────
export type AssistantState = 'idle' | 'listening' | 'thinking' | 'speaking' | 'sleeping'

// ─── Audio Types ─────────────────────────────────────────────────
export type AudioOutputType = 'speaker' | 'headphones' | 'bluetooth' | 'hdmi' | 'usb' | 'airplay' | 'unknown'

export interface AudioDevice {
  name: string
  type: AudioOutputType
  active: boolean
}

export interface BluetoothDevice {
  name: string
  mac: string
  paired: boolean
  connected: boolean
  /** Signal strength percentage (0-100), null if unknown */
  rssi?: number | null
}

export interface AudioState {
  volume: number
  outputs: AudioDevice[]
  bluetoothScanning: boolean
  bluetoothDevices: BluetoothDevice[]
}

// ─── Assistant Mood ───────────────────────────────────────────────
export type AssistantMood =
  | 'neutral'
  | 'happy'
  | 'sad'
  | 'shy'
  | 'playful'
  | 'sarcastic'
  | 'romantic'
  | 'surprised'
  | 'gotcha'

// ─── Avatar Types ─────────────────────────────────────────────────
export type AvatarType = 'orb' | 'pixel' | 'light' | 'caricature'

// ─── Intent Badges ────────────────────────────────────────────────
export type IntentStatus = 'queued' | 'processing' | 'done' | 'failed'

export type IntentIcon =
  | 'music'
  | 'bulb'
  | 'brain'
  | 'volume'
  | 'personality'
  | 'timer'
  | 'search'
  | 'general'

export interface IntentBadge {
  id: string
  intent_type: string
  label: string
  icon: IntentIcon
  status: IntentStatus
  detail?: string  // contextual info from handler (e.g., "Playing Sajni by Arijit Singh")
}

// ─── Settings Schema ─────────────────────────────────────────────
export interface SettingSchema {
  path: string
  type: 'string' | 'int' | 'float' | 'bool' | 'choice'
  label: string
  description: string
  category: string
  value: any
  choices?: string[]
  min?: number
  max?: number
  restart: 'none' | 'provider' | 'full'
  editable?: boolean
}

// ─── Messages FROM the assistant (server → browser) ───────────────
export interface StateMessage {
  type: 'state'
  state: AssistantState
}

export interface PersonalityMessage {
  type: 'personality'
  id: string
}

export interface PersonalitiesMessage {
  type: 'personalities'
  list: PersonalityInfo[]
}

export interface TranscriptMessage {
  type: 'transcript'
  text: string
  role: 'user' | 'assistant'
}

export interface NowPlayingData {
  title: string
  artist: string
  album?: string
  art_url?: string | null
  duration?: number
  position?: number
}

export interface NowPlayingMessage {
  type: 'now_playing'
  data: NowPlayingData
  paused?: boolean
}

export interface MusicStoppedMessage {
  type: 'music_stopped'
}

export interface MusicPausedMessage {
  type: 'music_paused'
  paused: boolean
}

export interface LightsMessage {
  type: 'lights'
  on: boolean
  color: string
  brightness: number
  scene: string | null
}

export interface VolumeMessage {
  type: 'volume'
  level: number
}

export interface IntentsMessage {
  type: 'intents'
  intents: IntentBadge[]
}

export interface IntentUpdateMessage {
  type: 'intent_update'
  id: string
  status: IntentStatus
  detail?: string
}

export interface MoodMessage {
  type: 'mood'
  mood: AssistantMood
}

export interface TokenUpdateMessage {
  type: 'token_update'
  path: string
  value: string
}

export interface SettingsMessage {
  type: 'settings'
  settings: SettingSchema[]
}

export interface SettingResultMessage {
  type: 'setting_result'
  path: string
  ok: boolean
  message: string
  restart_required?: string
}

export interface SleepModeMessage {
  type: 'sleep_mode'
  active: boolean
}

export interface AudioOutputsMessage {
  type: 'audio_outputs'
  outputs: AudioDevice[]
}

export interface BluetoothScanMessage {
  type: 'bt_scan_result'
  devices: BluetoothDevice[]
  scanning: boolean
}

export interface BluetoothPairMessage {
  type: 'bt_pair_result'
  mac: string
  success: boolean
  name?: string
}

export type ServerMessage =
  | StateMessage
  | PersonalityMessage
  | PersonalitiesMessage
  | TranscriptMessage
  | NowPlayingMessage
  | MusicStoppedMessage
  | MusicPausedMessage
  | LightsMessage
  | VolumeMessage
  | IntentsMessage
  | IntentUpdateMessage
  | MoodMessage
  | TokenUpdateMessage
  | SettingsMessage
  | SettingResultMessage
  | SleepModeMessage
  | AudioOutputsMessage
  | BluetoothScanMessage
  | BluetoothPairMessage

// ─── Messages TO the assistant (browser → server) ─────────────────
export type GestureType =
  | 'swipe_up'
  | 'swipe_down'
  | 'swipe_left'
  | 'swipe_right'
  | 'tap'
  | 'long_press'

export interface GestureMessage {
  type: 'gesture'
  gesture: GestureType
  target: string | null
}

export interface UIAction {
  action: string
  params: Record<string, unknown>
}

// ─── Client-side state ────────────────────────────────────────────
export interface TranscriptEntry {
  role: 'user' | 'assistant'
  text: string
  timestamp: number
}

export interface NowPlaying {
  title: string
  artist: string
  album: string
  artUrl: string | null
  duration: number
  position: number
  paused: boolean
}

export interface LightsState {
  on: boolean
  color: string
  brightness: number
  scene: string | null
}

export interface PersonalityInfo {
  id: string
  display_name: string
  description: string
}

export interface AssistantStore {
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
  actions: AssistantActions
  sendAction: (action: UIAction) => void
}

export interface AssistantActions {
  pause: () => void
  resume: () => void
  skip: () => void
  stop: () => void
  seek: (position: number) => void
  setVolume: (level: number) => void
  setLights: (params: Record<string, unknown>) => void
  switchPersonality: (id: string) => void
  sendText: (text: string) => void
  sendGesture: (gesture: string, target?: string) => void
  updateSetting: (path: string, value: any) => void
  requestSettings: () => void
  wake: () => void
  // Audio controls
  listOutputs: () => void
  setOutput: (device: string) => void
  btScan: () => void
  btPair: (mac: string) => void
  btDisconnect: (mac: string) => void
}
