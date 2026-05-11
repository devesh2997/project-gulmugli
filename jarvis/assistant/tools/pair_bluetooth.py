#!/usr/bin/env python3
"""
pair_bluetooth.py — guided Bluetooth speaker pairing for the Jetson.

## Why

The May 14 launch hardware is a Marshall Willen II BT speaker plus a
USB conference mic on a Jetson Orin Nano. On day-of we don't want to
fumble with `bluetoothctl` — this script walks the user through the
whole flow: put speaker in pairing mode → scan → pick from a numbered
list → pair + trust + connect → verify → optionally persist the MAC
into config.yaml so the assistant remembers the speaker across reboots.

## Usage

    cd jarvis/assistant
    python tools/pair_bluetooth.py            # interactive pair
    python tools/pair_bluetooth.py --save     # also write MAC to config.yaml
    python tools/pair_bluetooth.py --debug    # show tracebacks on errors
    python tools/pair_bluetooth.py --help

## Platform support

This tool only runs on Linux (the Jetson). On macOS it exits cleanly
with a hint to use System Preferences > Bluetooth instead — pairing on
Mac is best done via the GUI.

The actual Bluetooth work is delegated to
`providers.audio.bluetooth.BluetoothHelper`, which wraps `bluetoothctl`.

## Exit codes

  0 — success, or graceful early exit (e.g. wrong platform, user quit)
  1 — environment problem (bluetoothctl missing, etc.)
  2 — pairing failed after the user picked a device
"""

from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

# Bring assistant/ onto the path so we can import core/* and providers/*.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.logger import get_logger  # noqa: E402

log = get_logger("tools.pair_bluetooth")


# ── Output helpers ──────────────────────────────────────────────────

_USE_COLOR = hasattr(sys.stdout, "isatty") and sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def _c(code: str) -> str:
    return code if _USE_COLOR else ""


GREEN = _c("\033[32m")
RED = _c("\033[31m")
YELLOW = _c("\033[33m")
CYAN = _c("\033[36m")
DIM = _c("\033[2m")
BOLD = _c("\033[1m")
RESET = _c("\033[0m")


def _say(msg: str) -> None:
    print(msg, flush=True)


def _ok(msg: str) -> None:
    _say(f"{GREEN}✓{RESET} {msg}")


def _warn(msg: str) -> None:
    _say(f"{YELLOW}!{RESET} {msg}")


def _err(msg: str) -> None:
    _say(f"{RED}✗ {msg}{RESET}")


# ── Config writer (no ruamel.yaml — string surgery) ─────────────────

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"


def _update_config_yaml(mac: str, device_name: str) -> bool:
    """
    Add or update `audio.bluetooth.preferred_mac` and `audio.bluetooth.device_name`
    inside config.yaml WITHOUT touching surrounding sections, indentation, or
    comments more than necessary.

    Strategy (chosen because ruamel.yaml isn't in requirements.txt and
    re-emitting via PyYAML would obliterate every comment in the file):

      1. Read config.yaml as text.
      2. Find the `audio:` top-level key.
      3. Look inside its block (lines indented past column 0 until the next
         top-level key) for an existing `bluetooth:` subkey.
      4a. If found, find/replace `preferred_mac:` and `device_name:` lines
          beneath it, or insert them if missing.
      4b. If not found, insert a fresh `bluetooth:` block at the end of the
          audio section.
      5. Write the file back.

    All edits use 2-space indentation to match the rest of the file. We
    preserve trailing newlines and the file's existing comment structure.

    Returns True on success, False if `audio:` couldn't be located (in
    which case we leave the file untouched and the caller surfaces the
    error to the user).
    """
    if not CONFIG_PATH.exists():
        _err(f"config.yaml not found at {CONFIG_PATH}")
        return False

    text = CONFIG_PATH.read_text()
    lines = text.splitlines(keepends=False)

    # Find the audio: top-level key. A top-level key starts at column 0
    # and ends with a colon and (optionally) whitespace + a trailing comment.
    audio_start = None
    for i, ln in enumerate(lines):
        if re.match(r"^audio\s*:\s*(#.*)?$", ln):
            audio_start = i
            break

    if audio_start is None:
        _err("Couldn't find an `audio:` section in config.yaml. Add one manually:\n"
             f"  audio:\n"
             f"    bluetooth:\n"
             f"      preferred_mac: \"{mac}\"\n"
             f"      device_name: \"{device_name}\"")
        return False

    # Find where the audio block ends (next top-level key or EOF).
    audio_end = len(lines)
    for i in range(audio_start + 1, len(lines)):
        # Top-level key = first column is a letter/_ and ends with a colon.
        if re.match(r"^[A-Za-z_][\w-]*\s*:", lines[i]):
            audio_end = i
            break

    # Within [audio_start+1, audio_end), look for `  bluetooth:` (2-space indent).
    bt_start = None
    for i in range(audio_start + 1, audio_end):
        if re.match(r"^  bluetooth\s*:\s*(#.*)?$", lines[i]):
            bt_start = i
            break

    new_mac_line = f'    preferred_mac: "{mac}"'
    new_name_line = f'    device_name: "{device_name}"'

    if bt_start is not None:
        # Find the block under bluetooth: (4-space indent or deeper).
        bt_end = audio_end
        for i in range(bt_start + 1, audio_end):
            ln = lines[i]
            if ln.strip() == "":
                continue
            # If indent is <= 2 spaces and not a continuation comment, block ended.
            stripped = ln.lstrip()
            indent = len(ln) - len(stripped)
            if indent <= 2 and not stripped.startswith("#"):
                bt_end = i
                break

        # Try to find and replace existing preferred_mac / device_name lines.
        mac_idx = None
        name_idx = None
        for i in range(bt_start + 1, bt_end):
            if re.match(r"^\s+preferred_mac\s*:", lines[i]):
                mac_idx = i
            elif re.match(r"^\s+device_name\s*:", lines[i]):
                name_idx = i

        if mac_idx is not None:
            lines[mac_idx] = new_mac_line
        if name_idx is not None:
            lines[name_idx] = new_name_line

        # Insert whatever was missing, right after the `bluetooth:` line.
        to_insert = []
        if mac_idx is None:
            to_insert.append(new_mac_line)
        if name_idx is None:
            to_insert.append(new_name_line)
        if to_insert:
            lines[bt_start + 1:bt_start + 1] = to_insert
    else:
        # No bluetooth: block exists. Insert one at the end of the audio: block.
        # Trim trailing blank lines inside the block so the new entries sit flush.
        insert_at = audio_end
        while insert_at > audio_start + 1 and lines[insert_at - 1].strip() == "":
            insert_at -= 1
        new_block = [
            "  bluetooth:",
            new_mac_line,
            new_name_line,
        ]
        lines[insert_at:insert_at] = new_block

    new_text = "\n".join(lines)
    if text.endswith("\n") and not new_text.endswith("\n"):
        new_text += "\n"

    CONFIG_PATH.write_text(new_text)
    return True


