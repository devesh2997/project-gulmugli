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
export type AvatarType = 'orb' | 'pixel' | 'light' | 'caricature' | string

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
  /** Always present (empty string if no video available) */
  video_id: string
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

export interface YouTubeBrowseMessage {
  type: 'youtube_browse'
  url: string
}

export interface PlaySongMessage {
  type: 'play_song'
  data: { videoId: string; title: string; artist: string; album?: string; duration?: number }
}

export interface PlayerCommandMessage {
  type: 'player_command'
  command: 'pause' | 'play' | 'stop' | 'seek' | 'volume'
  position?: number
  level?: number
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

// ─── Reminders ──────────────────────────────────────────────────
export interface ReminderData {
  id: string
  text: string
  remind_at: string   // ISO datetime
  repeat: 'none' | 'daily' | 'weekly' | 'monthly'
  created_at: string
  active: boolean
}

export interface ReminderFiredMessage {
  type: 'reminder_fired'
  data: ReminderData
}

export interface RemindersUpdatedMessage {
  type: 'reminders_updated'
  reminders: ReminderData[]
}

// ─── Timers & Alarms ─────────────────────────────────────────────
export interface TimerData {
  id: string
  type: 'timer' | 'alarm'
  target_time: number     // unix timestamp
  label: string
  repeat: 'none' | 'daily' | 'weekdays'
  active: boolean
  remaining_seconds: number
  original_time_str?: string
  created_at: number
}

export interface TimersMessage {
  type: 'timers'
  timers: TimerData[]
}

export interface TimerFiredMessage {
  type: 'timer_fired'
  data: TimerData
}

export interface TimerCancelledMessage {
  type: 'timer_cancelled'
  data: TimerData
}

// ─── Quiz / Trivia ──────────────────────────────────────────────
export interface QuizShowMessage {
  type: 'quiz_show'
  data: {
    question: string
    category: string
    difficulty: string
    question_number: number
    total_questions: number
    time_limit?: number
    options: string[]  // ["A) Paris", "B) London", ...]
  }
}

export interface QuizUpdateMessage {
  type: 'quiz_update'
  state: {
    correct: boolean
    correct_answer: string
    explanation?: string
    reaction?: string  // personality-flavored response
    score: { correct: number; total: number }
  }
}

export interface QuizCloseMessage {
  type: 'quiz_close'
}

export interface QuizQuestion {
  question: string
  category: string
  difficulty: string
  questionNumber: number
  totalQuestions: number
  timeLimit?: number
  options: string[]
}

export interface QuizResult {
  correct: boolean
  correctAnswer: string
  explanation?: string
  reaction?: string
}

export interface QuizState {
  active: boolean
  question: QuizQuestion | null
  lastResult: QuizResult | null
  score: { correct: number; total: number }
  /** Track per-question outcomes for the score dot visualization */
  outcomes: ('correct' | 'wrong')[]
  /** Whether we're showing the end-of-game stats */
  showStats: boolean
}

// ─── Story Mode ──────────────────────────────────────────────────
export type StoryGenre = 'bedtime' | 'funny' | 'romantic' | 'scary' | 'adventure' | null

export interface StoryState {
  active: boolean
  genre: StoryGenre
  paragraphs: string[]
  currentParagraph: number
  finished: boolean
}

export interface StoryModeMessage {
  type: 'story_mode'
  data: {
    active: boolean
    genre?: string | null
    paragraphs?: string[]
    current_paragraph?: number
    finished?: boolean
  }
}

// ─── Weather ─────────────────────────────────────────────────────
export type WeatherCondition =
  | 'sunny'
  | 'partly_cloudy'
  | 'cloudy'
  | 'rain'
  | 'thunderstorm'
  | 'snow'
  | 'fog'
  | 'clear_night'

export interface WeatherCurrent {
  temperature: number
  feels_like: number
  humidity: number
  wind_speed: number
  condition: WeatherCondition
  description: string
  icon: WeatherCondition
  sunrise?: string
  sunset?: string
  location: string
  unit: string  // "C" or "F"
}

export interface WeatherForecastDay {
  date: string
  temp_min: number
  temp_max: number
  condition: WeatherCondition
  description: string
  icon: WeatherCondition
  precipitation_chance: number
}

export interface WeatherHourly {
  time: string
  temperature: number
  condition: WeatherCondition
  icon: WeatherCondition
  precipitation_chance: number
}

export interface WeatherData {
  temperature?: number
  feels_like?: number
  humidity?: number
  wind_speed?: number
  condition?: WeatherCondition
  description?: string
  icon?: WeatherCondition
  sunrise?: string
  sunset?: string
  location: string
  unit: string
  forecast?: WeatherForecastDay[]
  hourly?: WeatherHourly[]
}

export interface WeatherShowMessage {
  type: 'weather_show'
  data: WeatherData
}

// ─── Ambient Sounds ─────────────────────────────────────────────
export type AmbientSoundName =
  | 'rain'
  | 'ocean'
  | 'thunderstorm'
  | 'white_noise'
  | 'pink_noise'
  | 'brown_noise'
  | 'fireplace'
  | 'forest'
  | 'birds'
  | 'wind'
  | 'cafe'
  | 'fan'

export interface AmbientState {
  active: boolean
  sound: AmbientSoundName | ''
  volume: number
}

export interface AmbientMessage {
  type: 'ambient'
  active: boolean
  sound: AmbientSoundName | ''
  volume: number
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
  | ReminderFiredMessage
  | RemindersUpdatedMessage
  | TimersMessage
  | TimerFiredMessage
  | TimerCancelledMessage
  | QuizShowMessage
  | QuizUpdateMessage
  | QuizCloseMessage
  | YouTubeBrowseMessage
  | PlaySongMessage
  | PlayerCommandMessage
  | WeatherShowMessage
  | StoryModeMessage
  | AmbientMessage
  | { type: 'video_control'; action: string }
  | { type: 'playback_position'; position: number; duration: number }

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
  videoId: string | null
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
  quiz: QuizState
  story: StoryState
  reminders: ReminderData[]
  firedReminder: ReminderData | null
  timers: TimerData[]
  firedTimer: TimerData | null
  weather: WeatherData | null
  ambient: AmbientState
  youtubeBrowseUrl: string | null
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
  closeVideo: () => void
  closeBrowse: () => void
  // Player position reporting
  reportPosition: (position: number, duration: number) => void
  reportPlayerEnded: () => void
  // Reminder controls
  cancelReminder: (id: string) => void
  snoozeReminder: (id: string, minutes: number) => void
  dismissReminder: () => void
  // Timer controls
  cancelTimer: (id: string) => void
  snoozeTimer: (id: string, minutes?: number) => void
  dismissTimer: () => void
  // Quiz controls
  quizAnswer: (answer: string) => void
  quizHint: () => void
  quizQuit: () => void
  // Ambient controls
  stopAmbient: () => void
  setAmbientVolume: (level: number) => void
}
