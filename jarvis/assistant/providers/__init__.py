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

# As you add more providers, import them here:
# from providers.music.spotify import SpotifyMusicProvider
# from providers.brain.llamacpp import LlamaCppBrainProvider
# from providers.lights.hue import HueLightProvider
# from providers.ears.faster_whisper import FasterWhisperProvider
