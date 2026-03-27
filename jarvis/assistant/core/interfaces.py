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
from typing import Any, Optional


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
class Personality:
    """
    A personality the assistant can adopt.

    Each personality changes how the assistant talks (tone), what it sounds like
    (voice_model), and optionally what music it prefers (music_preferences).

    The tone string is injected directly into the LLM system prompt, so it
    should be written as instructions to the LLM:
        "You speak casually in Hinglish. You're nerdy and have dry humor."

    Music preferences override the global ones when set. When None, the global
    config.music.user_preferences are used instead.
    """
    id: str                           # config key: "devesh", "jarvis", "chandler"
    display_name: str                 # what the assistant calls itself in this mode
    description: str                  # one-liner for listing: "The sarcastic one"
    tone: str                         # injected into system prompt
    voice_provider: str = ""          # TTS provider: "piper", "xtts", "" = use default
    voice_model: str = ""             # TTS model ID (empty = use default from voice config)
    fallback_voice: str = ""          # voice to use when preferred provider unavailable
    music_preferences: dict = field(default_factory=dict)  # override global prefs, empty = use global
    wake_word: str = ""               # optional per-personality wake word


@dataclass
class TranscriptionResult:
    """Output from any speech-to-text provider."""
    text: str
    language: str            # detected language code
    confidence: float        # 0.0 to 1.0
    latency: float           # seconds


@dataclass
class SearchResult:
    """A single result from a knowledge/search provider."""
    title: str               # page/article title
    snippet: str             # short summary or extracted text (keep under ~100 words)
    url: str = ""            # source URL (empty for local docs/RSS)
    source: str = ""         # provider name: "duckduckgo", "searxng", "local_docs", etc.
    full_text: str = ""      # full page content (only populated by fetch(), empty for search())
    timestamp: str = ""      # publication date if known (ISO 8601)
    relevance: float = 1.0   # 0.0-1.0, provider's confidence in relevance


@dataclass
class Interaction:
    """
    A single interaction between a user and the assistant.

    This is what gets logged to memory — the full round-trip of
    "what was said → what was understood → what happened."

    Why log everything, not just the intent?
      - "Play Sajni" might resolve to different songs on different days
      - Knowing the outcome ("Played Sajni by Arijit Singh") lets you
        build preferences: "when ET says Sajni, he means the Arijit one"
      - The raw input is critical for future STT improvement — if you
        log what the user actually said vs what the LLM understood,
        you can spot where classification goes wrong
    """
    user_id: str                      # "default" for v1 (single-user), real IDs in v3
    input_text: str                   # raw text from user (or STT output)
    intents: list                     # list of Intent objects classified from input
    responses: list[str]              # what the assistant said back (one per intent)
    timestamp: str = ""               # ISO 8601 — filled automatically if empty
    outcome: str = ""                 # "success", "no_results", "error", etc.
    feedback: Optional[str] = None    # user feedback if any ("wrong song", thumbs up)


@dataclass
class Memory:
    """
    A single memory retrieved from the memory store.

    This wraps whatever the memory provider returns when you ask
    "what do you remember about X?" — could be an interaction log entry,
    a stored fact, or a preference.
    """
    content: str                      # human-readable summary of the memory
    category: str                     # "interaction", "fact", "preference"
    timestamp: str                    # when this memory was created
    relevance: float = 1.0            # 0.0-1.0, how relevant to the query
    raw: dict = field(default_factory=dict)  # full stored data for programmatic use


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

    Current implementations: CoreAudio (macOS), PulseAudio (Linux/Jetson), ALSA (Pi)
    Future implementations: PipeWire, Bluetooth-only
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

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this audio provider can operate on the current platform."""
        ...

    def bluetooth_scan(self, timeout: int = 10) -> list[dict]:
        """
        Scan for nearby Bluetooth audio devices.

        Returns: [{"name": "JBL Flip 6", "mac_address": "AA:BB:CC:DD:EE:FF", "paired": False}, ...]

        Default implementation returns empty list — override in providers
        that support Bluetooth (all current ones delegate to BluetoothHelper).
        """
        return []

    def bluetooth_pair(self, mac_address: str) -> bool:
        """
        Pair, trust, and connect to a Bluetooth device.

        Returns True if the device was successfully connected.
        Default: returns False (no Bluetooth support).
        """
        return False

    def bluetooth_disconnect(self, mac_address: str) -> bool:
        """
        Disconnect a paired Bluetooth device.

        Returns True if the device was successfully disconnected.
        Default: returns False (no Bluetooth support).
        """
        return False


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

    Each implementation handles one TTS engine (Piper, XTTS, etc.).
    The voice_model parameter maps to personality.voice_model from config.

    For Piper: voice_model = "en_US-lessac-medium" (a pre-built model name)
    For XTTS:  voice_model = "voices/devesh.wav" (path to reference audio for cloning)

    Current implementations: Piper TTS, Coqui XTTS
    Possible future implementations: ElevenLabs, system TTS, etc.
    """

    @abstractmethod
    def speak(self, text: str, voice_model: str = "") -> bytes:
        """
        Convert text to audio bytes (WAV format).

        voice_model: which voice to use. Empty = provider's default.
        The meaning depends on the provider:
          - Piper: model name like "en_US-lessac-medium"
          - XTTS: path to reference WAV for voice cloning
        """
        ...

    @abstractmethod
    def speak_to_device(self, text: str, voice_model: str = "", interrupt_event=None) -> bool:
        """
        Convert text to audio and play through the configured output device.

        Args:
            interrupt_event: Optional threading.Event. If set during playback,
                audio stops immediately (wake word barge-in).

        Returns:
            True if playback completed normally, False if interrupted.
        """
        ...

    @abstractmethod
    def list_voices(self) -> list[str]:
        """List available voice models for this provider."""
        ...


