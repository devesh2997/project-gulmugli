"""
Tuya light provider — for Wipro IoT bulbs and other Tuya-based smart lights.

Uses tinytuya for local LAN control (no cloud dependency, no internet needed).
Tested with: Wipro 20W LED Batten 5CT (RGB + white, protocol v3.5)

Tuya DPS (Data Points) for this device:
  DP 20: Switch (on/off)         → True/False
  DP 21: Mode                    → "white" or "colour"
  DP 22: Brightness (white mode) → 10-1000
  DP 23: Colour Temperature      → 0 (warm 2700K) to 1000 (cool 6500K)
  DP 24: Colour (HSV hex)        → 12-char hex string HHHHSSSSVVVV

To swap to Philips Hue:
  - Create providers/lights/hue.py
  - Implement LightProvider using phue library
  - Register with @register("lights", "hue")
  - Set lights.provider: "hue" in config.yaml
"""

import time
from core.interfaces import LightProvider
from core.registry import register
from core.config import config

# Tuya data point IDs (standard for Tuya RGB+CCT bulbs/battens)
DP_SWITCH = 20
DP_MODE = 21
DP_BRIGHTNESS = 22
DP_COLOUR_TEMP = 23
DP_COLOUR_HSV = 24


def _rgb_to_hsv_hex(r: int, g: int, b: int) -> str:
    """
    Convert RGB (0-255 each) to Tuya's HSV hex format.

    Tuya encodes HSV as a 12-character hex string: HHHHSSSSVVVV
      - H: Hue 0-360, stored as 4 hex chars
      - S: Saturation 0-1000, stored as 4 hex chars
      - V: Value/brightness 0-1000, stored as 4 hex chars
    """
    r, g, b = r / 255.0, g / 255.0, b / 255.0
    mx, mn = max(r, g, b), min(r, g, b)
    diff = mx - mn

    if diff == 0:
        h = 0
    elif mx == r:
        h = (60 * ((g - b) / diff) + 360) % 360
    elif mx == g:
        h = (60 * ((b - r) / diff) + 120) % 360
    else:
        h = (60 * ((r - g) / diff) + 240) % 360

    s = 0 if mx == 0 else (diff / mx) * 1000
    v = mx * 1000

    return f"{int(h):04x}{int(s):04x}{int(v):04x}"


