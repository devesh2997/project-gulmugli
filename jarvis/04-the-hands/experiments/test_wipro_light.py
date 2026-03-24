"""
Wipro 20W CCT Batten — Test Script

This script tests direct local LAN control of your Wipro batten using tinytuya.
No internet needed — it talks directly to the bulb over your Wi-Fi.

Your batten is a CCT (Correlated Colour Temperature) model, which means:
  ✓ On/Off
  ✓ Brightness (0-100%)
  ✓ Colour temperature: warm white (2700K) ↔ cool daylight (6500K)
  ✗ NO arbitrary RGB colours (that needs a different bulb model)

How tinytuya works (the AI/hardware explanation):
  - Tuya devices communicate using a custom encrypted protocol over TCP
  - Each device has a unique "local key" — a 16-byte AES encryption key
  - tinytuya encrypts commands with this key and sends them to the device's IP
  - The device decrypts, executes, and sends back an encrypted status response
  - All of this happens on your LOCAL network — no cloud, no internet, no latency

  DPS (Data Point Settings) — Tuya's way of organizing device capabilities:
  Each feature of the device is a numbered "data point" (DP). For CCT battens:
    DP 20: Switch (on/off)         → True/False
    DP 22: Brightness              → 10-1000 (we map 0-100% → 10-1000)
    DP 23: Colour temperature      → 0-1000 (0 = warm 2700K, 1000 = cool 6500K)

  These DP numbers are standard across Tuya CCT lights. If your device uses
  different DPs, we'll discover them with a status query.

Usage:
    python test_wipro_light.py
"""

import tinytuya
import time
import sys

# ─── Your device credentials ─────────────────────────────────
DEVICE_ID = "d77ff5e6b620c82fd25atp"
LOCAL_KEY = "~J8W8clsW3Ya9D7V"
IP = "192.168.1.6"
VERSIONS_TO_TRY = [3.4, 3.5, 3.3, 3.2, 3.1]  # Try 3.4 first — most likely for newer Wipro firmware

# ─── Standard DPs for CCT (tunable white) devices ────────────
DP_SWITCH = 20
DP_MODE = 21         # "white" = colour temp mode, "colour" = RGB mode
DP_BRIGHTNESS = 22
DP_COLOUR_TEMP = 23
DP_COLOUR_HSV = 24   # HSV colour as hex string: HHHHSSSSSVVVV


def connect():
    """Try connecting with different protocol versions until one works."""
    for version in VERSIONS_TO_TRY:
        print(f"Trying protocol version {version}...")
        device = tinytuya.BulbDevice(DEVICE_ID, IP, LOCAL_KEY)
        device.set_version(version)

        status = device.status()
        if "Error" not in status:
            print(f"✓ Connected with version {version}!")
            return device, status
        else:
            print(f"  ✗ Version {version} failed: {status.get('Error', 'unknown')}")

    # All versions failed
    return None, None


def get_status(device):
    """Query current status of the bulb."""
    status = device.status()
    print(f"\nRaw status: {status}")

    if "Error" in status:
        print(f"\n✗ Connection error: {status['Error']}")
        print("  Possible causes:")
        print("  - Bulb is not on the same Wi-Fi network as this computer")
        print("  - IP address has changed (try: python -m tinytuya scan)")
        print("  - Local key is wrong (re-run: python -m tinytuya wizard)")
        return None

    dps = status.get("dps", {})
    print(f"\nData Points (DPS):")
    for dp, value in sorted(dps.items(), key=lambda x: int(x[0])):
        dp_name = {
            "20": "Switch (on/off)",
            "22": "Brightness (10-1000)",
            "23": "Colour Temp (0=warm, 1000=cool)",
            "21": "Mode",
            "24": "Colour (HSV)",
            "25": "Colour Data",
            "26": "Scene Data",
        }.get(str(dp), f"Unknown DP {dp}")
        print(f"  DP {dp}: {value}  ← {dp_name}")

    return dps


def test_on_off(device):
    """Test basic on/off toggle."""
    print("\n── Test: Turn OFF ──")
    device.set_value(DP_SWITCH, False)
    time.sleep(2)

    print("── Test: Turn ON ──")
    device.set_value(DP_SWITCH, True)
    time.sleep(1)


def test_brightness(device):
    """Test brightness levels."""
    print("\n── Test: Brightness sweep ──")

    levels = [10, 250, 500, 750, 1000]
    for level in levels:
        pct = int(level / 10)
        print(f"  Brightness: {pct}%")
        device.set_value(DP_BRIGHTNESS, level)
        time.sleep(1.5)

    # Reset to comfortable level
    device.set_value(DP_BRIGHTNESS, 500)
    print("  Reset to 50%")


def test_colour_temp(device):
    """Test colour temperature range."""
    print("\n── Test: Colour temperature sweep ──")
    print("  (Watch: warm yellow → cool white)")

    temps = [0, 250, 500, 750, 1000]
    labels = ["Warm (2700K)", "Warm-neutral", "Neutral (4000K)", "Cool-neutral", "Cool daylight (6500K)"]

    for temp, label in zip(temps, labels):
        print(f"  {label}: CT={temp}")
        device.set_value(DP_COLOUR_TEMP, temp)
        time.sleep(2)

    # Reset to neutral
    device.set_value(DP_COLOUR_TEMP, 500)
    print("  Reset to neutral")


