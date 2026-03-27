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

    # ── Bluetooth (delegates to BluetoothHelper) ─────────────────

    def bluetooth_scan(self, timeout: int = 10) -> list[dict]:
        return self._bluetooth.scan(timeout)

    def bluetooth_pair(self, mac_address: str) -> bool:
        return self._bluetooth.pair(mac_address)

    def bluetooth_disconnect(self, mac_address: str) -> bool:
        return self._bluetooth.disconnect(mac_address)
