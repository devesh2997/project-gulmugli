"""
Weather endpoints — current conditions and forecast.
"""

from fastapi import APIRouter, Depends, HTTPException

from api.auth import verify_token
from api.deps import get_assistant
from api.schemas import WeatherCurrentResponse, WeatherForecastResponse
from core.config import config
from core.logger import get_logger

log = get_logger("api.weather")

router = APIRouter(dependencies=[Depends(verify_token)])


@router.get("/api/weather/current", response_model=WeatherCurrentResponse)
def weather_current(assistant: dict = Depends(get_assistant)):
    """Get current weather conditions."""
    weather = assistant.get("weather")
    if not weather or not hasattr(weather, "get_current"):
        raise HTTPException(status_code=503, detail="Weather provider not available.")

    location = config.get("weather", {}).get("location", {})
    lat = location.get("lat")
    lon = location.get("lon")

    try:
        data = weather.get_current(lat=lat, lon=lon)
        return WeatherCurrentResponse(**data)
    except Exception as e:
        log.warning("Weather current failed: %s", e)
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/api/weather/forecast", response_model=WeatherForecastResponse)
def weather_forecast(assistant: dict = Depends(get_assistant)):
    """Get weather forecast."""
    weather = assistant.get("weather")
    if not weather or not hasattr(weather, "get_forecast"):
        raise HTTPException(status_code=503, detail="Weather provider not available.")

    location = config.get("weather", {}).get("location", {})
    lat = location.get("lat")
    lon = location.get("lon")

    try:
        data = weather.get_forecast(lat=lat, lon=lon)
        return WeatherForecastResponse(**data)
    except Exception as e:
        log.warning("Weather forecast failed: %s", e)
        raise HTTPException(status_code=503, detail=str(e))