@dataclass
class WakeWordDetection:
    """Fired when a wake word is detected."""
    wake_word: str          # which wake word was heard: "jarvis", "devesh", etc.
    confidence: float       # 0.0 to 1.0 — how confident the model is
    personality_id: str = ""  # if this wake word maps to a personality, its ID
    audio_after: bytes = b""  # audio captured AFTER the wake word (for STT)


class WakeWordProvider(ABC):
    """
    Interface for wake word detection.

    The wake word system runs in a background thread, continuously streaming
    mic audio through a small neural model (~1-2MB). When it hears one of
    the registered wake words, it fires the callback with a WakeWordDetection
    object that tells you WHICH word was heard — enabling per-personality
    wake word switching.

    Flow:
      1. register_wake_words({"jarvis": "jarvis", "hey devesh": "devesh"})
      2. start_listening(on_detection_callback)
      3. User says "Hey Devesh, play some music"
      4. Callback fires with WakeWordDetection(wake_word="hey devesh", personality_id="devesh")
      5. Main loop switches personality → starts STT recording → processes command

    Current implementations: OpenWakeWord
    Possible future implementations: Porcupine, Snowboy, custom
    """

    @abstractmethod
    def register_wake_words(self, wake_words: dict[str, str]) -> None:
        """
        Register wake words and their personality mappings.

        Args:
            wake_words: dict mapping wake word phrase → personality ID.
                        e.g. {"jarvis": "jarvis", "hey devesh": "devesh"}
                        Use "" as personality_id for the system wake word
                        (keeps current personality).
        """
        ...

    @abstractmethod
    def start_listening(self, callback) -> None:
        """
        Start listening for wake words in a background thread.

        Args:
            callback: function(WakeWordDetection) called when a wake word is detected.
                      Called from the listener thread — keep it fast or dispatch.
        """
        ...

    @abstractmethod
    def stop_listening(self) -> None:
        """Stop wake word detection and release mic resources."""
        ...

    @abstractmethod
    def pause_listening(self) -> None:
        """
        Temporarily pause detection (e.g., while recording a command).

        The mic is still held open but detections are suppressed.
        This prevents the assistant from triggering on its own speech.
        """
        ...

    @abstractmethod
    def resume_listening(self) -> None:
        """Resume detection after a pause."""
        ...