# ── Pairing flow ────────────────────────────────────────────────────


def _verify_connected(mac: str) -> tuple[bool, str | None]:
    """
    Call `bluetoothctl info <mac>` and parse out Connected/Name lines.

    Returns (connected, name) — name may be None if we couldn't parse it.
    """
    try:
        result = subprocess.run(
            ["bluetoothctl", "info", mac],
            capture_output=True, text=True, timeout=10,
        )
    except FileNotFoundError:
        return False, None
    except subprocess.TimeoutExpired:
        log.warning("`bluetoothctl info %s` timed out", mac)
        return False, None
    except Exception as e:
        log.warning("`bluetoothctl info %s` failed: %s", mac, e)
        return False, None

    if result.returncode != 0:
        return False, None

    connected = False
    name = None
    for ln in result.stdout.splitlines():
        ln = ln.strip()
        if ln.startswith("Connected:"):
            connected = ln.split(":", 1)[1].strip().lower() == "yes"
        elif ln.startswith("Name:"):
            name = ln.split(":", 1)[1].strip() or None
        elif ln.startswith("Alias:") and name is None:
            name = ln.split(":", 1)[1].strip() or None
    return connected, name


def _scan_and_prompt(timeout: int) -> dict | None:
    """
    Run a scan, print a numbered list, return the chosen device dict or None
    if the user quits / no devices found.

    Retries on the user's request if no devices show up — the most common
    cause is "speaker isn't actually in pairing mode."
    """
    from providers.audio.bluetooth import BluetoothHelper
    helper = BluetoothHelper()

    while True:
        _say(f"\n{CYAN}Scanning for {timeout} seconds...{RESET}")
        devices = helper.scan(timeout)

        if not devices:
            _warn("No devices found.")
            _say(
                f"{DIM}Common causes: speaker isn't in pairing mode, "
                f"Bluetooth is disabled on the host, or scan was interrupted.{RESET}"
            )
            again = input("Try scanning again? [Y/n] ").strip().lower()
            if again in ("n", "no", "q", "quit"):
                return None
            continue

        _say(f"\n{BOLD}Found {len(devices)} device(s):{RESET}")
        for i, dev in enumerate(devices, 1):
            tag = f" {DIM}(already paired){RESET}" if dev.get("paired") else ""
            _say(f"  [{i}] {dev['name']} {DIM}({dev['mac_address']}){RESET}{tag}")

        while True:
            choice = input(
                f"\n{BOLD}Which one is your speaker?{RESET} "
                f"(number 1-{len(devices)}, r=rescan, q=quit): "
            ).strip().lower()
            if choice in ("q", "quit", "exit"):
                return None
            if choice in ("r", "rescan"):
                break  # back to scan loop
            try:
                idx = int(choice)
            except ValueError:
                _warn("Not a number. Try again.")
                continue
            if 1 <= idx <= len(devices):
                return devices[idx - 1]
            _warn(f"Pick a number between 1 and {len(devices)}.")


