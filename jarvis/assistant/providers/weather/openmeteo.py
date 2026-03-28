"""
Open-Meteo weather provider — free, no API key, perfect for local-first.

Open-Meteo is an open-source weather API that:
  - Requires NO API key (completely free for non-commercial use)
  - Has decent global coverage with multiple weather model sources
  - Returns JSON with current conditions + hourly/daily forecasts
  - Rate limit: ~10,000 requests/day (more than enough for a voice assistant)

How it works:
  The API takes latitude/longitude and returns weather data from a blend of
  weather models (ECMWF, GFS, DWD, etc.). It auto-selects the best model for
  the given location. The data is updated every 15-60 minutes depending on the
  model, which is why we cache results for 15 minutes.

WMO Weather Codes (used by Open-Meteo):
  Open-Meteo returns a "weathercode" integer based on the WMO standard.
  We map these to human-readable conditions and icon names for the frontend.

Platform notes:
  - Works on all platforms (Mac, Jetson, Pi) — just needs internet
  - Uses stdlib urllib instead of requests to avoid an extra dependency
  - Caches results in memory (no disk cache) — 15 minutes default
  - Gracefully returns None/empty when offline (is_available() + cache fallback)

Usage:
    weather = OpenMeteoWeatherProvider()
    current = weather.get_current(28.6139, 77.2090)  # Delhi
    if current:
        print(f"{current.temperature}°C, {current.description}")
"""

import json
import time
import socket
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Optional

from core.interfaces import WeatherProvider, WeatherData, WeatherForecast, HourlyWeather
from core.registry import register
from core.config import config
from core.logger import get_logger

log = get_logger("weather.openmeteo")

# ── WMO weather code mapping ────────────────────────────────────────
# Maps WMO code → (condition_key, human_description)
# condition_key is used by the frontend for icon selection.
WMO_CODES: dict[int, tuple[str, str]] = {
    0:  ("sunny",          "Clear sky"),
    1:  ("sunny",          "Mainly clear"),
    2:  ("partly_cloudy",  "Partly cloudy"),
    3:  ("cloudy",         "Overcast"),
    45: ("fog",            "Foggy"),
    48: ("fog",            "Depositing rime fog"),
    51: ("rain",           "Light drizzle"),
    53: ("rain",           "Moderate drizzle"),
    55: ("rain",           "Dense drizzle"),
    56: ("rain",           "Light freezing drizzle"),
    57: ("rain",           "Dense freezing drizzle"),
    61: ("rain",           "Slight rain"),
    63: ("rain",           "Moderate rain"),
    65: ("rain",           "Heavy rain"),
    66: ("rain",           "Light freezing rain"),
    67: ("rain",           "Heavy freezing rain"),
    71: ("snow",           "Slight snowfall"),
    73: ("snow",           "Moderate snowfall"),
    75: ("snow",           "Heavy snowfall"),
    77: ("snow",           "Snow grains"),
    80: ("rain",           "Slight rain showers"),
    81: ("rain",           "Moderate rain showers"),
    82: ("rain",           "Violent rain showers"),
    85: ("snow",           "Slight snow showers"),
    86: ("snow",           "Heavy snow showers"),
    95: ("thunderstorm",   "Thunderstorm"),
    96: ("thunderstorm",   "Thunderstorm with slight hail"),
    99: ("thunderstorm",   "Thunderstorm with heavy hail"),
}


def _wmo_to_condition(code: int, is_night: bool = False) -> tuple[str, str]:
    """Convert WMO weather code to (condition_key, description)."""
    condition, description = WMO_CODES.get(code, ("cloudy", "Unknown"))
    # At night, clear sky becomes clear_night
    if is_night and condition == "sunny":
        condition = "clear_night"
        description = "Clear night" if code == 0 else description
    return condition, description


