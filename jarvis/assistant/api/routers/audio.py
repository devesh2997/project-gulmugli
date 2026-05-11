"""
Audio I/O endpoints — list outputs/inputs, switch default input,
Bluetooth scan/pair/disconnect.
"""

from fastapi import APIRouter, Depends

from api.auth import verify_token
from api.deps import get_assistant
from api.schemas import (
    AudioInputInfo,
    AudioInputSwitchRequest,
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


@router.get("/api/audio/inputs", response_model=list[AudioInputInfo])
def audio_inputs(assistant: dict = Depends(get_assistant)):
    """List available audio input devices (microphones, line-in, USB capture)."""
    audio = assistant.get("audio")
    if not audio or not hasattr(audio, "list_inputs"):
        return []
    try:
        inputs = audio.list_inputs()
        # Only forward fields the schema recognises; providers may add
        # extras like `description` (ALSA) that would fail validation.
        return [
            AudioInputInfo(
                name=i.get("name", "Unknown"),
                type=i.get("type", "unknown"),
                active=bool(i.get("active", False)),
            )
            for i in inputs
        ]
    except Exception as e:
        log.warning("Failed to list audio inputs: %s", e)
        return []


@router.post("/api/audio/inputs/default", response_model=IntentResponse)
def audio_inputs_set_default(
    req: AudioInputSwitchRequest,
    assistant: dict = Depends(get_assistant),
):
    """Set the system default audio input device by name."""
    audio = assistant.get("audio")
    if not audio or not hasattr(audio, "set_default_input"):
        return IntentResponse(ok=False, error="Audio input switching not supported.")
    try:
        audio.set_default_input(req.name)
        return IntentResponse(ok=True, response=f"Default input set to {req.name}.")
    except Exception as e:
        log.warning("Failed to set default input: %s", e)
        return IntentResponse(ok=False, error=str(e))


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


@router.get("/api/audio/bluetooth/status")
def bluetooth_status(assistant: dict = Depends(get_assistant)) -> dict:
    """
    Status of the AudioSessionManager (preferred-speaker auto-reconnect).

    Returns the manager's snapshot dict (see AudioSessionManager.get_status),
    or an empty `{}` when no manager exists — e.g., no preferred_mac is
    configured, or the audio provider doesn't expose Bluetooth.
    """
    session = assistant.get("audio_session")
    if session is None or not hasattr(session, "get_status"):
        return {}
    try:
        return session.get_status()
    except Exception as e:
        log.warning("audio_session.get_status failed: %s", e)
        return {}


@router.post("/api/audio/bluetooth/reconnect", response_model=IntentResponse)
def bluetooth_reconnect(assistant: dict = Depends(get_assistant)):
    """
    Force an immediate Bluetooth reconnect attempt.

    Used by the dashboard "reconnect now" button when the user notices
    the speaker disconnected and doesn't want to wait for the next
    polling interval. If the daemon is running we just poke its wake
    event; if it's not (inert on Mac, or stopped), we run one
    synchronous attempt for the caller.
    """
    session = assistant.get("audio_session")
    if session is None or not hasattr(session, "force_reconnect"):
        return IntentResponse(
            ok=False,
            error="Bluetooth auto-reconnect not configured.",
        )
    try:
        result = session.force_reconnect()
        return IntentResponse(
            ok=bool(result.get("ok", False)),
            response=result.get("response", "") or "",
            error=result.get("error"),
        )
    except Exception as e:
        log.warning("audio_session.force_reconnect failed: %s", e)
        return IntentResponse(ok=False, error=str(e))