def _do_pairing(debug: bool, save: bool) -> int:
    """Run the full pairing flow. Returns process exit code."""
    _say(f"\n{BOLD}Hi. Let's pair a Bluetooth speaker with the Jetson.{RESET}\n")

    # Platform check
    if platform.system() != "Linux":
        _say(
            "This tool runs on the Jetson (Linux). "
            "On Mac, use System Preferences → Bluetooth instead."
        )
        return 0

    # bluetoothctl check
    if not shutil.which("bluetoothctl"):
        _err("`bluetoothctl` is not installed.")
        _say(f"  Install it with: {CYAN}sudo apt install bluez{RESET}")
        return 1

    # Prompt for pairing-mode
    _say(
        f"{CYAN}Step 1.{RESET} Put your speaker into pairing mode now.\n"
        f"  Marshall Willen II: {DIM}hold the Bluetooth button for ~3 seconds "
        f"until the LED starts blinking fast.{RESET}\n"
        f"  Other speakers: hold the BT/pair button until you see a blinking "
        f"or color-changing LED.\n"
    )
    input("Press Enter when the speaker is in pairing mode... ")

    # Scan + pick
    chosen = _scan_and_prompt(timeout=15)
    if chosen is None:
        _say("\nCancelled. No speaker paired.")
        return 0

    mac = chosen["mac_address"]
    name = chosen["name"]

    # Pair
    _say(f"\n{CYAN}Step 2.{RESET} Pairing with {BOLD}{name}{RESET} ({mac})...")
    _say(f"{DIM}(This typically takes 5-15 seconds. Don't unplug anything.){RESET}")

    from providers.audio.bluetooth import BluetoothHelper
    helper = BluetoothHelper()
    try:
        paired_ok = helper.pair(mac)
    except Exception as e:
        if debug:
            traceback.print_exc()
        _err(f"Pairing crashed: {e}")
        return 2

    # Verify via `bluetoothctl info`
    connected, info_name = _verify_connected(mac)
    final_name = info_name or name

    if not (paired_ok or connected):
        _err(f"Pairing failed for {final_name} ({mac}).")
        _say(
            f"  {DIM}Try these:\n"
            f"  - Re-enter pairing mode on the speaker and rerun this tool.\n"
            f"  - Check if the host's Bluetooth radio is on: "
            f"`bluetoothctl show` should report `Powered: yes`.\n"
            f"  - Some speakers need a manual `bluetoothctl > connect {mac}` "
            f"after pairing — try it.{RESET}"
        )
        return 2

    if not connected:
        # Pair succeeded but not connected — try a one-shot connect.
        _warn("Paired but not connected. Trying to connect now...")
        try:
            subprocess.run(
                ["bluetoothctl"], input=f"connect {mac}\nexit\n",
                capture_output=True, text=True, timeout=15,
            )
        except Exception as e:
            log.debug("Connect retry failed: %s", e)
        connected, info_name = _verify_connected(mac)
        final_name = info_name or final_name

    if connected:
        _ok(f"Paired and connected: {BOLD}{final_name}{RESET} ({mac})")
    else:
        _warn(f"Paired but {RED}not currently connected{RESET}. "
              f"Power-cycle the speaker and try `bluetoothctl > connect {mac}`.")

    # Persist to config
    _say("")
    if save:
        if _update_config_yaml(mac, final_name):
            _ok(f"Wrote audio.bluetooth.preferred_mac = \"{mac}\" to config.yaml")
            _ok(f"Wrote audio.bluetooth.device_name = \"{final_name}\" to config.yaml")
        else:
            _warn("Couldn't update config.yaml automatically — add this manually:")
            _say(f"  audio:")
            _say(f"    bluetooth:")
            _say(f"      preferred_mac: \"{mac}\"")
            _say(f"      device_name: \"{final_name}\"")
            return 2
    else:
        _say(f"{BOLD}Add this to your config.yaml under `audio:`{RESET}")
        _say(f"  bluetooth:")
        _say(f"    preferred_mac: \"{mac}\"")
        _say(f"    device_name: \"{final_name}\"")
        _say(f"")
        _say(f"Or rerun with: {CYAN}python tools/pair_bluetooth.py --save{RESET}")
        _say(f"{DIM}(this writes the lines to config.yaml automatically){RESET}")

    return 0


def main() -> int:
    p = argparse.ArgumentParser(
        description="Guided Bluetooth speaker pairing for the Jetson.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python tools/pair_bluetooth.py\n"
            "  python tools/pair_bluetooth.py --save     # also writes config.yaml\n"
        ),
    )
    p.add_argument("--save", action="store_true",
                   help="Persist the paired speaker's MAC + name to config.yaml.")
    p.add_argument("--debug", action="store_true",
                   help="Show full tracebacks on errors.")
    args = p.parse_args()

    try:
        return _do_pairing(debug=args.debug, save=args.save)
    except KeyboardInterrupt:
        _say(f"\n{YELLOW}Interrupted. No speaker paired.{RESET}")
        return 0
    except Exception as e:
        if args.debug:
            traceback.print_exc()
        _err(f"Unexpected error: {type(e).__name__}: {e}")
        _say(f"{DIM}(rerun with --debug for the full traceback){RESET}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
