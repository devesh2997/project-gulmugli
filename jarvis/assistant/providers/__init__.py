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

# As you add more providers, import them here:
# from providers.music.spotify import SpotifyMusicProvider
# from providers.brain.llamacpp import LlamaCppBrainProvider
# from providers.lights.hue import HueLightProvider
# from providers.ears.faster_whisper import FasterWhisperProvider
# from providers.voice.piper import PiperVoiceProvider
