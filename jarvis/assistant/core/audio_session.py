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
from typing import Any, Optional

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
        audio_provider: Any = None,
        output_priority: Optional[list] = None,
        input_priority: Optional[list] = None,
        override_store: Any = None,
    ):
        self._preferred_mac = (preferred_mac or "").strip()
        self._device_name = (device_name or self._preferred_mac).strip()
        self._auto_reconnect = bool(auto_reconnect)
        self._interval_s = max(self.MIN_INTERVAL_S, int(reconnect_interval_s))

        # Device resolver bits — the audio provider (PulseAudio / CoreAudio /
        # ALSA), the ordered priority lists from config, and the persistent
        # user-override store the dashboard mutates via the API. All three
        # are optional: with no audio provider OR no priority lists, the
        # resolver no-ops and only the BT reconnect tick runs.
        self._audio = audio_provider
        self._output_priority = list(output_priority or [])
        self._input_priority = list(input_priority or [])
        self._override_store = override_store

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
        """
        Spawn the daemon thread. No-op if not configured or already running.

        The daemon runs when EITHER (a) a preferred Bluetooth MAC is set
        AND auto_reconnect is on, OR (b) the device resolver has something
        to do (an audio provider + at least one priority list OR an
        override store). Routing-only deployments (no preferred BT speaker
        but USB/HDMI priority rules) still get auto-routing this way.
        """
        wants_bt = bool(self._preferred_mac) and self._auto_reconnect
        wants_resolver = self._audio is not None and (
            self._output_priority or self._input_priority or self._override_store is not None
        )
        if not wants_bt and not wants_resolver:
            if not self._preferred_mac:
                log.info("AudioSession: no preferred_mac and no resolver config; daemon inert.")
            else:
                log.info(
                    "AudioSession: auto_reconnect=false and no resolver config; "
                    "daemon will not be started (preferred_mac=%s)",
                    self._preferred_mac,
                )
            return

        # Run an initial resolution synchronously BEFORE spawning the thread
        # so devices route correctly within seconds of startup — the dashboard
        # picks up the right active device on first poll, rather than waiting
        # for the first tick interval.
        if wants_resolver:
            try:
                self.apply_resolution()
            except Exception as e:
                log.warning("AudioSession: initial apply_resolution failed: %s", e)

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
            "AudioSession: started — preferred=%s (%s), interval=%ds, "
            "resolver=%s",
            self._preferred_mac or "<none>",
            self._device_name or "unnamed",
            self._interval_s,
            "on" if wants_resolver else "off",
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
            base = {
                "connected": self._connected,
                "preferred_mac": self._preferred_mac,
                "device_name": self._device_name,
                "auto_reconnect": self._auto_reconnect,
                "interval_s": self._interval_s,
                "last_attempt_ts": self._last_attempt_ts,
                "last_error": self._last_error,
                "running": self.is_running(),
            }
        # Resolver state (read outside the lock — the audio provider
        # and override store have their own thread-safety).
        base["resolver_enabled"] = self._audio is not None and (
            bool(self._output_priority) or bool(self._input_priority)
            or self._override_store is not None
        )
        return base

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
        """
        One iteration: BT reconnect (if configured) + device resolver.

        ORDER MATTERS: BT reconnect runs FIRST. If the preferred Bluetooth
        speaker is currently disconnected and we successfully reconnect it
        in this tick, the freshly-connected `bluez_sink` only appears in
        the `pactl list sinks` output AFTER the reconnect succeeds. Running
        the resolver first would miss it and fall through to the next
        priority entry; running it second catches it on the same tick.
        """
        self._tick_bluetooth()
        # Resolver runs every tick regardless of whether BT is configured.
        # It's cheap (one `pactl list sinks` if PulseAudio, returns fast
        # when nothing changed thanks to the idempotency check inside
        # apply_resolution).
        if self._audio is not None and (
            self._output_priority or self._input_priority or self._override_store is not None
        ):
            try:
                self.apply_resolution()
            except Exception as e:
                log.debug("AudioSession: apply_resolution failed: %s", e)

    def _tick_bluetooth(self) -> None:
        """The existing BT reconnect logic, factored out so the resolver
        can run alongside it without entangling the two flows."""
        if not self._preferred_mac:
            # No BT configured — resolver-only deployment.
            return
        if not self._auto_reconnect:
            return

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

    # ── Device resolver ──────────────────────────────────────────────
    #
    # The resolver answers: "given the priority list + override store +
    # the live list of available devices, which device SHOULD be the
    # system default right now?". It does NOT itself flip the system
    # default — `apply_resolution()` does that, and only when the chosen
    # device differs from the currently-active one (idempotency).
    #
    # Priority entry forms:
    #   {"mac": "AA:BB:..."}    — match a Bluetooth device by MAC. PA
    #                              names bluez devices like
    #                              `bluez_sink.AA_BB_CC_DD_EE_FF.a2dp_sink`,
    #                              so we substring-match the MAC with
    #                              colons replaced by underscores. The
    #                              MAC compare is CASE-INSENSITIVE because
    #                              PulseAudio uppercases the bytes but
    #                              users will write the MAC any way they
    #                              feel like in config.yaml.
    #   {"name_pattern": "USB"} — case-insensitive substring match on the
    #                              full device name (sink/source name).
    #   "system_default"        — literal sentinel: always matches the
    #                              first device in the list. PulseAudio
    #                              returns devices ordered by sink index,
    #                              and index 0 is the system default in
    #                              practice. This sentinel CANNOT fail —
    #                              if there are zero devices the resolver
    #                              returns (None, "default") and skips
    #                              the switch.

    def resolve_output(self) -> tuple[Optional[str], str]:
        """
        Resolve the desired output device, returning (device_name, source).

        Source is one of:
          "override" — user explicitly pinned this device (and it's
                       currently available).
          "priority" — matched a config priority entry.
          "default"  — fell through to the system default (the first
                       available device).
          And (None, "default") when the audio provider is missing or
          returned an empty device list.
        """
        if self._audio is None or not hasattr(self._audio, "list_outputs"):
            return None, "default"
        try:
            devices = self._audio.list_outputs() or []
        except Exception as e:
            log.debug("AudioSession: list_outputs failed: %s", e)
            return None, "default"
        return _resolve_device(
            devices=devices,
            priority=self._output_priority,
            override=self._override_get("output"),
        )

    def resolve_input(self) -> tuple[Optional[str], str]:
        """Resolve the desired input (microphone) device. Same shape as
        resolve_output."""
        if self._audio is None or not hasattr(self._audio, "list_inputs"):
            return None, "default"
        try:
            devices = self._audio.list_inputs() or []
        except Exception as e:
            log.debug("AudioSession: list_inputs failed: %s", e)
            return None, "default"
        return _resolve_device(
            devices=devices,
            priority=self._input_priority,
            override=self._override_get("input"),
        )

    def apply_resolution(self) -> dict:
        """
        Resolve + switch (if needed). Returns a structured report so the
        API endpoint and tests can see what happened.

        Idempotency: when the chosen device equals the currently-active
        device (the one with `active: True` in list_outputs), we do NOT
        call set_default_output. Same for input.

        Safe to call repeatedly. Logs INFO when something switches,
        DEBUG when nothing did.
        """
        result = {
            "output": {"name": None, "source": "default", "switched": False},
            "input": {"name": None, "source": "default", "switched": False},
        }

        if self._audio is None:
            return result

        # ── Output side ────────────────────────────────────────────
        out_name, out_source = self.resolve_output()
        result["output"]["name"] = out_name
        result["output"]["source"] = out_source
        if out_name:
            active = _active_device(self._audio, "list_outputs")
            if active != out_name:
                if hasattr(self._audio, "set_default_output"):
                    try:
                        self._audio.set_default_output(out_name)
                        result["output"]["switched"] = True
                        log.info(
                            "AudioSession: switched default output to %s (source=%s, was=%s)",
                            out_name, out_source, active or "<unknown>",
                        )
                    except Exception as e:
                        log.warning(
                            "AudioSession: set_default_output(%s) failed: %s",
                            out_name, e,
                        )
            else:
                log.debug(
                    "AudioSession: output already on %s (source=%s); no switch.",
                    out_name, out_source,
                )

        # ── Input side ─────────────────────────────────────────────
        in_name, in_source = self.resolve_input()
        result["input"]["name"] = in_name
        result["input"]["source"] = in_source
        if in_name:
            active = _active_device(self._audio, "list_inputs")
            # PulseAudio's get_default_source is more authoritative than
            # the "active=True" flag for sources (sources are RUNNING
            # only while something is recording). Prefer it when present.
            if hasattr(self._audio, "get_default_input"):
                try:
                    current = self._audio.get_default_input()
                    if current:
                        active = current
                except Exception:
                    pass
            if active != in_name:
                if hasattr(self._audio, "set_default_input"):
                    try:
                        self._audio.set_default_input(in_name)
                        result["input"]["switched"] = True
                        log.info(
                            "AudioSession: switched default input to %s (source=%s, was=%s)",
                            in_name, in_source, active or "<unknown>",
                        )
                    except Exception as e:
                        log.warning(
                            "AudioSession: set_default_input(%s) failed: %s",
                            in_name, e,
                        )
            else:
                log.debug(
                    "AudioSession: input already on %s (source=%s); no switch.",
                    in_name, in_source,
                )

        # ── Bluetooth A2DP ↔ HFP profile reconciliation ──────────────
        # MUST be the LAST step: a successful profile switch causes
        # PulseAudio to rename the very sinks/sources we just selected
        # (e.g. `bluez_sink.AA_BB.a2dp_sink` becomes
        # `bluez_sink.AA_BB.headset_head_unit`). We don't chase the
        # rename here — the next tick re-resolves and reconciles.
        try:
            self._ensure_correct_bt_profile(out_name, in_name)
        except Exception as e:
            log.debug("AudioSession: _ensure_correct_bt_profile failed: %s", e)

        return result

    def _ensure_correct_bt_profile(
        self,
        chosen_output: Optional[str],
        chosen_input: Optional[str],
    ) -> None:
        """
        Switch the BT card to the correct profile based on whether the
        chosen input is on the same BT card as the chosen output.

        Logic:
          - If chosen_output is a bluez sink AND chosen_input is a bluez
            source on the SAME card → desired profile = headset_head_unit
          - Else if chosen_output is a bluez sink → desired profile = a2dp_sink
          - Else: no BT card involved, no profile switch.

        Note: a successful profile switch causes PulseAudio to rename
        the sinks/sources owned by the card. We don't try to chase the
        rename here — the next apply_resolution tick re-resolves
        against the new device names and reconciles.

        Defensive: any AttributeError / missing method on the audio
        provider yields a silent no-op (lets providers without profile
        support — CoreAudio, ALSA — coexist without try/except
        scaffolding on the caller side).
        """
        if not chosen_output or "bluez_sink" not in chosen_output:
            return
        if self._audio is None:
            return

        get_card = getattr(self._audio, "get_card_for_device", None)
        set_profile = getattr(self._audio, "set_card_profile", None)
        if not callable(get_card) or not callable(set_profile):
            return

        try:
            out_card = get_card(chosen_output)
        except Exception as e:
            log.debug("get_card_for_device(%s) raised: %s", chosen_output, e)
            return
        if not out_card:
            return

        in_card = None
        if chosen_input:
            try:
                in_card = get_card(chosen_input)
            except Exception as e:
                log.debug("get_card_for_device(%s) raised: %s", chosen_input, e)

        if in_card == out_card:
            desired_profile = "headset_head_unit"
        else:
            desired_profile = "a2dp_sink"

        try:
            set_profile(out_card, desired_profile)
        except Exception as e:
            log.warning(
                "set_card_profile(%s, %s) failed: %s",
                out_card, desired_profile, e,
            )

    def list_devices_with_state(self) -> dict:
        """
        Used by the dashboard. Returns a structured snapshot of every
        available output/input plus the override state and which device
        the resolver currently considers "selected" (with the source).
        """
        out_name, out_source = self.resolve_output()
        in_name, in_source = self.resolve_input()
        override = self._override_get_all()

        outputs = _annotate(
            self._safe_call(self._audio, "list_outputs"),
            priority=self._output_priority,
            chosen_name=out_name,
            chosen_source=out_source,
        )
        inputs = _annotate(
            self._safe_call(self._audio, "list_inputs"),
            priority=self._input_priority,
            chosen_name=in_name,
            chosen_source=in_source,
        )

        return {
            "outputs": outputs,
            "inputs": inputs,
            "override": override,
        }

    # ── Override-store helpers (None-safe) ──────────────────────────

    def _override_get(self, side: str) -> Optional[str]:
        if self._override_store is None:
            return None
        try:
            return (self._override_store.get() or {}).get(side)
        except Exception as e:
            log.debug("AudioSession: override store get failed: %s", e)
            return None

    def _override_get_all(self) -> dict:
        if self._override_store is None:
            return {"output": None, "input": None}
        try:
            data = self._override_store.get() or {}
            return {"output": data.get("output"), "input": data.get("input")}
        except Exception:
            return {"output": None, "input": None}

    @staticmethod
    def _safe_call(audio: Any, method: str) -> list:
        if audio is None or not hasattr(audio, method):
            return []
        try:
            return list(getattr(audio, method)() or [])
        except Exception:
            return []


