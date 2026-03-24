"""
Personality Manager — loads and switches between assistant personalities.

This is NOT a provider (you don't swap "personality backends"). It's a
config-driven state manager that holds the active personality and feeds
it to the brain, voice, and music systems.

Usage:
    from core.personality import personality_manager

    current = personality_manager.active          # Personality dataclass
    personality_manager.switch("chandler")        # Switch personality
    all_names = personality_manager.list()         # ["jarvis", "devesh", ...]

The active personality affects:
    - Brain: tone/mannerisms injected into the system prompt
    - Voice: TTS voice model changes per personality
    - Music: optional per-personality music taste override
    - Wake word: optional per-personality wake word (future: speaker ID)
"""

from core.config import config
from core.interfaces import Personality
from core.logger import get_logger

log = get_logger("personality")


class PersonalityManager:
    """
    Loads personalities from config.yaml and tracks the active one.

    Config structure:
        personalities:
          default: "jarvis"
          profiles:
            jarvis:
              display_name: "Jarvis"
              description: "Default — helpful, concise, warm"
              tone: "You speak concisely and warmly..."
              voice_model: "en_US-lessac-medium"
            devesh:
              display_name: "Devesh"
              ...
    """

    def __init__(self):
        pcfg = config.get("personalities", {})
        self._profiles: dict[str, Personality] = {}
        self._active_id: str = pcfg.get("default", "default")

        # Load all profiles from config
        for pid, pdata in pcfg.get("profiles", {}).items():
            self._profiles[pid] = Personality(
                id=pid,
                display_name=pdata.get("display_name", pid.title()),
                description=pdata.get("description", ""),
                tone=pdata.get("tone", ""),
                voice_provider=pdata.get("voice_provider", ""),
                voice_model=pdata.get("voice_model", ""),
                fallback_voice=pdata.get("fallback_voice", ""),
                music_preferences=pdata.get("music_preferences", {}),
                wake_word=pdata.get("wake_word", ""),
            )

        # If no personalities defined at all, create a fallback from the
        # old assistant.personality config so everything still works
        if not self._profiles:
            fallback_tone = config.get("assistant", {}).get("personality", "")
            fallback_name = config.get("assistant", {}).get("name", "Assistant")
            self._profiles["default"] = Personality(
                id="default",
                display_name=fallback_name,
                description="Default assistant personality",
                tone=fallback_tone,
                voice_model=config.get("voice", {}).get("model", ""),
            )
            self._active_id = "default"

        # Validate that the default personality exists
        if self._active_id not in self._profiles:
            available = list(self._profiles.keys())
            log.warning(
                'Default personality "%s" not found. Available: %s. Using "%s".',
                self._active_id, available, available[0],
            )
            self._active_id = available[0]

        log.info('Personality: "%s" (%s)', self.active.display_name, self.active.description)

    @property
    def active(self) -> Personality:
        """The currently active personality."""
        return self._profiles[self._active_id]

    def switch(self, personality_id: str) -> Personality:
        """
        Switch to a different personality.

        Returns the new active Personality, or raises KeyError if not found.
        """
        # Fuzzy match: try exact first, then case-insensitive, then display_name
        if personality_id in self._profiles:
            self._active_id = personality_id
        else:
            # Try case-insensitive match on id or display_name
            lower = personality_id.lower()
            match = None
            for pid, p in self._profiles.items():
                if pid.lower() == lower or p.display_name.lower() == lower:
                    match = pid
                    break
            if match:
                self._active_id = match
            else:
                available = [f"{p.display_name} ({pid})" for pid, p in self._profiles.items()]
                raise KeyError(
                    f"No personality '{personality_id}'. Available: {', '.join(available)}"
                )

        log.info('Switched to "%s" (%s)', self.active.display_name, self.active.description)
        return self.active

    def list(self) -> list[Personality]:
        """List all available personalities."""
        return list(self._profiles.values())

    def get(self, personality_id: str) -> Personality | None:
        """Get a personality by ID without switching to it."""
        return self._profiles.get(personality_id)


# ═══════════════════════════════════════════════════════════════
# Singleton — loaded once at import time, like config
# ═══════════════════════════════════════════════════════════════

personality_manager = PersonalityManager()
