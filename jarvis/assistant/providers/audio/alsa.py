"""
ALSA provider — system audio control for Raspberry Pi (and bare Linux without PA).

Volume: amixer set Master X%
Device list: aplay -l
Device switch: writes ~/.asoundrc (affects new audio sessions only)
Bluetooth: delegates to BluetoothHelper (uses bluetoothctl).

ALSA is the kernel-level audio layer on Linux. On the Pi, PulseAudio
is often not installed — ALSA is the only game in town. This provider
talks directly to ALSA via amixer/aplay CLI tools.

Limitation: changing the default output via .asoundrc only affects
processes that start AFTER the file is written. Currently-playing
audio keeps using the old device. A restart of mpv (or the assistant)
is needed to switch live audio.
"""

import re
import shutil
import subprocess
from pathlib import Path

from core.interfaces import AudioOutputProvider
from core.logger import get_logger
from core.registry import register
from providers.audio.bluetooth import BluetoothHelper

log = get_logger("audio.alsa")


@register("audio", "alsa")
class AlsaAudioProvider(AudioOutputProvider):
    """Raspberry Pi / bare-Linux audio control via ALSA (amixer/aplay)."""

    def __init__(self):
        self._bluetooth = BluetoothHelper()

    def is_available(self) -> bool:
        return shutil.which("amixer") is not None

    def set_volume(self, level: int, output: str = "default") -> None:
        """
        Set Master volume 0-100%.

        amixer's "Master" control is the main output volume on most
        Pi audio setups (built-in headphone jack, USB audio, HDMI).
        """
        level = max(0, min(100, level))
        try:
            subprocess.run(
                ["amixer", "set", "Master", f"{level}%"],
                capture_output=True, text=True, timeout=10,
            )
            log.debug("ALSA Master volume set to %d%%", level)
        except subprocess.TimeoutExpired:
            log.warning("amixer set Master timed out")
        except Exception as e:
            log.error("Failed to set volume: %s", e)

    def get_volume(self, output: str = "default") -> int:
        """
        Get current Master volume 0-100%.

        Parses the [XX%] from amixer get Master output:
        "  Mono: Playback 42000 [64%] [-11.78dB] [on]"
        """
        try:
            result = subprocess.run(
                ["amixer", "get", "Master"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                match = re.search(r"\[(\d+)%\]", result.stdout)
                if match:
                    return int(match.group(1))
        except subprocess.TimeoutExpired:
            log.warning("amixer get Master timed out")
        except Exception as e:
            log.error("Failed to get volume: %s", e)
        return -1

    def list_outputs(self) -> list[dict]:
        """
        List available audio playback devices via aplay -l.

        Parses output like:
        "card 0: Headphones [bcm2835 Headphones], device 0: bcm2835 Headphones [bcm2835 Headphones]"
        """
        try:
            result = subprocess.run(
                ["aplay", "-l"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                return []

            outputs = []
            for line in result.stdout.splitlines():
                # Match lines like "card N: Name [Description], device M: ..."
                match = re.match(
                    r"card\s+(\d+):\s+(\w+)\s+\[(.+?)\],\s+device\s+(\d+):",
                    line,
                )
                if match:
                    card_num = match.group(1)
                    card_id = match.group(2)
                    description = match.group(3)
                    device_num = match.group(4)

                    # Infer type
                    device_type = "system"
                    desc_lower = description.lower()
                    if "bluetooth" in desc_lower or "bluez" in desc_lower:
                        device_type = "bluetooth"
                    elif "hdmi" in desc_lower:
                        device_type = "hdmi"
                    elif "usb" in desc_lower:
                        device_type = "usb"

                    outputs.append({
                        "name": f"hw:{card_num},{device_num}",
                        "type": device_type,
                        "active": False,
                        "description": description,
                    })
            return outputs

        except subprocess.TimeoutExpired:
            log.warning("aplay -l timed out")
        except Exception as e:
            log.error("Failed to list outputs: %s", e)
        return []

    def set_default_output(self, output: str) -> None:
        """
        Set the default ALSA output by writing ~/.asoundrc.

        This only affects processes started AFTER the write. Active
        playback (mpv) keeps using the old device until restarted.

        Expects output in "hw:X,Y" format (from list_outputs).
        """
        asoundrc = Path.home() / ".asoundrc"
        config_content = (
            f"# Generated by Jarvis AudioOutputProvider\n"
            f"pcm.!default {{\n"
            f"    type hw\n"
            f"    card {output}\n"
            f"}}\n"
            f"ctl.!default {{\n"
            f"    type hw\n"
            f"    card {output}\n"
            f"}}\n"
        )
        try:
            # Parse card number from "hw:X,Y" format
            if output.startswith("hw:"):
                card = output.split(":")[1].split(",")[0]
            else:
                card = output

            config_content = (
                f"# Generated by Jarvis AudioOutputProvider\n"
                f"pcm.!default {{\n"
                f"    type hw\n"
                f"    card {card}\n"
                f"}}\n"
                f"ctl.!default {{\n"
                f"    type hw\n"
                f"    card {card}\n"
                f"}}\n"
            )
            asoundrc.write_text(config_content)
            log.info(
                "Default ALSA output set to: %s (written to %s). "
                "Note: active playback uses the old device until restarted.",
                output, asoundrc,
            )
        except Exception as e:
            log.error("Failed to write %s: %s", asoundrc, e)

    # ── Bluetooth (delegates to BluetoothHelper) ─────────────────

    def bluetooth_scan(self, timeout: int = 10) -> list[dict]:
        return self._bluetooth.scan(timeout)

    def bluetooth_pair(self, mac_address: str) -> bool:
        return self._bluetooth.pair(mac_address)

    def bluetooth_disconnect(self, mac_address: str) -> bool:
        return self._bluetooth.disconnect(mac_address)