# ── Module-level helpers (pure functions — easier to test) ──────────


def _matches(entry: Any, device_name: str) -> bool:
    """
    Does a priority entry match a device by name?

    Accepted entry shapes:
      - {"mac": "AA:BB:..."}     — Bluetooth MAC, colons→underscores,
                                    case-insensitive substring match.
      - {"name_pattern": "USB"}  — case-insensitive substring of device name.
      - "system_default"          — handled by the caller (always matches
                                    the first device), so this returns False.

    Anything else logs at DEBUG and returns False — we don't crash a
    config typo into a broken resolver.
    """
    if entry == "system_default":
        return False  # caller handles this sentinel
    if not isinstance(entry, dict):
        return False
    name_lc = (device_name or "").lower()
    if "mac" in entry:
        mac = (entry.get("mac") or "").strip()
        if not mac:
            return False
        needle = mac.replace(":", "_").lower()
        return needle in name_lc
    if "name_pattern" in entry:
        pat = (entry.get("name_pattern") or "").strip()
        if not pat:
            return False
        return pat.lower() in name_lc
    return False


def _label_for(entry: Any) -> str:
    """Pull the friendly label out of a priority entry, falling back to a
    sensible default. Used for dashboard display."""
    if entry == "system_default":
        return "System default"
    if isinstance(entry, dict):
        label = entry.get("label")
        if label:
            return str(label)
        if "mac" in entry:
            return str(entry.get("mac") or "Bluetooth device")
        if "name_pattern" in entry:
            return str(entry.get("name_pattern") or "Audio device")
    return "Audio device"


