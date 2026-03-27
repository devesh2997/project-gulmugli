"""
Audio Focus Manager — production audio coexistence for a voice assistant.

Problem:
    TTS and music fight over the audio device. On macOS, PortAudio throws
    error -9986 when sounddevice tries to play while mpv has the output.
    On Linux with PulseAudio, both streams can coexist but you want music
    to duck (lower volume) so TTS is clearly audible.

Solution:
    A singleton coordinator that manages audio channels by priority.
    Does NOT mix audio in software — tells mpv to duck or pause when TTS
    needs the device, restores after.

Platform strategy (auto-detected):
    macOS (CoreAudio)    → Pause mpv during TTS (can't mix OutputStream instances)
    Jetson (PulseAudio)  → Duck mpv to ~20% (PulseAudio mixes streams natively)
    Pi (ALSA)            → Pause (default) or duck if PulseAudio present

Usage:
    from core.audio_focus import AudioFocusManager, AudioChannel

    # In a music provider's __init__:
    focus = AudioFocusManager.instance()
    focus.register_channel(
        AudioChannel.MUSIC,
        on_duck=lambda level: set_volume(level),
        on_restore=lambda level: set_volume(level),
        on_pause=lambda: pause(),
        on_resume=lambda: resume(),
        on_get_volume=lambda: get_volume(),
    )

    # When TTS needs the device:
    focus.acquire(AudioChannel.TTS)    # ducks/pauses music
    ... play TTS ...
    focus.release(AudioChannel.TTS)    # restores music
"""

import enum
import platform
import shutil
import threading
import time
from typing import Callable, Optional

from core.config import config
from core.logger import get_logger

log = get_logger("audio.focus")


class AudioChannel(enum.IntEnum):
    """
    Audio channels ordered by priority.

    Higher value = higher priority. When a high-priority channel acquires
    focus, all lower-priority active channels are suppressed (ducked or
    paused depending on platform strategy).
    """
    AMBIENT = 0   # future: background sounds, white noise
    MUSIC = 5     # mpv playback
    TTS = 10      # voice responses (sounddevice / piper / kokoro)
    ALERT = 15    # future: alarms, timers, urgent notifications


class FocusStrategy(enum.Enum):
    """How to suppress a lower-priority channel."""
    PAUSE = "pause"   # stop playback entirely (macOS, ALSA without PulseAudio)
    DUCK = "duck"     # lower volume (PulseAudio — streams can coexist)


class _ChannelState:
    """Internal state for a registered audio channel."""
    __slots__ = (
        "channel", "active", "suppressed",
        "on_duck", "on_restore", "on_pause", "on_resume", "on_get_volume",
        "saved_volume",
    )

    def __init__(
        self,
        channel: AudioChannel,
        on_duck: Optional[Callable[[int], None]] = None,
        on_restore: Optional[Callable[[int], None]] = None,
        on_pause: Optional[Callable[[], None]] = None,
        on_resume: Optional[Callable[[], None]] = None,
        on_get_volume: Optional[Callable[[], int]] = None,
    ):
        self.channel = channel
        self.active = False       # is this channel currently producing audio?
        self.suppressed = False   # has this channel been ducked/paused by a higher-priority channel?
        self.on_duck = on_duck
        self.on_restore = on_restore
        self.on_pause = on_pause
        self.on_resume = on_resume
        self.on_get_volume = on_get_volume
        self.saved_volume: int = 100  # volume to restore after ducking


