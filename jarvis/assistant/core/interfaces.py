"""
Interfaces for every swappable component.

This is the architectural backbone of the project. Each interface defines
WHAT a component must do, not HOW it does it. Implementations live in
their own folders (providers/brain/ollama.py, providers/music/youtube.py, etc.)

To swap any component:
  1. Write a new class that inherits from the interface
  2. Register it in the provider registry (providers/__init__.py)
  3. Change one line in config.yaml

No other code needs to change.

Why ABC (Abstract Base Class)?
  - Forces every implementation to define the required methods
  - If you forget to implement a method, Python raises an error at startup
    (not at runtime when a user asks to play music)
  - Makes it crystal clear what the "contract" is between modules
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


# ═══════════════════════════════════════════════════════════════
# Data classes — shared across all implementations
# ═══════════════════════════════════════════════════════════════

@dataclass
class LLMResponse:
    """Response from any LLM provider."""
    text: str
    model: str
    latency: float           # seconds
    tokens_generated: int
    tokens_per_second: float
    raw: dict = field(default_factory=dict)  # provider-specific metadata


@dataclass
class Intent:
    """Parsed user intent — the output of the brain."""
    name: str                # music_play, music_control, light_control, chat, system
    params: dict             # intent-specific parameters
    response: str            # what to speak back to the user
    confidence: float = 1.0  # 0.0 to 1.0 — how sure the brain is
    meta: dict = field(default_factory=dict)  # latency, model used, etc.


@dataclass
class SongResult:
    """A single song search result from any music provider."""
    title: str
    artist: str
    album: str = ""
    duration: str = ""
    uri: str = ""            # provider-specific ID (videoId, spotify URI, etc.)
    source: str = ""         # "youtube_music", "spotify", etc.


@dataclass
class TranscriptionResult:
    """Output from any speech-to-text provider."""
    text: str
    language: str            # detected language code
    confidence: float        # 0.0 to 1.0
    latency: float           # seconds


# ═══════════════════════════════════════════════════════════════
# Interfaces
# ═══════════════════════════════════════════════════════════════

class BrainProvider(ABC):
    """
    Interface for the LLM / intent classification layer.

    Current implementations: Ollama (wrapping qwen, llama, phi, etc.)
    Possible future implementations: llama.cpp server, OpenAI API, local ONNX, etc.
    """

    @abstractmethod
    def generate(self, prompt: str, system: str = "", json_mode: bool = False,
                 temperature: float = 0.7) -> LLMResponse:
        """Generate a raw text response from the LLM."""
        ...

    @abstractmethod
    def classify_intent(self, user_input: str) -> list[Intent]:
        """
        Classify a voice command into one or more structured intents.

        Returns a list because users may chain commands:
          "Play Sajni and set lights to red" → [music_play, light_control]
          "Sajni volume 30" → [music_play, music_control]
          "just play something" → [music_play]  (single-element list)
        """
        ...

    @abstractmethod
    def list_models(self) -> list[str]:
        """List available models on this provider."""
        ...


class AudioOutputProvider(ABC):
    """
    Interface for system-level audio output control.

    This is the layer between everything that produces sound (music, TTS)
    and the physical speakers. Volume lives here, not in MusicProvider,
    because "volume down" means "the speaker is too loud" — it applies to
    all audio, not just the current song.

    Why separate from MusicProvider?
      - Music plays through it, but so does TTS (voice responses)
      - Volume is per-speaker, not per-source
      - Multiple speakers may be connected (room, bedroom, portable)
      - On edge devices, this maps to ALSA/PulseAudio/PipeWire
      - On Mac simulation, this maps to mpv's volume + system volume

    Current implementations: none yet (volume temporarily handled in MusicProvider)
    Future implementations: PulseAudio, PipeWire, ALSA, CoreAudio (macOS), Bluetooth
    """

    @abstractmethod
    def set_volume(self, level: int, output: str = "default") -> None:
        """Set volume 0-100 on a named output. 'default' = primary speaker."""
        ...

    @abstractmethod
    def get_volume(self, output: str = "default") -> int:
        """Get current volume 0-100 on a named output."""
        ...

    @abstractmethod
    def list_outputs(self) -> list[dict]:
        """
        List available audio outputs.
        Returns: [{"name": "bluetooth_jbl", "type": "bluetooth", "active": True}, ...]
        """
        ...

    @abstractmethod
    def set_default_output(self, output: str) -> None:
        """Switch the default audio output (e.g., switch from HDMI to Bluetooth)."""
        ...


class MusicProvider(ABC):
    """
    Interface for music search and playback.

    Note: volume is NOT here. Volume is a system-level concern handled by
    AudioOutputProvider. MusicProvider only controls music-specific things:
    search, play, pause, resume, stop, skip.

    Current implementations: YouTube Music (via ytmusicapi + mpv)
    Possible future implementations: Spotify (spotipy), Apple Music, local library, etc.
    """

    @abstractmethod
    def search(self, query: str, limit: int = 5) -> list[SongResult]:
        """Search for songs matching a query."""
        ...

    @abstractmethod
    def play(self, song: SongResult) -> bool:
        """Start playing a song. Returns True if playback started successfully."""
        ...

    @abstractmethod
    def pause(self) -> None:
        """Pause current playback."""
        ...

    @abstractmethod
    def resume(self) -> None:
        """Resume paused playback."""
        ...

    @abstractmethod
    def stop(self) -> None:
        """Stop playback entirely."""
        ...

    @abstractmethod
    def skip(self) -> None:
        """Skip to the next song (if queue exists)."""
        ...


class LightProvider(ABC):
    """
    Interface for smart light control.

    Current implementations: Tuya (for Wipro IoT bulbs via tinytuya)
    Possible future implementations: Philips Hue, WiZ, MQTT, HomeAssistant, etc.
    """

    @abstractmethod
    def turn_on(self, device_name: str = "all") -> None:
        ...

    @abstractmethod
    def turn_off(self, device_name: str = "all") -> None:
        ...

    @abstractmethod
    def set_color(self, color: str, device_name: str = "all") -> None:
        """Set color. Accepts hex (#FF0000), named colors (red), or HSV tuples."""
        ...

    @abstractmethod
    def set_brightness(self, level: int, device_name: str = "all") -> None:
        """Set brightness. 0-100."""
        ...

    @abstractmethod
    def set_scene(self, scene_name: str) -> None:
        """Apply a named scene from config (romantic, movie, etc.)."""
        ...

    @abstractmethod
    def list_devices(self) -> list[dict]:
        """List all discovered/configured light devices."""
        ...


class EarsProvider(ABC):
    """
    Interface for speech-to-text.

    Current implementations: faster-whisper
    Possible future implementations: whisper.cpp, Google Cloud STT, Azure, Vosk, etc.
    """

    @abstractmethod
    def transcribe(self, audio_data: bytes, sample_rate: int = 16000) -> TranscriptionResult:
        """Transcribe audio bytes to text."""
        ...

    @abstractmethod
    def transcribe_file(self, file_path: str) -> TranscriptionResult:
        """Transcribe an audio file to text."""
        ...


class VoiceProvider(ABC):
    """
    Interface for text-to-speech.

    Current implementations: Piper TTS
    Possible future implementations: Coqui XTTS, ElevenLabs, system TTS, etc.
    """

    @abstractmethod
    def speak(self, text: str) -> bytes:
        """Convert text to audio bytes (WAV format)."""
        ...

    @abstractmethod
    def speak_to_device(self, text: str) -> None:
        """Convert text to audio and play it through the configured output device."""
        ...


class WakeWordProvider(ABC):
    """
    Interface for wake word detection.

    Current implementations: OpenWakeWord
    Possible future implementations: Porcupine, Snowboy, custom, etc.
    """

    @abstractmethod
    def start_listening(self, callback) -> None:
        """Start listening for the wake word. Calls callback() when detected."""
        ...

    @abstractmethod
    def stop_listening(self) -> None:
        """Stop wake word detection."""
        ...