@register("weather", "openmeteo")
class OpenMeteoWeatherProvider(WeatherProvider):
    """
    Open-Meteo weather — free, no API key, auto-selects best model.

    Config (config.yaml):
        weather:
          provider: "openmeteo"
          location:
            lat: 28.6139
            lon: 77.2090
            name: "New Delhi"
          units: "celsius"
          cache_minutes: 15
    """

    BASE_URL = "https://api.open-meteo.com/v1/forecast"

    def __init__(self, **kwargs):
        weather_cfg = config.get("weather", {})
        location = weather_cfg.get("location", {})
        self._default_lat = location.get("lat", 28.6139)
        self._default_lon = location.get("lon", 77.2090)
        self._location_name = location.get("name", "New Delhi")
        self._units = weather_cfg.get("units", "celsius")
        self._cache_minutes = weather_cfg.get("cache_minutes", 15)

        # In-memory cache: key → (timestamp, data)
        self._cache: dict[str, tuple[float, any]] = {}

        # Availability check cache
        self._available: bool | None = None

        log.info(
            "Open-Meteo weather provider ready (location=%s, units=%s, cache=%dm)",
            self._location_name, self._units, self._cache_minutes,
        )

    @property
    def location_name(self) -> str:
        return self._location_name

    # ── Cache helpers ───────────────────────────────────────────────

    def _cache_get(self, key: str):
        """Return cached value if still fresh, else None."""
        if key in self._cache:
            ts, data = self._cache[key]
            if time.time() - ts < self._cache_minutes * 60:
                return data
        return None

    def _cache_set(self, key: str, data):
        """Store data in cache with current timestamp."""
        self._cache[key] = (time.time(), data)

    # ── API call helper ─────────────────────────────────────────────

    def _fetch_json(self, params: dict) -> Optional[dict]:
        """Make a GET request to Open-Meteo and return parsed JSON."""
        # Build query string
        query = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{self.BASE_URL}?{query}"

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "JarvisAssistant/1.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.URLError as e:
            log.warning("Open-Meteo request failed: %s", e)
            self._available = None  # reset availability cache
            return None
        except Exception as e:
            log.warning("Open-Meteo unexpected error: %s", e)
            return None

    # ── Temperature unit helpers ────────────────────────────────────

    def _temp_unit_param(self) -> str:
        """Return Open-Meteo temperature unit parameter."""
        return "fahrenheit" if self._units == "fahrenheit" else "celsius"

    def _wind_unit_param(self) -> str:
        """Return Open-Meteo wind speed unit parameter."""
        return "mph" if self._units == "fahrenheit" else "kmh"

    # ── Interface methods ───────────────────────────────────────────

    def get_current(self, lat: float = 0, lon: float = 0) -> Optional[WeatherData]:
        lat = lat or self._default_lat
        lon = lon or self._default_lon

        cache_key = f"current:{lat:.4f},{lon:.4f}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            log.debug("Weather cache hit for current conditions")
            return cached

        temp_unit = self._temp_unit_param()
        wind_unit = self._wind_unit_param()

        data = self._fetch_json({
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,"
                       "weather_code,wind_speed_10m,surface_pressure",
            "daily": "sunrise,sunset,uv_index_max",
            "temperature_unit": temp_unit,
            "wind_speed_unit": wind_unit,
            "timezone": "auto",
            "forecast_days": 1,
        })

        if not data or "current" not in data:
            # Try returning stale cache if we have one
            if cache_key in self._cache:
                _, stale = self._cache[cache_key]
                log.info("Returning stale weather cache (API unavailable)")
                return stale
            return None

        current = data["current"]
        daily = data.get("daily", {})

        # Determine if it's night for icon selection
        is_night = False
        try:
            now_str = current.get("time", "")
            sunrise_str = daily.get("sunrise", [""])[0]
            sunset_str = daily.get("sunset", [""])[0]
            if now_str and sunrise_str and sunset_str:
                now_hour = int(now_str.split("T")[1].split(":")[0])
                sunrise_hour = int(sunrise_str.split("T")[1].split(":")[0])
                sunset_hour = int(sunset_str.split("T")[1].split(":")[0])
                is_night = now_hour < sunrise_hour or now_hour >= sunset_hour
        except (IndexError, ValueError):
            pass

        wmo_code = current.get("weather_code", 0)
        condition, description = _wmo_to_condition(wmo_code, is_night)

        # Extract sunrise/sunset as HH:MM
        sunrise = ""
        sunset = ""
        try:
            sunrise = daily["sunrise"][0].split("T")[1][:5]
            sunset = daily["sunset"][0].split("T")[1][:5]
        except (KeyError, IndexError):
            pass

        result = WeatherData(
            temperature=current.get("temperature_2m", 0),
            feels_like=current.get("apparent_temperature", 0),
            humidity=current.get("relative_humidity_2m", 0),
            wind_speed=current.get("wind_speed_10m", 0),
            condition=condition,
            description=description,
            icon=condition,
            sunrise=sunrise,
            sunset=sunset,
            uv_index=daily.get("uv_index_max", [0])[0] if daily.get("uv_index_max") else 0,
            pressure=current.get("surface_pressure", 0),
        )

        self._cache_set(cache_key, result)
        log.info(
            "Weather: %.1f°%s, %s (%s)",
            result.temperature,
            "F" if self._units == "fahrenheit" else "C",
            result.description,
            self._location_name,
        )
        return result

    def get_forecast(self, lat: float = 0, lon: float = 0, days: int = 3) -> list[WeatherForecast]:
        lat = lat or self._default_lat
        lon = lon or self._default_lon

        cache_key = f"forecast:{lat:.4f},{lon:.4f}:{days}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        temp_unit = self._temp_unit_param()
        wind_unit = self._wind_unit_param()

        data = self._fetch_json({
            "latitude": lat,
            "longitude": lon,
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
                     "precipitation_probability_max,relative_humidity_2m_max,"
                     "wind_speed_10m_max",
            "temperature_unit": temp_unit,
            "wind_speed_unit": wind_unit,
            "timezone": "auto",
            "forecast_days": min(days, 7),
        })

        if not data or "daily" not in data:
            if cache_key in self._cache:
                _, stale = self._cache[cache_key]
                return stale
            return []

        daily = data["daily"]
        forecasts = []
        for i in range(len(daily.get("time", []))):
            wmo_code = daily["weather_code"][i] if i < len(daily.get("weather_code", [])) else 0
            condition, description = _wmo_to_condition(wmo_code)
            forecasts.append(WeatherForecast(
                date=daily["time"][i],
                temp_max=daily.get("temperature_2m_max", [0])[i],
                temp_min=daily.get("temperature_2m_min", [0])[i],
                condition=condition,
                description=description,
                icon=condition,
                humidity=daily.get("relative_humidity_2m_max", [0])[i],
                wind_speed=daily.get("wind_speed_10m_max", [0])[i],
                precipitation_chance=daily.get("precipitation_probability_max", [0])[i],
            ))

        self._cache_set(cache_key, forecasts)
        return forecasts

    def get_hourly(self, lat: float = 0, lon: float = 0, hours: int = 12) -> list[HourlyWeather]:
        lat = lat or self._default_lat
        lon = lon or self._default_lon

        cache_key = f"hourly:{lat:.4f},{lon:.4f}:{hours}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        temp_unit = self._temp_unit_param()

        data = self._fetch_json({
            "latitude": lat,
            "longitude": lon,
            "hourly": "temperature_2m,weather_code,precipitation_probability",
            "temperature_unit": temp_unit,
            "timezone": "auto",
            "forecast_hours": min(hours, 48),
        })

        if not data or "hourly" not in data:
            if cache_key in self._cache:
                _, stale = self._cache[cache_key]
                return stale
            return []

        hourly = data["hourly"]
        results = []
        # Only take future hours up to the requested count
        now = datetime.now()
        count = 0
        for i in range(len(hourly.get("time", []))):
            if count >= hours:
                break
            try:
                hour_time = datetime.fromisoformat(hourly["time"][i])
                if hour_time < now:
                    continue
            except (ValueError, KeyError):
                continue

            wmo_code = hourly.get("weather_code", [0])[i] if i < len(hourly.get("weather_code", [])) else 0
            condition, _ = _wmo_to_condition(wmo_code)

            time_str = hourly["time"][i].split("T")[1][:5] if "T" in hourly["time"][i] else ""

            results.append(HourlyWeather(
                time=time_str,
                temperature=hourly.get("temperature_2m", [0])[i],
                condition=condition,
                icon=condition,
                precipitation_chance=hourly.get("precipitation_probability", [0])[i] or 0,
            ))
            count += 1

        self._cache_set(cache_key, results)
        return results

    def is_available(self) -> bool:
        """
        Check connectivity to Open-Meteo via raw socket (fast, no rate limit hit).
        Caches the result within the session.
        """
        if self._available is not None:
            return self._available

        try:
            sock = socket.create_connection(("api.open-meteo.com", 443), timeout=2)
            sock.close()
            self._available = True
        except (socket.timeout, OSError):
            self._available = False
            log.info("Internet not available — weather features disabled")

        return self._available