class AudioFocusManager:
    """
    Singleton coordinator for audio channel priority and coexistence.

    Thread-safe via RLock. All callback invocations are wrapped in
    try/except so a crashing music provider never prevents TTS from playing.
    """

    _instance: Optional["AudioFocusManager"] = None
    _instance_lock = threading.Lock()

    # Watchdog: auto-release focus if held longer than this (seconds)
    _WATCHDOG_TIMEOUT = 30.0

    # CoreAudio settle delay after pausing mpv (seconds)
    _COREAUDIO_SETTLE = 0.1

    @classmethod
    def instance(cls) -> "AudioFocusManager":
        """Get or create the singleton AudioFocusManager."""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._lock = threading.RLock()

        # Registered channels: AudioChannel → _ChannelState
        self._channels: dict[AudioChannel, _ChannelState] = {}

        # Which channels currently hold focus (have acquired and not released)
        self._focus_holders: set[AudioChannel] = set()

        # Watchdog timers: AudioChannel → threading.Timer
        self._watchdogs: dict[AudioChannel, threading.Timer] = {}

        # Detect platform strategy
        self._strategy = self._detect_strategy()
        self._duck_level = self._get_duck_level()

        log.info(
            'AudioFocusManager initialized: strategy="%s", duck_level=%d',
            self._strategy.value, self._duck_level,
        )

    def _detect_strategy(self) -> FocusStrategy:
        """
        Auto-detect the best audio coexistence strategy for this platform.

        Config override: audio.focus.strategy can be "pause", "duck", or "auto".
        """
        focus_cfg = config.get("audio", {}).get("focus", {})
        strategy_str = focus_cfg.get("strategy", "auto")

        if strategy_str == "pause":
            log.debug("Strategy forced to PAUSE by config.")
            return FocusStrategy.PAUSE
        if strategy_str == "duck":
            log.debug("Strategy forced to DUCK by config.")
            return FocusStrategy.DUCK

        # Auto-detect
        system = platform.system()
        if system == "Darwin":
            log.debug("macOS detected — using PAUSE strategy (CoreAudio can't mix streams).")
            return FocusStrategy.PAUSE

        # Linux: check for PulseAudio
        if shutil.which("pactl"):
            log.debug("PulseAudio detected (pactl found) — using DUCK strategy.")
            return FocusStrategy.DUCK

        log.debug("No PulseAudio detected — using PAUSE strategy (ALSA default).")
        return FocusStrategy.PAUSE

    def _get_duck_level(self) -> int:
        """Read duck volume level from config (0-100, default 20)."""
        focus_cfg = config.get("audio", {}).get("focus", {})
        level = focus_cfg.get("duck_level", 20)
        return max(0, min(100, int(level)))

    @property
    def strategy(self) -> FocusStrategy:
        """The active focus strategy."""
        return self._strategy

    # ──────────────────────────────────────────────────────────────
    # Channel registration
    # ──────────────────────────────────────────────────────────────

    def register_channel(
        self,
        channel: AudioChannel,
        on_duck: Optional[Callable[[int], None]] = None,
        on_restore: Optional[Callable[[int], None]] = None,
        on_pause: Optional[Callable[[], None]] = None,
        on_resume: Optional[Callable[[], None]] = None,
        on_get_volume: Optional[Callable[[], int]] = None,
    ) -> None:
        """
        Register an audio channel with its control callbacks.

        Args:
            channel: The audio channel to register.
            on_duck: Called with target volume level (0-100) when ducking.
            on_restore: Called with original volume level when restoring from duck.
            on_pause: Called to pause the channel's audio output.
            on_resume: Called to resume the channel's audio output.
            on_get_volume: Called to query current volume (used to save before ducking).
        """
        with self._lock:
            self._channels[channel] = _ChannelState(
                channel=channel,
                on_duck=on_duck,
                on_restore=on_restore,
                on_pause=on_pause,
                on_resume=on_resume,
                on_get_volume=on_get_volume,
            )
            log.debug("Registered channel: %s", channel.name)

    def set_channel_active(self, channel: AudioChannel, active: bool) -> None:
        """
        Report that a channel has started or stopped producing audio.

        Only active channels are suppressed when a higher-priority channel
        acquires focus. If music isn't playing, acquiring TTS focus is a no-op
        for the MUSIC channel.
        """
        with self._lock:
            state = self._channels.get(channel)
            if state is None:
                log.debug("set_channel_active for unregistered channel %s — ignoring.", channel.name)
                return

            old_active = state.active
            state.active = active
            if old_active != active:
                log.debug("Channel %s active: %s → %s", channel.name, old_active, active)

    # ──────────────────────────────────────────────────────────────
    # Focus acquire / release
    # ──────────────────────────────────────────────────────────────

    def acquire(self, channel: AudioChannel) -> None:
        """
        Acquire audio focus for the given channel.

        Suppresses (ducks or pauses) all lower-priority channels that are
        currently active. If this channel already holds focus, this is a no-op
        (reentrant safe via RLock).
        """
        with self._lock:
            if channel in self._focus_holders:
                log.debug("Channel %s already holds focus — no-op acquire.", channel.name)
                return

            self._focus_holders.add(channel)
            log.debug("Channel %s acquiring focus.", channel.name)

            # Suppress all lower-priority active channels
            suppressed_any = False
            for ch, state in self._channels.items():
                if ch < channel and state.active and not state.suppressed:
                    self._suppress_channel(state)
                    suppressed_any = True

            # On macOS, CoreAudio needs a moment to release the device
            # after mpv pauses. Without this, sounddevice.play() can still
            # fail with error -9986.
            if suppressed_any and self._strategy == FocusStrategy.PAUSE:
                if platform.system() == "Darwin":
                    log.debug(
                        "CoreAudio settle delay: %.0fms",
                        self._COREAUDIO_SETTLE * 1000,
                    )
                    time.sleep(self._COREAUDIO_SETTLE)

            # Start watchdog timer
            self._start_watchdog(channel)

    def release(self, channel: AudioChannel) -> None:
        """
        Release audio focus for the given channel.

        Restores all channels that were suppressed by this channel, as long
        as no other higher-priority channel still holds focus.
        """
        with self._lock:
            if channel not in self._focus_holders:
                log.debug("Channel %s doesn't hold focus — no-op release.", channel.name)
                return

            self._focus_holders.discard(channel)
            self._cancel_watchdog(channel)
            log.debug("Channel %s released focus.", channel.name)

            # Find the highest remaining focus holder
            max_holder = max(self._focus_holders) if self._focus_holders else None

            # Restore channels that are suppressed and no longer outranked
            for ch, state in self._channels.items():
                if state.suppressed:
                    # Only restore if no remaining focus holder outranks this channel
                    if max_holder is None or ch >= max_holder:
                        self._restore_channel(state)

    def is_active(self, channel: AudioChannel) -> bool:
        """Check if a channel currently holds focus."""
        with self._lock:
            return channel in self._focus_holders

    # ──────────────────────────────────────────────────────────────
    # Internal: suppress / restore
    # ──────────────────────────────────────────────────────────────

    def _suppress_channel(self, state: _ChannelState) -> None:
        """Duck or pause a channel based on the current strategy."""
        state.suppressed = True

        if self._strategy == FocusStrategy.DUCK:
            # Save current volume, then duck
            if state.on_get_volume:
                try:
                    vol = state.on_get_volume()
                    if vol is not None:
                        state.saved_volume = vol
                except Exception as e:
                    log.warning("Failed to get volume for %s: %s", state.channel.name, e)

            if state.on_duck:
                try:
                    log.debug(
                        "Ducking %s: %d → %d",
                        state.channel.name, state.saved_volume, self._duck_level,
                    )
                    state.on_duck(self._duck_level)
                except Exception as e:
                    log.warning("Duck callback failed for %s: %s", state.channel.name, e)
        else:
            # Pause strategy
            if state.on_pause:
                try:
                    log.debug("Pausing %s for higher-priority audio.", state.channel.name)
                    state.on_pause()
                except Exception as e:
                    log.warning("Pause callback failed for %s: %s", state.channel.name, e)

    def _restore_channel(self, state: _ChannelState) -> None:
        """Restore a previously suppressed channel."""
        state.suppressed = False

        if self._strategy == FocusStrategy.DUCK:
            if state.on_restore:
                try:
                    log.debug(
                        "Restoring %s volume: %d → %d",
                        state.channel.name, self._duck_level, state.saved_volume,
                    )
                    state.on_restore(state.saved_volume)
                except Exception as e:
                    log.warning("Restore callback failed for %s: %s", state.channel.name, e)
        else:
            # Resume from pause
            if state.on_resume:
                try:
                    log.debug("Resuming %s after higher-priority audio.", state.channel.name)
                    state.on_resume()
                except Exception as e:
                    log.warning("Resume callback failed for %s: %s", state.channel.name, e)

    # ──────────────────────────────────────────────────────────────
    # Watchdog: auto-release stuck focus
    # ──────────────────────────────────────────────────────────────

    def _start_watchdog(self, channel: AudioChannel) -> None:
        """Start a timer that auto-releases focus if held too long."""
        self._cancel_watchdog(channel)

        def _watchdog_expired():
            log.warning(
                "WATCHDOG: Channel %s held focus for >%.0fs — auto-releasing!",
                channel.name, self._WATCHDOG_TIMEOUT,
            )
            self.release(channel)

        timer = threading.Timer(self._WATCHDOG_TIMEOUT, _watchdog_expired)
        timer.daemon = True
        timer.name = f"focus-watchdog-{channel.name}"
        timer.start()
        self._watchdogs[channel] = timer

    def _cancel_watchdog(self, channel: AudioChannel) -> None:
        """Cancel the watchdog timer for a channel."""
        timer = self._watchdogs.pop(channel, None)
        if timer is not None:
            timer.cancel()
