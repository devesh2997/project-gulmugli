"""
Audio Session Manager — background Bluetooth speaker auto-reconnect.

## What it does

On assistant startup, attempts to (re)connect to a configured "preferred"
Bluetooth speaker (e.g., the Marshall Willen II). After that, a daemon
thread polls the connection state every `reconnect_interval_s` (default
30s, min 5s). When the speaker is found to be disconnected — because the
user powered it off, walked out of range, paired it to another device
(multi-point), etc. — the loop fires a single `bluetoothctl connect <mac>`
attempt and waits a full interval before trying again.

## Why this is needed

The Marshall Willen II is multi-point (up to two simultaneous source
connections) and shared across the user's laptop, Alexa, phone, and the
Jetson. Disconnect/reconnect churn is routine. BlueZ's automatic
reconnect-on-trust is best-effort and unreliable — an active retry
daemon makes the assistant feel like a real appliance: turn the speaker
on, the music keeps coming back.

## Design choices

- **Polling not events.** D-Bus has signal-based connect/disconnect
  events via `org.bluez.Device1.Connected`, but: (a) bluetoothctl
  doesn't expose them as a simple CLI surface, (b) the polling cadence
  is forgiving (30s default) and the resource cost is negligible
  (one subprocess call per minute), (c) a fresh `bluetoothctl info`
  query is the source of truth — D-Bus state can lie if BlueZ itself
  is wedged.
- **Single attempt per interval.** No tight retry loops. If a connect
  fails because the speaker is genuinely off, retrying every 2s would
  spam the BlueZ stack and burn CPU on the Jetson. One attempt every
  30s recovers within ~30s of the speaker coming back online, which is
  imperceptible in practice.
- **Inert when bluetoothctl absent.** On the Mac dev box, bluetoothctl
  isn't installed (Mac uses blueutil). The manager logs once and stops
  — it does NOT keep polling and spamming the log. This keeps the
  developer experience clean while still letting the daemon path run
  in CI/tests.
- **Don't disconnect on shutdown.** If the Jetson reboots mid-song, we
  want the speaker to remain bonded so the post-boot reconnect attempt
  is fast and clean. Active disconnects in the shutdown hook would
  break that.

## Thread safety

- A single daemon thread runs the loop. `start()` and `stop()` are
  idempotent and guarded by an internal lock.
- `get_status()` reads the status dict under the same lock — values
  are plain primitives, so callers get an immediate snapshot.
- The shutdown signal is a `threading.Event`; calling `stop()` sets
  the event, the loop exits its current `Event.wait()` early, and the
  thread joins. No thread-local state, no inter-thread queues.

## `bluetoothctl info` parsing

`bluetoothctl info <mac>` returns multi-line key:value output:

    Device AA:BB:CC:DD:EE:FF (public)
        Name: Marshall Willen II
        Alias: Marshall Willen II
        Paired: yes
        Trusted: yes
        Blocked: no
        Connected: yes
        ...

We grep for the literal `Connected:` line and check its value. The
parse is deliberately tolerant — case-insensitive, whitespace-tolerant
— because BlueZ versions vary (Jetson Ubuntu 22.04 ships BlueZ 5.64,
Pi OS bookworm 5.66, Debian sid 5.72; output format is stable across
all three, but defensive parsing costs nothing).
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import threading
import time
from typing import Optional

from core.logger import get_logger

log = get_logger("audio_session")


class AudioSessionManager:
    """
    Daemon-thread Bluetooth speaker reconnect service.

    Construct with a preferred MAC (and optional friendly name + interval),
    call `start()` once after the assistant is wired up, and call `stop()`
    on shutdown. If `preferred_mac` is falsy the manager is INERT — no
    thread is spawned and `get_status()` returns an empty-ish dict.
    """

    # Floor for the poll interval. Anything below this would hammer the
    # BlueZ stack and add CPU noise on the Jetson without any UX benefit.
    MIN_INTERVAL_S = 5

    # Connect attempt timeout. BlueZ typically resolves in 2-4s; we give
    # it 10s before declaring the attempt a failure.
    CONNECT_TIMEOUT_S = 10
    INFO_TIMEOUT_S = 5

    def __init__(
        self,
        preferred_mac: str,
        device_name: str = "",
        reconnect_interval_s: int = 30,
        auto_reconnect: bool = True,
    ):
        self._preferred_mac = (preferred_mac or "").strip()
        self._device_name = (device_name or self._preferred_mac).strip()
        self._auto_reconnect = bool(auto_reconnect)
        self._interval_s = max(self.MIN_INTERVAL_S, int(reconnect_interval_s))

        self._stop_event = threading.Event()
        # Wake event lets `force_reconnect()` poke the loop without waiting
        # for the next scheduled interval.
        self._wake_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Status state (read by get_status, written by the loop).
        self._connected: bool = False
        self._last_attempt_ts: float = 0.0
        self._last_error: Optional[str] = None
        # Set true after we log the "bluetoothctl unavailable" message so
        # we don't spam the log every interval on dev machines.
        self._inert_logged: bool = False

    # ── Public lifecycle ────────────────────────────────────────────

    def start(self) -> None:
        """Spawn the daemon thread. No-op if not configured or already running."""
        if not self._preferred_mac:
            log.info("AudioSession: no preferred_mac configured; reconnect daemon inert.")
            return
        if not self._auto_reconnect:
            log.info(
                "AudioSession: auto_reconnect=false; daemon will not be started "
                "(preferred_mac=%s)", self._preferred_mac,
            )
            return
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return  # already running
            self._stop_event.clear()
            self._wake_event.clear()
            self._thread = threading.Thread(
                target=self._loop,
                name="audio-session",
                daemon=True,
            )
            self._thread.start()
        log.info(
            "AudioSession: started — preferred=%s (%s), interval=%ds",
            self._preferred_mac, self._device_name or "unnamed", self._interval_s,
        )

    def stop(self) -> None:
        """Signal the thread to exit and join. Idempotent."""
        self._stop_event.set()
        self._wake_event.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=self.CONNECT_TIMEOUT_S + 2.0)
        log.info("AudioSession: stopped.")

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ── Status API ──────────────────────────────────────────────────

    def get_status(self) -> dict:
        """
        Snapshot of the session manager state.

        Returns a fresh dict each call — callers can mutate freely.
        """
        with self._lock:
            return {
                "connected": self._connected,
                "preferred_mac": self._preferred_mac,
                "device_name": self._device_name,
                "auto_reconnect": self._auto_reconnect,
                "interval_s": self._interval_s,
                "last_attempt_ts": self._last_attempt_ts,
                "last_error": self._last_error,
                "running": self.is_running(),
            }

    # ── Force-reconnect (used by API endpoint) ──────────────────────

    def force_reconnect(self) -> dict:
        """
        Trigger an immediate connect attempt, bypassing the interval wait.

        If the daemon thread is running, we just kick it via `_wake_event`
        so it loops one extra time. If the daemon is NOT running (e.g.,
        inert on Mac, or stopped), we still attempt one synchronous
        connect for the API caller's benefit and return the result.
        """
        if not self._preferred_mac:
            return {"ok": False, "error": "No preferred_mac configured."}

        # If the daemon is running, poking the wake event causes the loop
        # to skip the rest of its sleep and run one tick immediately.
        if self.is_running():
            self._wake_event.set()
            return {"ok": True, "response": "Reconnect attempt scheduled."}

        # Daemon inert or stopped — run one synchronous attempt right here.
        ok = self._attempt_connect()
        return {
            "ok": ok,
            "response": (
                f"Connect attempt to {self._device_name or self._preferred_mac} "
                f"{'succeeded' if ok else 'failed'}."
            ),
        }

    # ── Loop ────────────────────────────────────────────────────────

    def _loop(self) -> None:
        """
        Daemon thread body.

        On Mac (no bluetoothctl), the first tick logs once and the loop
        then idles for the configured interval forever — it doesn't spam,
        but it also doesn't exit, so that a `stop()` always finds a live
        thread to join.
        """
        # Attempt an initial connect at startup so the speaker comes up
        # without waiting for the first interval.
        try:
            self._tick()
        except Exception as e:
            log.warning("AudioSession: initial tick failed: %s", e)

        while not self._stop_event.is_set():
            # Wait the interval OR until the wake event fires.
            # Event.wait() returns True if the event was set during the
            # wait — we treat that as "do another tick now."
            woke_early = self._wake_event.wait(timeout=self._interval_s)
            if woke_early:
                self._wake_event.clear()
            if self._stop_event.is_set():
                break
            try:
                self._tick()
            except Exception as e:
                # Don't let one bad tick kill the daemon — log and keep going.
                log.warning("AudioSession: tick failed: %s", e)

    def _tick(self) -> None:
        """One iteration: check status, reconnect if needed."""
        if not self._is_bluetoothctl_available():
            if not self._inert_logged:
                log.info(
                    "AudioSession: bluetoothctl not available on this platform "
                    "(%s); daemon will idle without acting.", platform.system(),
                )
                self._inert_logged = True
            with self._lock:
                self._last_error = "bluetoothctl-unavailable"
                self._connected = False
            return

        connected = self._query_connected(self._preferred_mac)
        with self._lock:
            self._connected = bool(connected)

        if connected:
            log.debug(
                "AudioSession: %s (%s) is connected.",
                self._preferred_mac, self._device_name or "unnamed",
            )
            return

        # Disconnected. Attempt one reconnect (no tight loop).
        log.info(
            "AudioSession: attempting to connect to %s (%s)...",
            self._preferred_mac, self._device_name or "unnamed",
        )
        ok = self._attempt_connect()
        if ok:
            log.info(
                "AudioSession: connected to %s (%s).",
                self._preferred_mac, self._device_name or "unnamed",
            )
        else:
            log.warning(
                "AudioSession: could not connect to %s (%s); will retry in %ds.",
                self._preferred_mac, self._device_name or "unnamed", self._interval_s,
            )

    # ── Helpers ─────────────────────────────────────────────────────

    def _is_bluetoothctl_available(self) -> bool:
        return shutil.which("bluetoothctl") is not None

    def _query_connected(self, mac: str) -> bool:
        """
        Run `bluetoothctl info <mac>` and parse the `Connected:` line.

        Returns False on any error (subprocess failure, timeout, parse
        miss) — "I couldn't confirm connected" is treated the same as
        "disconnected" so the next attempt will try to reconnect.
        """
        try:
            result = subprocess.run(
                ["bluetoothctl", "info", mac],
                capture_output=True,
                text=True,
                timeout=self.INFO_TIMEOUT_S,
            )
        except subprocess.TimeoutExpired:
            log.debug("AudioSession: bluetoothctl info %s timed out", mac)
            with self._lock:
                self._last_error = "info-timeout"
            return False
        except Exception as e:
            log.debug("AudioSession: bluetoothctl info %s raised: %s", mac, e)
            with self._lock:
                self._last_error = f"info-error: {e}"
            return False

        # bluetoothctl returns rc=0 even for unknown devices on some
        # BlueZ versions, so we don't gate on rc — we parse the output.
        out = (result.stdout or "") + "\n" + (result.stderr or "")
        for raw in out.splitlines():
            line = raw.strip().lower()
            # Tolerant parse: anything starting with "connected:"
            if line.startswith("connected:"):
                value = line.split(":", 1)[1].strip()
                return value.startswith("yes")
        # No `Connected:` line means the device is unknown / never paired.
        # Treat as disconnected so the retry path runs (which will fail
        # cleanly — pairing is out of scope for this manager).
        with self._lock:
            self._last_error = "info-no-connected-line"
        return False

    def _attempt_connect(self) -> bool:
        """Run a single `bluetoothctl connect <mac>` attempt."""
        with self._lock:
            self._last_attempt_ts = time.time()
            self._last_error = None

        if not self._is_bluetoothctl_available():
            with self._lock:
                self._last_error = "bluetoothctl-unavailable"
            return False

        try:
            result = subprocess.run(
                ["bluetoothctl", "connect", self._preferred_mac],
                capture_output=True,
                text=True,
                timeout=self.CONNECT_TIMEOUT_S,
            )
        except subprocess.TimeoutExpired:
            with self._lock:
                self._last_error = "connect-timeout"
            return False
        except Exception as e:
            with self._lock:
                self._last_error = f"connect-error: {e}"
            return False

        combined = (result.stdout or "") + "\n" + (result.stderr or "")
        lc = combined.lower()
        # Success markers BlueZ uses across versions.
        if "connection successful" in lc or "already connected" in lc:
            with self._lock:
                self._connected = True
            return True
        # Failure markers — log the first short reason for the status dict.
        with self._lock:
            self._connected = False
            # Capture a short error reason for the status endpoint.
            for line in combined.splitlines():
                s = line.strip()
                if s.lower().startswith("failed to connect"):
                    self._last_error = s[:160]
                    break
            else:
                self._last_error = "connect-failed"
        return False
