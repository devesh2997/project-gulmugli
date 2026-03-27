"""
Provider Registry — the glue between config.yaml and actual implementations.

This is where "provider: youtube_music" in config.yaml gets mapped to
the actual YouTubeMusicProvider class.

To add a new provider:
  1. Write a class that implements the relevant interface (e.g., MusicProvider)
  2. Register it here with @register("category", "name")
  3. Set the name in config.yaml

That's it. No other code changes needed.
"""

from core.interfaces import (
    AudioOutputProvider,
    BrainProvider,
    MusicProvider,
    LightProvider,
    EarsProvider,
    VoiceProvider,
    WakeWordProvider,
    MemoryProvider,
    KnowledgeProvider,
    QuizProvider,
)

# ═══════════════════════════════════════════════════════════════
# Registry storage
# ═══════════════════════════════════════════════════════════════

_registry: dict[str, dict[str, type]] = {
    "audio": {},
    "brain": {},
    "music": {},
    "lights": {},
    "ears": {},
    "voice": {},
    "wake_word": {},
    "memory": {},
    "knowledge": {},
    "quiz": {},
}


def register(category: str, name: str):
    """
    Decorator to register a provider implementation.

    Usage:
        @register("music", "youtube_music")
        class YouTubeMusicProvider(MusicProvider):
            ...

        @register("brain", "ollama")
        class OllamaBrainProvider(BrainProvider):
            ...
    """
    def decorator(cls):
        if category not in _registry:
            raise ValueError(f"Unknown category: {category}. Must be one of: {list(_registry.keys())}")
        _registry[category][name] = cls
        return cls
    return decorator


def get_provider(category: str, name: str, **kwargs):
    """
    Instantiate a registered provider by category and name.

    Usage:
        brain = get_provider("brain", "ollama", model="llama3.2:3b", endpoint="http://localhost:11434")
        music = get_provider("music", "youtube_music")
    """
    if category not in _registry:
        raise ValueError(f"Unknown category: {category}")

    if name not in _registry[category]:
        available = list(_registry[category].keys())
        raise ValueError(
            f"No '{name}' provider registered for '{category}'. "
            f"Available: {available}. "
            f"Did you forget to import the provider module?"
        )

    cls = _registry[category][name]
    return cls(**kwargs)


def list_providers(category: str = None) -> dict:
    """List all registered providers, optionally filtered by category."""
    if category:
        return {category: list(_registry.get(category, {}).keys())}
    return {cat: list(providers.keys()) for cat, providers in _registry.items()}
