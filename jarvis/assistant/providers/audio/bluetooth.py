"""
Shared Bluetooth helper — wraps platform-specific CLI tools.

macOS: uses `blueutil` (brew install blueutil)
Linux: uses `bluetoothctl` (ships with BlueZ, pre-installed on most distros)

All methods are safe to call on any platform — they return empty/False
when the required CLI tool is not installed, never crash.
"""

import platform
import shutil
import subprocess
from core.logger import get_logger

log = get_logger("audio.bluetooth")


class BluetoothHelper:
    """
    Platform-agnostic Bluetooth device management.

    Delegates to `blueutil` on macOS or `bluetoothctl` on Linux.
    Every method checks tool availability first and degrades gracefully.
    """

    def __init__(self):
        self._system = platform.system()

    # ── Public API ───────────────────────────────────────────────

    def scan(self, timeout: int = 10) -> list[dict]:
        """
        Scan for nearby Bluetooth devices.

        Returns: [{"name": "JBL Flip 6", "mac_address": "AA:BB:CC:DD:EE:FF", "paired": False}, ...]
        """
        if self._system == "Darwin":
            return self._macos_scan(timeout)
        elif self._system == "Linux":
            return self._linux_scan(timeout)
        log.debug("Bluetooth scan not supported on %s", self._system)
        return []

    def pair(self, mac_address: str) -> bool:
        """Pair, trust, and connect to a Bluetooth device."""
        if self._system == "Darwin":
            return self._macos_pair(mac_address)
        elif self._system == "Linux":
            return self._linux_pair(mac_address)
        log.debug("Bluetooth pair not supported on %s", self._system)
        return False

    def disconnect(self, mac_address: str) -> bool:
        """Disconnect a paired Bluetooth device."""
        if self._system == "Darwin":
            return self._macos_disconnect(mac_address)
        elif self._system == "Linux":
            return self._linux_disconnect(mac_address)
        log.debug("Bluetooth disconnect not supported on %s", self._system)
        return False

    def list_paired(self) -> list[dict]:
        """List currently paired Bluetooth devices."""
        if self._system == "Darwin":
            return self._macos_list_paired()
        elif self._system == "Linux":
            return self._linux_list_paired()
        log.debug("Bluetooth list_paired not supported on %s", self._system)
        return []

    # ── macOS (blueutil) ─────────────────────────────────────────

    def _has_blueutil(self) -> bool:
        if shutil.which("blueutil"):
            return True
        log.debug("blueutil not found. Install: brew install blueutil")
        return False

    def _run_blueutil(self, args: list[str], timeout: int = 15) -> str | None:
        """Run a blueutil command, return stdout or None on failure."""
        if not self._has_blueutil():
            return None
        try:
            result = subprocess.run(
                ["blueutil"] + args,
                capture_output=True, text=True, timeout=timeout,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            log.debug("blueutil %s failed: %s", args, result.stderr.strip())
        except subprocess.TimeoutExpired:
            log.warning("blueutil %s timed out after %ds", args, timeout)
        except Exception as e:
            log.warning("blueutil %s error: %s", args, e)
        return None

    def _macos_scan(self, timeout: int) -> list[dict]:
        # blueutil --inquiry <timeout> returns discovered devices
        output = self._run_blueutil(["--inquiry", str(timeout)], timeout=timeout + 5)
        if not output:
            return []
        devices = []
        paired_macs = {d["mac_address"] for d in self._macos_list_paired()}
        for line in output.strip().splitlines():
            # Format: "address: AA-BB-CC-DD-EE-FF, name: "Device Name", ..."
            parts = {}
            for segment in line.split(", "):
                if ": " in segment:
                    key, val = segment.split(": ", 1)
                    parts[key.strip()] = val.strip().strip('"')
            address = parts.get("address", "").replace("-", ":")
            name = parts.get("name", address)
            if address:
                devices.append({
                    "name": name,
                    "mac_address": address,
                    "paired": address in paired_macs,
                })
        return devices

    def _macos_pair(self, mac_address: str) -> bool:
        result = self._run_blueutil(["--pair", mac_address])
        if result is None:
            return False
        # Also connect after pairing
        connect_result = self._run_blueutil(["--connect", mac_address])
        return connect_result is not None

    def _macos_disconnect(self, mac_address: str) -> bool:
        result = self._run_blueutil(["--disconnect", mac_address])
        return result is not None

    def _macos_list_paired(self) -> list[dict]:
        output = self._run_blueutil(["--paired"])
        if not output:
            return []
        devices = []
        for line in output.strip().splitlines():
            parts = {}
            for segment in line.split(", "):
                if ": " in segment:
                    key, val = segment.split(": ", 1)
                    parts[key.strip()] = val.strip().strip('"')
            address = parts.get("address", "").replace("-", ":")
            name = parts.get("name", address)
            if address:
                devices.append({
                    "name": name,
                    "mac_address": address,
                    "paired": True,
                })
        return devices

    # ── Linux (bluetoothctl) ─────────────────────────────────────

    def _has_bluetoothctl(self) -> bool:
        if shutil.which("bluetoothctl"):
            return True
        log.debug("bluetoothctl not found. Install: sudo apt install bluez")
        return False

    def _run_bluetoothctl(self, commands: list[str], timeout: int = 15) -> str | None:
        """
        Run one or more bluetoothctl commands via stdin pipe.

        bluetoothctl is interactive, so we feed commands via stdin
        and read stdout. Each command is newline-separated.
        """
        if not self._has_bluetoothctl():
            return None
        try:
            input_text = "\n".join(commands) + "\nexit\n"
            result = subprocess.run(
                ["bluetoothctl"],
                input=input_text,
                capture_output=True, text=True, timeout=timeout,
            )
            return result.stdout
        except subprocess.TimeoutExpired:
            log.warning("bluetoothctl timed out after %ds", timeout)
        except Exception as e:
            log.warning("bluetoothctl error: %s", e)
        return None

    def _linux_scan(self, timeout: int) -> list[dict]:
        # Start scan, wait, then list devices
        output = self._run_bluetoothctl(
            [f"scan on"],
            timeout=timeout + 5,
        )
        # After scan, list discovered devices
        list_output = self._run_bluetoothctl(["devices"], timeout=5)
        if not list_output:
            return []
        devices = []
        paired_macs = {d["mac_address"] for d in self._linux_list_paired()}
        for line in list_output.splitlines():
            # Format: "Device AA:BB:CC:DD:EE:FF Device Name"
            line = line.strip()
            if line.startswith("Device "):
                parts = line[7:].split(" ", 1)
                if len(parts) >= 1:
                    mac = parts[0]
                    name = parts[1] if len(parts) > 1 else mac
                    devices.append({
                        "name": name,
                        "mac_address": mac,
                        "paired": mac in paired_macs,
                    })
        return devices

    def _linux_pair(self, mac_address: str) -> bool:
        output = self._run_bluetoothctl(
            [f"pair {mac_address}", f"trust {mac_address}", f"connect {mac_address}"],
            timeout=30,
        )
        if not output:
            return False
        # Check for successful connection
        return "Connection successful" in output or "Connected: yes" in output

    def _linux_disconnect(self, mac_address: str) -> bool:
        output = self._run_bluetoothctl([f"disconnect {mac_address}"], timeout=10)
        if not output:
            return False
        return "Successful disconnected" in output or "Connected: no" in output

    def _linux_list_paired(self) -> list[dict]:
        output = self._run_bluetoothctl(["paired-devices"], timeout=5)
        if not output:
            return []
        devices = []
        for line in output.splitlines():
            line = line.strip()
            if line.startswith("Device "):
                parts = line[7:].split(" ", 1)
                if len(parts) >= 1:
                    mac = parts[0]
                    name = parts[1] if len(parts) > 1 else mac
                    devices.append({
                        "name": name,
                        "mac_address": mac,
                        "paired": True,
                    })
        return devices
