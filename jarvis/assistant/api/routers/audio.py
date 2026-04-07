"""
Audio output endpoints — list outputs, Bluetooth scan/pair/disconnect.
"""

from fastapi import APIRouter, Depends

from api.auth import verify_token
from api.deps import get_assistant
from api.schemas import (
    AudioOutputInfo,
    BluetoothActionRequest,
    BluetoothDeviceInfo,
    IntentResponse,
)
from core.logger import get_logger

log = get_logger("api.audio")

router = APIRouter(dependencies=[Depends(verify_token)])


@router.get("/api/audio/outputs", response_model=list[AudioOutputInfo])
def audio_outputs(assistant: dict = Depends(get_assistant)):
    """List available audio output devices."""
    audio = assistant.get("audio")
    if not audio or not hasattr(audio, "list_outputs"):
        return []
    try:
        outputs = audio.list_outputs()
        return [AudioOutputInfo(**o) for o in outputs]
    except Exception as e:
        log.warning("Failed to list audio outputs: %s", e)
        return []


@router.post("/api/audio/bluetooth/scan", response_model=list[BluetoothDeviceInfo])
def bluetooth_scan(assistant: dict = Depends(get_assistant)):
    """Scan for nearby Bluetooth audio devices."""
    audio = assistant.get("audio")
    if not audio or not hasattr(audio, "bluetooth_scan"):
        return []
    try:
        devices = audio.bluetooth_scan()
        return [BluetoothDeviceInfo(**d) for d in devices]
    except Exception as e:
        log.warning("Bluetooth scan failed: %s", e)
        return []


@router.post("/api/audio/bluetooth/pair", response_model=IntentResponse)
def bluetooth_pair(
    req: BluetoothActionRequest,
    assistant: dict = Depends(get_assistant),
):
    """Pair with a Bluetooth audio device."""
    audio = assistant.get("audio")
    if not audio or not hasattr(audio, "bluetooth_pair"):
        return IntentResponse(ok=False, error="Audio provider not available.")
    try:
        audio.bluetooth_pair(req.mac_address)
        return IntentResponse(ok=True, response=f"Paired with {req.mac_address}.")
    except Exception as e:
        log.warning("Bluetooth pair failed: %s", e)
        return IntentResponse(ok=False, error=str(e))


@router.post("/api/audio/bluetooth/disconnect", response_model=IntentResponse)
def bluetooth_disconnect(
    req: BluetoothActionRequest,
    assistant: dict = Depends(get_assistant),
):
    """Disconnect a Bluetooth audio device."""
    audio = assistant.get("audio")
    if not audio or not hasattr(audio, "bluetooth_disconnect"):
        return IntentResponse(ok=False, error="Audio provider not available.")
    try:
        audio.bluetooth_disconnect(req.mac_address)
        return IntentResponse(ok=True, response=f"Disconnected {req.mac_address}.")
    except Exception as e:
        log.warning("Bluetooth disconnect failed: %s", e)
        return IntentResponse(ok=False, error=str(e))