class KnowledgeProvider(ABC):
    """
    Interface for external knowledge retrieval — web search, browsing, RSS, local docs.

    This is the layer that gives the assistant access to information beyond the LLM's
    training data. When connected to the internet, this upgrades the assistant from
    a static knowledge base to a live-information system — without changing any other code.

    The core principle: the assistant is LOCAL-FIRST, INTERNET-ENHANCED.
    - Without internet: LLM still works, music fails gracefully, lights work, TTS works.
    - With internet: knowledge queries get real-time answers, chat responses get
      grounded in current facts, and future browse/action capabilities light up.

    How it fits the pipeline:
      1. Brain classifies intent as "knowledge_search" (or "chat" that needs grounding)
      2. KnowledgeProvider.search() fetches relevant context from the web/docs/RSS
      3. Results are injected into the LLM prompt as grounding context
      4. LLM generates a response that's both conversational AND factually current

    This is lightweight RAG (Retrieval-Augmented Generation):
      RAG is a technique where you "retrieve" relevant documents/snippets and "augment"
      the LLM's prompt with them before "generating" a response. The LLM doesn't need
      to have memorized the information — it just needs to read and summarize what you
      give it. This is how ChatGPT's browsing mode works, how Perplexity works, and
      how enterprise AI assistants ground their answers in company docs.

      For a 3B model on edge hardware, keep retrieved context SHORT (under 500 tokens).
      The KV cache (the model's working memory during inference) grows linearly with
      input length, and on Jetson's 8GB shared memory, a 3B model at INT8 already uses
      ~3GB for weights. Long context = more VRAM for KV cache = less room for everything
      else. The max_results and content truncation in SearchResult keep this in check.

    Capability levels (implementations can support one or more):
      Level 1 — Search: query → list of results with snippets (DuckDuckGo, SearXNG)
      Level 2 — Fetch: retrieve full page content from a URL (readability extraction)
      Level 3 — Browse: navigate, interact, fill forms, take actions on websites

    Current implementations: DuckDuckGo (Level 1 — search only, no API key needed)
    Possible future implementations:
      - SearXNG (self-hosted search aggregator — fully local, no API key)
      - Google Custom Search (API key needed, better results)
      - Tavily (AI-optimized search API, returns clean snippets)
      - Brave Search API (privacy-focused, good for grounding)
      - Local docs (search PDFs, notes, bookmarks on device)
      - RSS feed aggregator (cached news, works offline after initial fetch)
      - Browser agent (Playwright/Selenium — Level 3, full web interaction)
    """

    @abstractmethod
    def search(self, query: str, max_results: int = 3) -> list["SearchResult"]:
        """
        Search for information matching a query.

        Returns a list of SearchResult objects with titles, snippets, and URLs.
        Implementations should handle their own error cases (network down, rate
        limited, etc.) and return an empty list on failure — never raise.

        max_results: Keep this LOW for edge hardware. Each result's snippet gets
        injected into the LLM prompt, eating into the context window. 3 results
        with 100-word snippets ≈ 400 tokens — reasonable for a 3B model.
        """
        ...

    @abstractmethod
    def fetch(self, url: str) -> Optional["SearchResult"]:
        """
        Fetch and extract readable content from a URL.

        Level 2 capability — not all implementations need to support this.
        Returns None if not supported or if the fetch fails.

        For implementations that DO support this: extract the main article text,
        strip navigation/ads/boilerplate. Libraries like readability-lxml,
        trafilatura, or newspaper3k are good at this.
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if this provider can currently serve requests.

        For web-based providers: checks internet connectivity.
        For local providers (RSS cache, local docs): always True.

        The assistant uses this to decide whether to attempt knowledge queries
        or fall back to pure LLM responses. This is checked lazily (on first
        knowledge query), not at startup — so a flaky connection doesn't block boot.
        """
        ...

    @property
    def capabilities(self) -> list[str]:
        """
        What this provider can do: ["search"], ["search", "fetch"], or
        ["search", "fetch", "browse"].

        The brain uses this to decide what to ask for. A search-only provider
        gets simple queries. A browse-capable provider can be asked to fill
        forms, check prices, etc.
        """
        return ["search"]


class MemoryProvider(ABC):
    """
    Interface for persistent memory — interaction logging, facts, and recall.

    The memory system is how Jarvis goes from a stateless command processor
    to something that actually knows you. Every interaction gets logged,
    and over time patterns emerge: music taste, routines, preferences.

    v1 (this interface): interaction logging + keyword recall
    v2 (future): semantic search with embeddings, stored facts
    v3 (future): multi-user with access control, per-user encryption
    v4 (future): speaker recognition integration
    v5 (future): automatic preference inference from interaction patterns

    Why an ABC and not just a class?
      Same reason as every other provider — you might want to swap SQLite
      for PostgreSQL, or a vector DB, or even a cloud-synced store later.
      The rest of the codebase doesn't care how memories are stored.

    Current implementations: SQLite (local, zero dependencies)
    Possible future implementations: PostgreSQL, ChromaDB, LanceDB, etc.
    """

    @abstractmethod
    def log_interaction(self, interaction: Interaction) -> int:
        """
        Log a complete interaction (input → intents → response → outcome).

        Returns the interaction ID (for linking feedback later).
        """
        ...

    @abstractmethod
    def recall(self, query: str, user_id: str = "default",
               limit: int = 5) -> list[Memory]:
        """
        Search memory for interactions relevant to a query.

        v1: keyword search (SQL LIKE)
        v2+: semantic similarity search via embeddings

        Examples:
          recall("what did I play yesterday") → recent music_play interactions
          recall("Sajni") → all interactions mentioning Sajni
          recall("lights") → recent light_control interactions
        """
        ...

    @abstractmethod
    def get_recent(self, user_id: str = "default",
                   limit: int = 10) -> list[Memory]:
        """
        Get the N most recent interactions. No search, just chronological.

        Useful for: "what did I just ask?", building context windows,
        and the debug UI showing interaction history.
        """
        ...

    @abstractmethod
    def get_stats(self, user_id: str = "default") -> dict:
        """
        Get summary statistics about stored memories.

        Returns: {"total_interactions": 142, "first_interaction": "2026-03-26T...",
                  "top_intents": {"music_play": 80, "chat": 30, ...}, ...}
        """
        ...
