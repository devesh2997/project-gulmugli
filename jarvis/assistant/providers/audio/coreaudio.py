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
from typing import Optional

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

    # ── Inputs (microphones) ─────────────────────────────────────

    def list_inputs(self) -> list[dict]:
        """
        List available audio input devices (microphones, line-in, USB capture).

        Parses `system_profiler SPAudioDataType -json` for entries with
        `coreaudio_device_input > 0`. system_profiler is always available
        on macOS — no brew package needed.
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
            inputs = []
            audio_items = data.get("SPAudioDataType", [])
            for item in audio_items:
                items_list = item.get("_items", [])
                for device in items_list:
                    # Only treat as input if it has input channels.
                    # system_profiler exposes this under several possible keys
                    # depending on macOS version; check the common ones.
                    input_chans = (
                        device.get("coreaudio_device_input")
                        or device.get("coreaudio_input_source")
                        or 0
                    )
                    try:
                        input_chans = int(input_chans)
                    except (TypeError, ValueError):
                        input_chans = 1 if input_chans else 0

                    is_default_input = (
                        device.get("coreaudio_default_audio_input_device") == "spaudio_yes"
                    )

                    # Include device if it has input channels OR is marked as default input
                    if input_chans <= 0 and not is_default_input:
                        continue

                    name = device.get("_name", "Unknown")
                    coreaudio_info = device.get("coreaudio_device_transport", "")
                    device_type = "system"
                    if "bluetooth" in coreaudio_info.lower():
                        device_type = "bluetooth"
                    elif "usb" in coreaudio_info.lower():
                        device_type = "usb"
                    elif "hdmi" in name.lower():
                        device_type = "hdmi"

                    inputs.append({
                        "name": name,
                        "type": device_type,
                        "active": is_default_input,
                    })
            return inputs

        except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
            log.warning("Failed to list inputs: %s", e)
        except Exception as e:
            log.error("Failed to list inputs: %s", e)
        return []

    def get_default_input(self) -> Optional[str]:
        """
        Return the current default input device name.

        Uses SwitchAudioSource if available (`brew install switchaudio-osx`).
        Falls back to parsing system_profiler for the device marked as default.
        Returns None on any failure.
        """
        if shutil.which("SwitchAudioSource"):
            try:
                result = subprocess.run(
                    ["SwitchAudioSource", "-c", "-t", "input"],
                    capture_output=True, text=True, timeout=10,
                )
                if result.returncode == 0:
                    name = result.stdout.strip()
                    return name or None
            except subprocess.TimeoutExpired:
                log.warning("SwitchAudioSource -c (input) timed out")
            except Exception as e:
                log.debug("SwitchAudioSource current input failed: %s", e)

        # Fallback: parse system_profiler for default-input device
        try:
            result = subprocess.run(
                ["system_profiler", "SPAudioDataType", "-json"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                return None
            data = json.loads(result.stdout)
            for item in data.get("SPAudioDataType", []):
                for device in item.get("_items", []):
                    if device.get("coreaudio_default_audio_input_device") == "spaudio_yes":
                        return device.get("_name") or None
        except Exception as e:
            log.debug("system_profiler default-input fallback failed: %s", e)
        return None

    def set_default_input(self, input_name: str) -> None:
        """
        Switch the default input device by name.

        Requires SwitchAudioSource (brew install switchaudio-osx). Without it,
        logs a warning — the user can switch manually in System Settings → Sound.
        """
        if not shutil.which("SwitchAudioSource"):
            log.warning(
                "SwitchAudioSource not found. Install: brew install switchaudio-osx. "
                "You can switch audio input manually in System Settings → Sound."
            )
            return

        try:
            result = subprocess.run(
                ["SwitchAudioSource", "-t", "input", "-s", input_name],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                log.info("Switched audio input to: %s", input_name)
            else:
                log.warning("Failed to switch input: %s", result.stderr.strip())
        except subprocess.TimeoutExpired:
            log.warning("SwitchAudioSource (input) timed out")
        except Exception as e:
            log.error("Failed to switch input: %s", e)

    # ── Bluetooth (delegates to BluetoothHelper) ─────────────────

    def bluetooth_scan(self, timeout: int = 10) -> list[dict]:
        return self._bluetooth.scan(timeout)

    def bluetooth_pair(self, mac_address: str) -> bool:
        return self._bluetooth.pair(mac_address)

    def bluetooth_disconnect(self, mac_address: str) -> bool:
        return self._bluetooth.disconnect(mac_address)