def _resolve_device(
    devices: list,
    priority: list,
    override: Optional[str],
) -> tuple[Optional[str], str]:
    """
    Pure resolver: given the live device list, the priority list, and
    the override (or None), return (chosen_name, source).
    """
    if not devices:
        return None, "default"
    names = [d.get("name") for d in devices if isinstance(d, dict) and d.get("name")]

    # 1) Override wins if the named device is currently available.
    if override:
        for n in names:
            if n == override:
                return n, "override"
        # Override device not currently available — fall through to priority.

    # 2) Walk the priority list, first match wins.
    for entry in priority:
        if entry == "system_default":
            # Sentinel: first device in the list IS the system default.
            return names[0], "priority"
        for n in names:
            if _matches(entry, n):
                return n, "priority"

    # 3) Nothing matched — system default fallback.
    return names[0], "default"


def _active_device(audio: Any, list_method: str) -> Optional[str]:
    """Read the currently-active device name from the audio provider."""
    if audio is None or not hasattr(audio, list_method):
        return None
    try:
        devices = getattr(audio, list_method)() or []
    except Exception:
        return None
    for d in devices:
        if isinstance(d, dict) and d.get("active"):
            return d.get("name")
    return None


def _annotate(
    devices: list,
    priority: list,
    chosen_name: Optional[str],
    chosen_source: str,
) -> list[dict]:
    """
    Decorate each device dict with priority-list label + index +
    selection_source. Returns a NEW list of dicts (doesn't mutate input).
    """
    out: list[dict] = []
    for d in devices:
        if not isinstance(d, dict):
            continue
        name = d.get("name", "")
        label = None
        priority_index = None
        for i, entry in enumerate(priority):
            if entry == "system_default":
                # `system_default` doesn't pin to a specific device, so
                # don't label any device with it — it's a fallthrough.
                continue
            if _matches(entry, name):
                label = _label_for(entry)
                priority_index = i
                break

        # Determine this device's selection_source. Only the chosen
        # device gets the resolver's source string; everything else is
        # tagged as the fallback "default" (i.e., not currently selected).
        if name == chosen_name:
            selection_source = chosen_source
        else:
            selection_source = "default"

        out.append({
            "name": name,
            "label": label,
            "type": d.get("type", "unknown"),
            "available": True,           # if it's in the list, it's available
            "active": bool(d.get("active", False)),
            "selection_source": selection_source,
            "priority_index": priority_index,
        })
    return out