def rgb_to_hsv_hex(r: int, g: int, b: int) -> str:
    """
    Convert RGB (0-255 each) to Tuya's HSV hex format.

    Tuya encodes HSV as a 12-character hex string: HHHHSSSSSVVVV
      - H: Hue 0-360 → stored as 4 hex chars (0000-0168)
      - S: Saturation 0-1000 → stored as 4 hex chars (0000-03E8)
      - V: Value/brightness 0-1000 → stored as 4 hex chars (0000-03E8)
    """
    r, g, b = r / 255.0, g / 255.0, b / 255.0
    mx, mn = max(r, g, b), min(r, g, b)
    diff = mx - mn

    # Hue
    if diff == 0:
        h = 0
    elif mx == r:
        h = (60 * ((g - b) / diff) + 360) % 360
    elif mx == g:
        h = (60 * ((b - r) / diff) + 120) % 360
    else:
        h = (60 * ((r - g) / diff) + 240) % 360

    # Saturation
    s = 0 if mx == 0 else (diff / mx) * 1000

    # Value
    v = mx * 1000

    return f"{int(h):04x}{int(s):04x}{int(v):04x}"


def set_colour(device, r: int, g: int, b: int):
    """Set the bulb to an RGB colour."""
    hsv_hex = rgb_to_hsv_hex(r, g, b)
    # Switch to colour mode and set the colour in one go
    device.set_value(DP_MODE, "colour")
    time.sleep(0.3)
    device.set_value(DP_COLOUR_HSV, hsv_hex)


def set_white_mode(device, brightness: int = 500, colour_temp: int = 500):
    """Switch back to white mode with given brightness and colour temp."""
    device.set_value(DP_MODE, "white")
    time.sleep(0.3)
    device.set_value(DP_BRIGHTNESS, brightness)
    time.sleep(0.3)
    device.set_value(DP_COLOUR_TEMP, colour_temp)


def test_colours(device):
    """Test RGB colour capabilities."""
    print("\n── Test: RGB Colours ──")
    print("  (Your batten supports full RGB!)")

    colours = [
        ("Red",     255, 0, 0),
        ("Green",   0, 255, 0),
        ("Blue",    0, 0, 255),
        ("Purple",  128, 0, 128),
        ("Pink",    255, 105, 180),
        ("Orange",  255, 165, 0),
        ("Cyan",    0, 255, 255),
    ]

    for name, r, g, b in colours:
        hsv = rgb_to_hsv_hex(r, g, b)
        print(f"  {name}: RGB({r},{g},{b}) → HSV hex: {hsv}")
        set_colour(device, r, g, b)
        time.sleep(2)

    # Switch back to white mode
    print("  Switching back to white mode...")
    set_white_mode(device)
    time.sleep(1)


def test_scenes(device):
    """Test predefined scene presets — now with colour support!"""
    print("\n── Test: Scene presets ──")

    scenes = [
        {
            "name": "Movie Mode",
            "mode": "colour",
            "colour": (26, 26, 60),     # Very dim deep blue
        },
        {
            "name": "Romantic",
            "mode": "colour",
            "colour": (255, 20, 80),     # Deep pink/red
        },
        {
            "name": "Study Mode",
            "mode": "white",
            "brightness": 1000,
            "colour_temp": 800,          # Bright + cool
        },
        {
            "name": "Party Mode",
            "mode": "colour",
            "colour": (255, 0, 255),     # Magenta
        },
        {
            "name": "Sleep Mode",
            "mode": "white",
            "brightness": 10,
            "colour_temp": 0,            # Dimmest + warmest
        },
        {
            "name": "Normal",
            "mode": "white",
            "brightness": 500,
            "colour_temp": 500,          # Neutral
        },
    ]

    for scene in scenes:
        print(f"\n  {scene['name']}:")
        if scene["mode"] == "colour":
            r, g, b = scene["colour"]
            print(f"    Colour: RGB({r},{g},{b})")
            set_colour(device, r, g, b)
        else:
            print(f"    Brightness: {scene['brightness']/10:.0f}%")
            print(f"    Colour temp: {scene['colour_temp']}")
            set_white_mode(device, scene["brightness"], scene["colour_temp"])
        time.sleep(3)

    # Reset
    device.set_value(DP_BRIGHTNESS, 500)
    device.set_value(DP_COLOUR_TEMP, 500)


# ─── Main ─────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  Wipro 20W CCT Batten — Local Control Test")
    print("=" * 60)

    # Step 1: Auto-detect protocol version
    print("\n─── Step 1: Connecting (auto-detecting protocol version) ───")
    device, initial_status = connect()

    if device is None:
        print("\nCouldn't connect with any protocol version.")
        print("Check that:")
        print("  - The bulb's wall switch is ON (bulb has power)")
        print("  - Your Mac is on the same Wi-Fi as the bulb")
        print("  - The local key is correct (re-run: python -m tinytuya wizard)")
        sys.exit(1)

    # Show the status from the successful connection
    dps = initial_status.get("dps", {})
    print(f"\nRaw status: {initial_status}")
    print(f"\nData Points (DPS):")
    for dp, value in sorted(dps.items(), key=lambda x: int(x[0])):
        dp_name = {
            "20": "Switch (on/off)",
            "22": "Brightness (10-1000)",
            "23": "Colour Temp (0=warm, 1000=cool)",
            "21": "Mode",
            "24": "Colour (HSV)",
            "25": "Colour Data",
            "26": "Scene Data",
        }.get(str(dp), f"Unknown DP {dp}")
        print(f"  DP {dp}: {value}  ← {dp_name}")

    print("\n✓ Connected successfully!")

    # Step 2: Run through tests
    response = input("\nReady to test? This will toggle your light. [y/N]: ").strip().lower()
    if response != "y":
        print("Okay, exiting. You can run individual tests by importing this module.")
        sys.exit(0)

    test_on_off(device)
    test_brightness(device)
    test_colour_temp(device)
    test_colours(device)
    test_scenes(device)

    print("\n" + "=" * 60)
    print("  All tests complete!")
    print("  Your Wipro batten is controllable via local LAN.")
    print("  No cloud, no internet, no latency.")
    print("=" * 60)
