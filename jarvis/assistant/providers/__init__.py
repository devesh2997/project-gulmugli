"""
Provider auto-discovery.

Importing this module automatically registers all providers found in
the subdirectories. This is how the registry knows about OllamaBrainProvider,
YouTubeMusicProvider, etc. — each file uses the @register decorator on import.

To add a new provider: just create the file. It gets picked up automatically.
"""

# Import all provider modules so their @register decorators run.
# Each import triggers the decorator which adds the class to the registry.

# Brain providers
from providers.brain.ollama import OllamaBrainProvider

# Music providers
from providers.music.youtube import YouTubeMusicProvider

# Light providers
from providers.lights.tuya import TuyaLightProvider

# Voice providers — optional (TTS libraries may not be installed)
# We catch Exception (not just ImportError) because some packages are
# installed but have broken transitive dependencies (e.g., coqui-tts
# installed without PyTorch raises ImportError deep inside its __init__).
try:
    from providers.voice.piper_tts import PiperVoiceProvider
except Exception:
    pass  # piper-tts not installed or broken

try:
    from providers.voice.kokoro_tts import KokoroVoiceProvider
except Exception:
    pass  # kokoro-onnx not installed

try:
    from providers.voice.edge_tts import EdgeTTSVoiceProvider
except Exception:
    pass  # edge-tts not installed

try:
    from providers.voice.xtts import XTTSVoiceProvider
except Exception:
    pass  # coqui-tts not installed or missing PyTorch

# Ears (STT) providers — optional (whisper model may not be installed)
try:
    from providers.ears.faster_whisper import FasterWhisperProvider
except Exception:
    pass  # faster-whisper not installed

# Memory providers
from providers.memory.sqlite import SQLiteMemoryProvider

# Wake word providers — optional (openwakeword may not be installed)
try:
    from providers.wake_word.openwakeword import OpenWakeWordProvider
except Exception:
    pass  # openwakeword not installed or missing sounddevice

# Knowledge providers — optional (needs internet + duckduckgo_search library)
try:
    from providers.knowledge.duckduckgo import DuckDuckGoKnowledgeProvider
except Exception:
    pass  # duckduckgo_search not installed

# Audio output providers — platform-specific, optional
try:
    from providers.audio.coreaudio import CoreAudioProvider
except Exception:
    pass  # not on macOS or missing osascript

try:
    from providers.audio.pulseaudio import PulseAudioProvider
except Exception:
    pass  # pactl not available

try:
    from providers.audio.alsa import AlsaAudioProvider
except Exception:
    pass  # amixer not available

# Quiz providers
from providers.quiz.trivia import TriviaQuizProvider

# Weather providers — optional (needs internet)
try:
    from providers.weather.openmeteo import OpenMeteoWeatherProvider
except Exception:
    pass  # urllib available everywhere, but import may fail for other reasons

# As you add more providers, import them here:
# from providers.music.spotify import SpotifyMusicProvider
# from providers.brain.llamacpp import LlamaCppBrainProvider
# from providers.lights.hue import HueLightProvider
# from providers.knowledge.searxng import SearXNGKnowledgeProvider
# from providers.knowledge.tavily import TavilyKnowledgeProvider
