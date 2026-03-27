"""
CoreAudio provider — system audio control for macOS.

Volume: osascript (AppleScript) — always available on macOS.
Device list: system_profiler SPAudioDataType -json — always available.
Device switch: SwitchAudioSource (optional, brew install switchaudio-osx).
Bluetooth: delegates to BluetoothHelper (uses blueutil).
"""

import json
import platform
import shutil
import subprocess

from core.interfaces import AudioOutputProvider
from core.logger import get_logger
from core.registry import register
from providers.audio.bluetooth import BluetoothHelper

log = get_logger("audio.coreaudio")


@register("audio", "coreaudio")
class CoreAudioProvider(AudioOutputProvider):
    """macOS audio output control via CoreAudio / osascript."""

    def __init__(self):
        self._bluetooth = BluetoothHelper()

    def is_available(self) -> bool:
        return platform.system() == "Darwin"

    def set_volume(self, level: int, output: str = "default") -> None:
        """
        Set system volume 0-100.

        macOS volume is 0-100 via osascript. The output param is accepted
        but currently only controls the system default output.
        """
        level = max(0, min(100, level))
        try:
            subprocess.run(
                ["osascript", "-e", f"set volume output volume {level}"],
                capture_output=True, text=True, timeout=10,
            )
            log.debug("System volume set to %d", level)
        except subprocess.TimeoutExpired:
            log.warning("osascript set volume timed out")
        except Exception as e:
            log.error("Failed to set volume: %s", e)

    def get_volume(self, output: str = "default") -> int:
        """Get current system volume 0-100."""
        try:
            result = subprocess.run(
                ["osascript", "-e", "output volume of (get volume settings)"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                return int(result.stdout.strip())
        except (subprocess.TimeoutExpired, ValueError) as e:
            log.warning("Failed to get volume: %s", e)
        except Exception as e:
            log.error("Failed to get volume: %s", e)
        return -1

    def list_outputs(self) -> list[dict]:
        """
        List available audio output devices.

        Uses system_profiler SPAudioDataType -json which is always
        available on macOS. Returns structured device info.
        """
        try:
            result = subprocess.run(
                ["system_profiler", "SPAudioDataType", "-json"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                log.warning("system_profiler failed: %s", result.stderr.strip())
                return []

            data = json.loads(result.stdout)
            outputs = []
            audio_items = data.get("SPAudioDataType", [])
            for item in audio_items:
                items_list = item.get("_items", [])
                for device in items_list:
                    name = device.get("_name", "Unknown")
                    # Determine type from the device info
                    device_type = "system"
                    coreaudio_info = device.get("coreaudio_device_transport", "")
                    if "bluetooth" in coreaudio_info.lower():
                        device_type = "bluetooth"
                    elif "hdmi" in name.lower():
                        device_type = "hdmi"
                    elif "usb" in coreaudio_info.lower():
                        device_type = "usb"

                    outputs.append({
                        "name": name,
                        "type": device_type,
                        "active": False,  # system_profiler doesn't tell us this directly
                    })
            return outputs

        except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
            log.warning("Failed to list outputs: %s", e)
        except Exception as e:
            log.error("Failed to list outputs: %s", e)
        return []

    def set_default_output(self, output: str) -> None:
        """
        Switch the default audio output device by name.

        Requires SwitchAudioSource (brew install switchaudio-osx).
        Without it, logs a warning — the user can still switch manually
        via System Settings → Sound.
        """
        if not shutil.which("SwitchAudioSource"):
            log.warning(
                "SwitchAudioSource not found. Install: brew install switchaudio-osx. "
                "You can switch audio output manually in System Settings → Sound."
            )
            return

        try:
            result = subprocess.run(
                ["SwitchAudioSource", "-s", output],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                log.info("Switched audio output to: %s", output)
            else:
                log.warning("Failed to switch output: %s", result.stderr.strip())
        except subprocess.TimeoutExpired:
            log.warning("SwitchAudioSource timed out")
        except Exception as e:
            log.error("Failed to switch output: %s", e)

    # ── Bluetooth (delegates to BluetoothHelper) ─────────────────

    def bluetooth_scan(self, timeout: int = 10) -> list[dict]:
        return self._bluetooth.scan(timeout)

    def bluetooth_pair(self, mac_address: str) -> bool:
        return self._bluetooth.pair(mac_address)

    def bluetooth_disconnect(self, mac_address: str) -> bool:
        return self._bluetooth.disconnect(mac_address)
