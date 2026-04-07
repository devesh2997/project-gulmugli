"""
Pydantic models — the shared API contract.

These define the request/response shapes for all API endpoints.
FastAPI auto-generates OpenAPI docs from these at /api/docs.

The models mirror the dataclasses in core/interfaces.py and the
TypeScript types in dashboard/src/types/assistant.ts.

Start with core models for Phase 1. Expanded in later phases.
"""

from typing import Any, Optional

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════
# System
# ═══════════════════════════════════════════════════════════════

class HealthResponse(BaseModel):
    """Unauthenticated health check — used by service discovery."""
    status: str = "ok"
    name: str
    version: str = "1.0.0"


class SystemStatusResponse(BaseModel):
    """Full system status — authenticated."""
    name: str
    state: str                         # idle, listening, thinking, speaking, sleeping
    personality: str                   # active personality id
    personality_display_name: str
    sleep_mode: bool
    music_playing: bool
    volume: int
    uptime_seconds: float
    version: str = "1.0.0"


class TimeResponse(BaseModel):
    time: str       # HH:MM:SS
    date: str       # YYYY-MM-DD
    day: str        # Monday, Tuesday, ...
    timezone: str


# ═══════════════════════════════════════════════════════════════
# Intents (unified endpoint)
# ═══════════════════════════════════════════════════════════════

class IntentRequest(BaseModel):
    """Submit an intent directly — bypass LLM classification."""
    name: str = Field(..., description="Intent type: music_play, light_control, volume, etc.")
    params: dict[str, Any] = Field(default_factory=dict, description="Intent-specific parameters.")


class IntentResponse(BaseModel):
    """Response from intent execution."""
    ok: bool
    response: str = ""                 # spoken response text
    error: Optional[str] = None


# ═══════════════════════════════════════════════════════════════
# Chat
# ═══════════════════════════════════════════════════════════════

class ChatRequest(BaseModel):
    """Send text through the full pipeline (classify → execute → respond)."""
    text: str = Field(..., min_length=1, description="User input text.")


class ChatResponse(BaseModel):
    ok: bool
    response: str = ""
    intents: list[dict[str, Any]] = Field(default_factory=list)
    error: Optional[str] = None


# ═══════════════════════════════════════════════════════════════
# Music
# ═══════════════════════════════════════════════════════════════

class MusicPlayRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Song name / search query.")
    with_video: bool = False


class MusicControlRequest(BaseModel):
    action: str = Field(..., description="pause, resume, stop, or skip.")


class MusicSeekRequest(BaseModel):
    position: float = Field(..., ge=0, description="Seek position in seconds.")


class NowPlayingResponse(BaseModel):
    playing: bool
    paused: bool = False
    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    duration: Optional[float] = None
    position: Optional[float] = None
    art_url: Optional[str] = None
    video_id: Optional[str] = None


# ═══════════════════════════════════════════════════════════════
# Lights
# ═══════════════════════════════════════════════════════════════

class LightControlRequest(BaseModel):
    action: str = Field(..., description="on, off, color, brightness, or scene.")
    value: Optional[str] = None        # color hex/name, brightness 0-100, scene name
    device: Optional[str] = None       # specific device or 'all'


class LightStateResponse(BaseModel):
    on: bool
    color: str = "#ffffff"
    brightness: int = 100
    scene: Optional[str] = None


class LightDeviceResponse(BaseModel):
    name: str
    device_id: str
    online: bool = True


# ═══════════════════════════════════════════════════════════════
# Volume
# ═══════════════════════════════════════════════════════════════

class VolumeRequest(BaseModel):
    level: int = Field(..., ge=0, le=100, description="Volume level 0-100.")


class VolumeResponse(BaseModel):
    level: int


# ═══════════════════════════════════════════════════════════════
# Personality
# ═══════════════════════════════════════════════════════════════

class PersonalitySwitchRequest(BaseModel):
    personality: str = Field(..., description="Personality id or display name.")


class PersonalityInfo(BaseModel):
    id: str
    display_name: str
    description: str
    avatar_type: str = "orb"


class PersonalityListResponse(BaseModel):
    active: str
    personalities: list[PersonalityInfo]


# ═══════════════════════════════════════════════════════════════
# Weather
# ═══════════════════════════════════════════════════════════════

class WeatherCurrentResponse(BaseModel):
    temperature: float
    feels_like: float
    humidity: int
    wind_speed: float
    condition: str
    description: str
    sunrise: str = ""
    sunset: str = ""


class WeatherForecastDay(BaseModel):
    date: str
    temp_min: float
    temp_max: float
    condition: str
    description: str
    precipitation_chance: int = 0


class WeatherForecastResponse(BaseModel):
    current: Optional[WeatherCurrentResponse] = None
    forecast: list[WeatherForecastDay] = Field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
# Quiz
# ═══════════════════════════════════════════════════════════════

class QuizStartRequest(BaseModel):
    category: str = "general"
    difficulty: str = "medium"
    num_questions: int = 10


class QuizAnswerRequest(BaseModel):
    answer: str


class QuizResponse(BaseModel):
    ok: bool
    data: dict[str, Any] = Field(default_factory=dict)
    response: str = ""


# ═══════════════════════════════════════════════════════════════
# Timer / Reminder
# ═══════════════════════════════════════════════════════════════

class TimerRequest(BaseModel):
    action: str = Field(..., description="set or cancel.")
    duration: Optional[str] = None     # "5 minutes", "30 seconds"
    label: Optional[str] = None
    cancel_id: Optional[str] = None


class ReminderRequest(BaseModel):
    action: str = Field(..., description="set or cancel.")
    text: Optional[str] = None
    time: Optional[str] = None         # "3pm", "in 2 hours"
    cancel_id: Optional[str] = None


# ═══════════════════════════════════════════════════════════════
# Story / Ambient
# ═══════════════════════════════════════════════════════════════

class StoryRequest(BaseModel):
    action: str = Field(..., description="start, continue, or stop.")
    genre: Optional[str] = None
    topic: Optional[str] = None


class AmbientRequest(BaseModel):
    action: str = Field(..., description="start or stop.")
    sound: Optional[str] = None        # rain, ocean, fireplace, etc.
    volume: Optional[int] = None


# ═══════════════════════════════════════════════════════════════
# Memory
# ═══════════════════════════════════════════════════════════════

class MemoryRecallResponse(BaseModel):
    memories: list[dict[str, Any]] = Field(default_factory=list)


class MemoryStatsResponse(BaseModel):
    total_interactions: int = 0
    stats: dict[str, Any] = Field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════
# Knowledge
# ═══════════════════════════════════════════════════════════════

class KnowledgeSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)


# ═══════════════════════════════════════════════════════════════
# Settings
# ═══════════════════════════════════════════════════════════════

class SettingUpdateRequest(BaseModel):
    path: str = Field(..., description="Dotted config path, e.g. 'music.search_results'.")
    value: Any


class SettingUpdateResponse(BaseModel):
    ok: bool
    path: str
    error: Optional[str] = None


# ═══════════════════════════════════════════════════════════════
# Audio
# ═══════════════════════════════════════════════════════════════

class AudioOutputInfo(BaseModel):
    name: str
    type: str = "unknown"
    active: bool = False


class BluetoothDeviceInfo(BaseModel):
    name: str
    mac_address: str
    paired: bool = False


class BluetoothActionRequest(BaseModel):
    mac_address: str
