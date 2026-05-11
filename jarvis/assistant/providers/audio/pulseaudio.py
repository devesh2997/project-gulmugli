"""
PulseAudio provider — system audio control for Linux (Jetson, desktop Linux).

Volume: pactl set-sink-volume / get-sink-volume
Device list: pactl list sinks short
Device switch: pactl set-default-sink
Bluetooth: delegates to BluetoothHelper (uses bluetoothctl).

PulseAudio is the default audio server on most desktop Linux distros
and on Jetson (NVIDIA ships PA pre-configured). PipeWire also exposes
a PulseAudio-compatible interface, so this provider works with PipeWire too.
"""

import re
import shutil
import subprocess
from typing import Optional

from core.interfaces import AudioOutputProvider
from core.logger import get_logger
from core.registry import register
from providers.audio.bluetooth import BluetoothHelper

log = get_logger("audio.pulseaudio")


@register("audio", "pulseaudio")
class PulseAudioProvider(AudioOutputProvider):
    """Linux audio output control via PulseAudio (pactl)."""

    def __init__(self):
        self._bluetooth = BluetoothHelper()

    def is_available(self) -> bool:
        return shutil.which("pactl") is not None

    def set_volume(self, level: int, output: str = "default") -> None:
        """
        Set sink volume 0-100%.

        Uses @DEFAULT_SINK@ when output is "default", otherwise
        treats output as a sink name (from list_outputs).
        """
        level = max(0, min(100, level))
        sink = "@DEFAULT_SINK@" if output == "default" else output
        try:
            subprocess.run(
                ["pactl", "set-sink-volume", sink, f"{level}%"],
                capture_output=True, text=True, timeout=10,
            )
            log.debug("PulseAudio volume set to %d%% on %s", level, sink)
        except subprocess.TimeoutExpired:
            log.warning("pactl set-sink-volume timed out")
        except Exception as e:
            log.error("Failed to set volume: %s", e)

    def get_volume(self, output: str = "default") -> int:
        """
        Get current sink volume 0-100%.

        Parses the percentage from pactl get-sink-volume output:
        "Volume: front-left: 42000 /  64% / -11.78 dB, front-right: ..."
        """
        sink = "@DEFAULT_SINK@" if output == "default" else output
        try:
            result = subprocess.run(
                ["pactl", "get-sink-volume", sink],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                # Extract first percentage value
                match = re.search(r"(\d+)%", result.stdout)
                if match:
                    return int(match.group(1))
        except subprocess.TimeoutExpired:
            log.warning("pactl get-sink-volume timed out")
        except Exception as e:
            log.error("Failed to get volume: %s", e)
        return -1

    def list_outputs(self) -> list[dict]:
        """
        List available audio sinks.

        Uses `pactl list sinks short` for a compact listing:
        "0\\tname\\tmodule\\tsample_spec\\tstate"
        """
        try:
            result = subprocess.run(
                ["pactl", "list", "sinks", "short"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                return []

            outputs = []
            for line in result.stdout.strip().splitlines():
                parts = line.split("\t")
                if len(parts) >= 2:
                    sink_name = parts[1]
                    state = parts[-1] if len(parts) >= 5 else "UNKNOWN"

                    # Infer type from sink name
                    device_type = "system"
                    name_lower = sink_name.lower()
                    if "bluetooth" in name_lower or "bluez" in name_lower:
                        device_type = "bluetooth"
                    elif "hdmi" in name_lower:
                        device_type = "hdmi"
                    elif "usb" in name_lower:
                        device_type = "usb"

                    outputs.append({
                        "name": sink_name,
                        "type": device_type,
                        "active": state == "RUNNING",
                    })
            return outputs

        except subprocess.TimeoutExpired:
            log.warning("pactl list sinks timed out")
        except Exception as e:
            log.error("Failed to list outputs: %s", e)
        return []

    def set_default_output(self, output: str) -> None:
        """
        Switch the default sink.

        Also moves all currently playing streams to the new sink
        so that active audio (music, TTS) switches immediately.
        """
        try:
            result = subprocess.run(
                ["pactl", "set-default-sink", output],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                log.info("Default sink set to: %s", output)
                # Move active streams to new sink
                self._move_streams_to_sink(output)
            else:
                log.warning("Failed to set default sink: %s", result.stderr.strip())
        except subprocess.TimeoutExpired:
            log.warning("pactl set-default-sink timed out")
        except Exception as e:
            log.error("Failed to set default sink: %s", e)

    def _move_streams_to_sink(self, sink_name: str) -> None:
        """Move all active sink-inputs (streams) to the given sink."""
        try:
            # List active streams
            result = subprocess.run(
                ["pactl", "list", "sink-inputs", "short"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                return

            for line in result.stdout.strip().splitlines():
                parts = line.split("\t")
                if parts:
                    stream_id = parts[0]
                    subprocess.run(
                        ["pactl", "move-sink-input", stream_id, sink_name],
                        capture_output=True, text=True, timeout=5,
                    )
        except Exception as e:
            log.debug("Could not move streams to new sink: %s", e)

    # ── Inputs (microphones) ─────────────────────────────────────

    def list_inputs(self) -> list[dict]:
        """
        List available audio sources (microphones, line-in, USB capture).

        Filters out monitor sources (sinks-as-sources for loopback recording)
        which aren't real microphones — their names contain ".monitor".

        Same parsing as list_outputs but against `pactl list sources short`.
        """
        try:
            result = subprocess.run(
                ["pactl", "list", "sources", "short"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                return []

            inputs = []
            for line in result.stdout.strip().splitlines():
                parts = line.split("\t")
                if len(parts) < 2:
                    continue
                source_name = parts[1]

                # Skip monitor sources (loopback of sinks, not real mics)
                if ".monitor" in source_name:
                    continue

                state = parts[-1] if len(parts) >= 5 else "UNKNOWN"

                # Infer type from source name
                device_type = "system"
                name_lower = source_name.lower()
                if "bluetooth" in name_lower or "bluez" in name_lower:
                    device_type = "bluetooth"
                elif "hdmi" in name_lower:
                    device_type = "hdmi"
                elif "usb" in name_lower:
                    device_type = "usb"

                inputs.append({
                    "name": source_name,
                    "type": device_type,
                    "active": state == "RUNNING",
                })
            return inputs

        except subprocess.TimeoutExpired:
            log.warning("pactl list sources timed out")
        except Exception as e:
            log.error("Failed to list inputs: %s", e)
        return []

    def get_default_input(self) -> Optional[str]:
        """
        Get the current default source name.

        Returns None on any failure (timeout, no source set, pactl missing).
        """
        try:
            result = subprocess.run(
                ["pactl", "get-default-source"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                name = result.stdout.strip()
                return name or None
        except subprocess.TimeoutExpired:
            log.warning("pactl get-default-source timed out")
        except Exception as e:
            log.debug("Failed to get default input: %s", e)
        return None

    def set_default_input(self, input_name: str) -> None:
        """
        Switch the default source.

        Also moves any active source-outputs (recording streams) to the new
        source so live recordings (wake-word loop, etc.) switch immediately.
        """
        try:
            result = subprocess.run(
                ["pactl", "set-default-source", input_name],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                log.info("Default source set to: %s", input_name)
                self._move_streams_to_source(input_name)
            else:
                log.warning("Failed to set default source: %s", result.stderr.strip())
        except subprocess.TimeoutExpired:
            log.warning("pactl set-default-source timed out")
        except Exception as e:
            log.error("Failed to set default source: %s", e)

    def _move_streams_to_source(self, source_name: str) -> None:
        """Move all active source-outputs (recording streams) to the given source."""
        try:
            result = subprocess.run(
                ["pactl", "list", "source-outputs", "short"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                return

            for line in result.stdout.strip().splitlines():
                parts = line.split("\t")
                if parts:
                    stream_id = parts[0]
                    subprocess.run(
                        ["pactl", "move-source-output", stream_id, source_name],
                        capture_output=True, text=True, timeout=5,
                    )
        except Exception as e:
            log.debug("Could not move recording streams to new source: %s", e)

    # ── Card profile control (BT A2DP <-> HFP switching) ──────────

    def set_card_profile(self, card_name: str, profile_name: str) -> bool:
        """
        Switch a PulseAudio card to the given profile via
        `pactl set-card-profile <card> <profile>`.

        Used by AudioSessionManager to flip a Bluetooth card between
        `a2dp_sink` (high-fi output, no mic) and `headset_head_unit`
        (HFP — mic available, narrowband output) depending on whether
        the user's chosen input is on the same BT card.

        Quirk to know about: changing the profile causes PulseAudio to
        RENAME the sinks/sources owned by the card. e.g., the same
        speaker exposed as `bluez_sink.AA_BB_CC.a2dp_sink` becomes
        `bluez_sink.AA_BB_CC.headset_head_unit` after the switch. The
        caller (AudioSessionManager) is responsible for re-resolving
        the default sink/source on the NEXT tick. We don't try to
        chase the rename here — that would be a layering violation
        and racy besides.
        """
        if not card_name or not profile_name:
            return False
        try:
            result = subprocess.run(
                ["pactl", "set-card-profile", card_name, profile_name],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                log.info(
                    "Switched card '%s' to profile '%s'",
                    card_name, profile_name,
                )
                return True
            log.warning(
                "pactl set-card-profile %s %s failed: %s",
                card_name, profile_name, (result.stderr or "").strip(),
            )
        except subprocess.TimeoutExpired:
            log.warning(
                "pactl set-card-profile %s %s timed out",
                card_name, profile_name,
            )
        except Exception as e:
            log.error(
                "Failed to set card profile %s -> %s: %s",
                card_name, profile_name, e,
            )
        return False

    def get_card_for_device(self, device_name: str) -> Optional[str]:
        """
        Find the card name that owns a given sink or source device.

        Parses the verbose form of `pactl list sinks` / `pactl list
        sources` (NOT the `short` form — that omits the Card field).
        Walks the output line-by-line, tracking the current device
        block, and when we hit the matching `Name:` we capture the
        `Card:` from the same block.

        Robustness notes:
          - Multi-card output: each "Sink #N" or "Source #N" header
            resets the block-local state, so multiple devices don't
            leak Card values across blocks.
          - Missing Card field: many non-BT sinks (e.g., null sinks,
            module-loaded virtual sinks) don't have a Card. We return
            None for those without scanning the rest of the file.
          - Malformed output: any subprocess error / timeout returns
            None. Never raises.

        Returns the card name (e.g., "bluez_card.AA_BB_CC_DD_EE_FF")
        or None if not found.
        """
        if not device_name:
            return None
        # Try sinks first, then sources. Most callers will be asking
        # about a sink (Bluetooth speaker); checking sources second
        # covers the input-side lookup.
        for kind in ("sinks", "sources"):
            card = self._find_card_in_pactl_block(kind, device_name)
            if card:
                return card
        return None

    def _find_card_in_pactl_block(self, kind: str, device_name: str) -> Optional[str]:
        """
        Run `pactl list <kind>` and parse out the Card for `device_name`.

        kind is "sinks" or "sources". Block boundaries are lines that
        start with "Sink #" or "Source #". Inside each block we look
        for a `Name:` line matching `device_name` and capture the
        `Card:` value (PulseAudio writes "Card: N" or "Card: <name>"
        depending on version; we capture the whole token).
        """
        try:
            result = subprocess.run(
                ["pactl", "list", kind],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                return None
        except subprocess.TimeoutExpired:
            log.warning("pactl list %s timed out", kind)
            return None
        except Exception as e:
            log.debug("Failed to list %s for card lookup: %s", kind, e)
            return None

        # Block markers depend on kind: "Sink #..." / "Source #..."
        header_prefix = "Sink #" if kind == "sinks" else "Source #"

        current_name: Optional[str] = None
        current_card: Optional[str] = None
        target_block_card: Optional[str] = None
        target_found = False

        for raw in result.stdout.splitlines():
            line = raw.strip()
            if line.startswith(header_prefix):
                # New device block — if we already finished the target
                # block (saw both Name AND Card for it), resolve and return.
                if target_found and target_block_card:
                    return self._resolve_card_id_to_name(target_block_card)
                current_name = None
                current_card = None
                continue

            # "Name: <device>"
            if line.startswith("Name:"):
                current_name = line.split(":", 1)[1].strip()
                if current_name == device_name:
                    target_found = True
                    # We may have already seen Card: above Name:; capture it.
                    if current_card and target_block_card is None:
                        target_block_card = current_card
                continue

            # "Card: <id-or-name>" — usually just an integer index
            # ("Card: 42") on older PA but newer pactl can print a name.
            # Translate integer to the card name via the cards list below.
            if line.startswith("Card:"):
                current_card = line.split(":", 1)[1].strip()
                if target_found and target_block_card is None:
                    target_block_card = current_card

        # Tail of file: if we found the target block but never hit
        # another header, the captured Card is still valid.
        if target_found and target_block_card:
            return self._resolve_card_id_to_name(target_block_card)
        return None

    def _resolve_card_id_to_name(self, card_token: str) -> Optional[str]:
        """
        `pactl list sinks` writes "Card: 42" (a numeric index) on most
        PulseAudio versions. We need the symbolic name ("bluez_card.AA_BB_...")
        because that's what `pactl set-card-profile` expects.

        If `card_token` is already a name (contains a dot or non-digit),
        return it as-is. If it's purely numeric, look up the matching
        card from `pactl list cards short` whose first column matches.
        """
        if not card_token:
            return None
        token = card_token.strip()
        if not token.isdigit():
            # Already a name like "bluez_card.AA_BB_CC_DD_EE_FF" — use directly.
            return token
        try:
            result = subprocess.run(
                ["pactl", "list", "cards", "short"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                return None
        except subprocess.TimeoutExpired:
            log.warning("pactl list cards short timed out")
            return None
        except Exception as e:
            log.debug("Failed to list cards: %s", e)
            return None

        for line in result.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2 and parts[0].strip() == token:
                return parts[1].strip()
        return None

    # ── Bluetooth (delegates to BluetoothHelper) ─────────────────

    def bluetooth_scan(self, timeout: int = 10) -> list[dict]:
        return self._bluetooth.scan(timeout)

    def bluetooth_pair(self, mac_address: str) -> bool:
        return self._bluetooth.pair(mac_address)

    def bluetooth_disconnect(self, mac_address: str) -> bool:
        return self._bluetooth.disconnect(mac_address)