@register("lights", "tuya")
class TuyaLightProvider(LightProvider):
    """Tuya-based smart light control via local LAN."""

    def __init__(self, **kwargs):
        lights_config = config.get("lights", {})
        self.devices_config = lights_config.get("devices", [])
        self.scenes = lights_config.get("scenes", {})
        self._devices = {}  # lazy-loaded connections

    def _get_device(self, device_name: str):
        """Lazy-load a tinytuya device connection."""
        import tinytuya

        if device_name not in self._devices:
            dev_config = next(
                (d for d in self.devices_config if d["name"] == device_name),
                None,
            )
            if not dev_config:
                raise ValueError(f"Unknown device: {device_name}. Available: {[d['name'] for d in self.devices_config]}")

            device = tinytuya.BulbDevice(
                dev_id=dev_config["device_id"],
                address=dev_config["ip"],
                local_key=dev_config["local_key"],
            )
            device.set_version(dev_config.get("version", 3.5))
            # Short socket timeout — don't hang for 15+ seconds on unreachable devices.
            # 3 seconds is generous for a LAN device. If it's not reachable, fail fast.
            device.set_socketTimeout(3.0)
            self._devices[device_name] = device

        return self._devices[device_name]

    def _get_all_device_names(self) -> list[str]:
        return [d["name"] for d in self.devices_config]

    def _for_devices(self, device_name: str) -> list[str]:
        """Return device names — all of them if 'all', otherwise just the one."""
        if device_name == "all":
            return self._get_all_device_names()
        return [device_name]

    def turn_on(self, device_name: str = "all") -> None:
        for name in self._for_devices(device_name):
            self._get_device(name).set_value(DP_SWITCH, True)

    def turn_off(self, device_name: str = "all") -> None:
        for name in self._for_devices(device_name):
            self._get_device(name).set_value(DP_SWITCH, False)

    def set_color(self, color: str, device_name: str = "all") -> None:
        r, g, b = self._parse_color(color)
        hsv_hex = _rgb_to_hsv_hex(r, g, b)

        for name in self._for_devices(device_name):
            device = self._get_device(name)
            # Switch to colour mode, then set the colour
            device.set_value(DP_MODE, "colour")
            time.sleep(0.3)
            device.set_value(DP_COLOUR_HSV, hsv_hex)

    def set_brightness(self, level: int, device_name: str = "all") -> None:
        # level: 0-100 → Tuya: 10-1000
        tuya_level = max(10, min(1000, int(level * 10)))

        for name in self._for_devices(device_name):
            device = self._get_device(name)
            # Switch to white mode for brightness control
            device.set_value(DP_MODE, "white")
            time.sleep(0.3)
            device.set_value(DP_BRIGHTNESS, tuya_level)

    def set_colour_temperature(self, temp: int, device_name: str = "all") -> None:
        """
        Set colour temperature.
        temp: 0-100 where 0 = warmest (2700K), 100 = coolest (6500K)
        Maps to Tuya range 0-1000.
        """
        tuya_temp = max(0, min(1000, int(temp * 10)))
        for name in self._for_devices(device_name):
            device = self._get_device(name)
            device.set_value(DP_MODE, "white")
            time.sleep(0.3)
            device.set_value(DP_COLOUR_TEMP, tuya_temp)

    def set_scene(self, scene_name: str) -> None:
        scene = self.scenes.get(scene_name)
        if not scene:
            available = list(self.scenes.keys())
            raise ValueError(f"Unknown scene: {scene_name}. Available: {available}")

        if "color" in scene:
            self.set_color(scene["color"])
            # After setting colour, also adjust brightness if specified
            if "brightness" in scene:
                r, g, b = self._parse_color(scene["color"])
                # Scale the RGB values by brightness percentage
                factor = scene["brightness"] / 100.0
                hsv_hex = _rgb_to_hsv_hex(
                    int(r * factor), int(g * factor), int(b * factor)
                )
                for name in self._get_all_device_names():
                    self._get_device(name).set_value(DP_COLOUR_HSV, hsv_hex)
        elif "brightness" in scene:
            self.set_brightness(scene["brightness"])

    def list_devices(self) -> list[dict]:
        return self.devices_config

    @staticmethod
    def _parse_color(color: str) -> tuple[int, int, int]:
        """Parse a color string to RGB. Handles hex (#FF0000) and named colors."""
        named_colors = {
            # English
            "red": (255, 0, 0), "green": (0, 255, 0), "blue": (0, 0, 255),
            "white": (255, 255, 255), "purple": (128, 0, 128),
            "pink": (255, 105, 180), "orange": (255, 165, 0),
            "yellow": (255, 255, 0), "cyan": (0, 255, 255),
            "magenta": (255, 0, 255), "warm": (255, 180, 100),
            "cool": (200, 220, 255), "warm white": (255, 180, 100),
            "cool white": (200, 220, 255),
            # Hindi colour names (as Whisper might transcribe them)
            "neeli": (0, 0, 255),       # blue
            "laal": (255, 0, 0),        # red
            "hara": (0, 255, 0),        # green
            "peeli": (255, 255, 0),     # yellow
            "gulabi": (255, 105, 180),  # pink
            "safed": (255, 255, 255),   # white
            "narangi": (255, 165, 0),   # orange
        }

        if color.lower() in named_colors:
            return named_colors[color.lower()]

        if color.startswith("#") and len(color) == 7:
            return (
                int(color[1:3], 16),
                int(color[3:5], 16),
                int(color[5:7], 16),
            )

        # Default to white if unparseable
        return (255, 255, 255)
