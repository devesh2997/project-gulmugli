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
    AudioOverrideRequest,
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


# ── Device resolver (priority + override) ─────────────────────────────


@router.get("/api/audio/devices")
def audio_devices(assistant: dict = Depends(get_assistant)) -> dict:
    """
    Combined device list + override state for the dashboard.

    Returns the AudioSessionManager.list_devices_with_state() output —
    every output/input with priority label, active flag, and the
    resolver's selection_source ("override" | "priority" | "default").
    Includes the current override pin (output + input).

    Returns {"outputs": [], "inputs": [], "override": {...}} when there's
    no AudioSessionManager (no preferred BT mac + no resolver config).
    """
    session = assistant.get("audio_session")
    if session is None or not hasattr(session, "list_devices_with_state"):
        return {"outputs": [], "inputs": [], "override": {"output": None, "input": None}}
    try:
        return session.list_devices_with_state()
    except Exception as e:
        log.warning("audio_session.list_devices_with_state failed: %s", e)
        return {"outputs": [], "inputs": [], "override": {"output": None, "input": None}}


@router.post("/api/audio/override", response_model=IntentResponse)
def set_audio_override(
    req: AudioOverrideRequest,
    assistant: dict = Depends(get_assistant),
):
    """
    Pin the output and/or input device.

    Field semantics on the request body:
      - omitted (not in JSON)       — leave that side untouched
      - explicit null               — clear the pin for that side
      - non-empty string            — pin to that PA sink/source name

    Calls apply_resolution() immediately so the switch happens within
    the request — the client doesn't have to wait for the next tick.
    """
    session = assistant.get("audio_session")
    if session is None or not hasattr(session, "apply_resolution"):
        return IntentResponse(
            ok=False,
            error="Audio device resolver not configured.",
        )

    store = getattr(session, "_override_store", None)
    if store is None:
        return IntentResponse(
            ok=False,
            error="Audio override store not configured.",
        )

    # Use model_fields_set to distinguish "omitted" from "explicit null".
    # Pydantic v2 sets `model_fields_set` to the fields the client actually
    # sent; absent fields are NOT in that set even though they have a default.
    try:
        fields = req.model_fields_set
    except AttributeError:
        # Pydantic v1 fallback (unlikely in this codebase but harmless).
        fields = {k for k in ("output", "input") if getattr(req, k, None) is not None}

    if "output" in fields:
        try:
            store.set_output(req.output)
        except Exception as e:
            log.warning("AudioOverrideStore.set_output failed: %s", e)
            return IntentResponse(ok=False, error=f"set_output failed: {e}")

    if "input" in fields:
        try:
            store.set_input(req.input)
        except Exception as e:
            log.warning("AudioOverrideStore.set_input failed: %s", e)
            return IntentResponse(ok=False, error=f"set_input failed: {e}")

    # Re-resolve immediately. The result is informational — we don't
    # surface it in the response body (the dashboard re-polls /devices).
    try:
        session.apply_resolution()
    except Exception as e:
        log.warning("apply_resolution after override failed: %s", e)

    return IntentResponse(ok=True, response="Audio override updated.")


@router.delete("/api/audio/override", response_model=IntentResponse)
def clear_audio_override(assistant: dict = Depends(get_assistant)):
    """Clear BOTH override pins. Re-runs the resolver immediately."""
    session = assistant.get("audio_session")
    if session is None or not hasattr(session, "apply_resolution"):
        return IntentResponse(
            ok=False,
            error="Audio device resolver not configured.",
        )

    store = getattr(session, "_override_store", None)
    if store is None:
        return IntentResponse(
            ok=False,
            error="Audio override store not configured.",
        )

    try:
        store.clear_all()
    except Exception as e:
        log.warning("AudioOverrideStore.clear_all failed: %s", e)
        return IntentResponse(ok=False, error=str(e))

    try:
        session.apply_resolution()
    except Exception as e:
        log.warning("apply_resolution after clear failed: %s", e)

    return IntentResponse(ok=True, response="Audio override cleared.")


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
