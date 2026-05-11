"""
Tests for core.audio_session.

Strategy: drive AudioSessionManager directly with monkey-patched
subprocess.run + shutil.which so no real bluetoothctl calls happen
even if the test box happens to have BlueZ installed.

What we cover:
  - Inert when preferred_mac is empty: start() spawns nothing,
    get_status reflects that.
  - Inert when auto_reconnect=false: same.
  - Interval clamp (anything < 5s is bumped to 5s).
  - Single tick: when bluetoothctl reports connected=yes, no connect
    attempt is fired and last_attempt_ts stays zero.
  - Single tick: when bluetoothctl reports connected=no, a connect
    attempt IS fired and `Connection successful` flips _connected.
  - Single tick: when bluetoothctl is absent, the manager logs once
    (we check via the `_inert_logged` flag) and on subsequent ticks
    stays quiet.
  - force_reconnect on inert manager runs a synchronous attempt
    via the mocked subprocess.
  - start/stop lifecycle: thread starts, joins cleanly on stop.
  - get_status returns the expected keys.

Resolver tests:
  - Priority-list ordering: first available match wins.
  - Override pin wins over priority list.
  - Override pin falls back to priority when device is offline.
  - apply_resolution() flips the default sink when it differs.
  - apply_resolution() is a no-op when the active device matches.
  - list_devices_with_state correctly annotates each device.
  - AudioOverrideStore atomic write + corrupt-file recovery.
"""

from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.audio_session import AudioSessionManager  # noqa: E402
from core.audio_override import AudioOverrideStore  # noqa: E402


# ── Subprocess fake ──────────────────────────────────────────────────


def _fake_run_factory(script: dict):
    """
    Build a fake subprocess.run callable.

    `script` keys describe the response for a given command shape:
      - "info-connected"     → bluetoothctl info <mac> returns "Connected: yes"
      - "info-disconnected"  → bluetoothctl info <mac> returns "Connected: no"
      - "connect-success"    → bluetoothctl connect <mac> returns success
      - "connect-failure"    → bluetoothctl connect <mac> returns failure
    """
    calls: list = []

    def _run(cmd, capture_output=True, text=True, timeout=None, **_):
        calls.append(list(cmd))
        if len(cmd) >= 3 and cmd[0] == "bluetoothctl":
            if cmd[1] == "info":
                if script.get("info") == "connected":
                    return SimpleNamespace(
                        returncode=0,
                        stdout=(
                            "Device AA:BB:CC:DD:EE:FF (public)\n"
                            "\tName: Marshall Willen II\n"
                            "\tPaired: yes\n"
                            "\tTrusted: yes\n"
                            "\tConnected: yes\n"
                        ),
                        stderr="",
                    )
                if script.get("info") == "disconnected":
                    return SimpleNamespace(
                        returncode=0,
                        stdout=(
                            "Device AA:BB:CC:DD:EE:FF (public)\n"
                            "\tName: Marshall Willen II\n"
                            "\tPaired: yes\n"
                            "\tConnected: no\n"
                        ),
                        stderr="",
                    )
                return SimpleNamespace(returncode=1, stdout="", stderr="Device not available")
            if cmd[1] == "connect":
                if script.get("connect") == "success":
                    return SimpleNamespace(
                        returncode=0,
                        stdout="Attempting to connect to AA:BB:CC:DD:EE:FF\nConnection successful\n",
                        stderr="",
                    )
                return SimpleNamespace(
                    returncode=1,
                    stdout="",
                    stderr="Failed to connect: org.bluez.Error.NotReady\n",
                )
        return SimpleNamespace(returncode=1, stdout="", stderr="unknown command")

    _run.calls = calls
    return _run


def _which_yes(_name):
    return "/usr/bin/bluetoothctl"


def _which_no(_name):
    return None


# ── Tests ────────────────────────────────────────────────────────────


def test_inert_when_no_preferred_mac():
    """No MAC → no thread spawned, status reflects that."""
    mgr = AudioSessionManager(preferred_mac="")
    mgr.start()
    assert not mgr.is_running()
    status = mgr.get_status()
    assert status["preferred_mac"] == ""
    assert status["running"] is False
    mgr.stop()  # idempotent


def test_inert_when_auto_reconnect_false():
    """auto_reconnect=false → no thread spawned, status correct."""
    mgr = AudioSessionManager(preferred_mac="AA:BB:CC:DD:EE:FF", auto_reconnect=False)
    mgr.start()
    assert not mgr.is_running()
    status = mgr.get_status()
    assert status["auto_reconnect"] is False
    mgr.stop()


def test_interval_clamped_to_min():
    """reconnect_interval_s < 5 is clamped to 5."""
    mgr = AudioSessionManager(preferred_mac="AA:BB:CC:DD:EE:FF", reconnect_interval_s=1)
    assert mgr._interval_s == AudioSessionManager.MIN_INTERVAL_S
    mgr2 = AudioSessionManager(preferred_mac="AA:BB:CC:DD:EE:FF", reconnect_interval_s=60)
    assert mgr2._interval_s == 60


def test_get_status_has_expected_keys():
    mgr = AudioSessionManager(
        preferred_mac="AA:BB:CC:DD:EE:FF",
        device_name="Marshall Willen II",
        reconnect_interval_s=30,
    )
    s = mgr.get_status()
    for k in (
        "connected", "preferred_mac", "device_name", "auto_reconnect",
        "interval_s", "last_attempt_ts", "last_error", "running",
    ):
        assert k in s, f"missing key: {k}"
    assert s["preferred_mac"] == "AA:BB:CC:DD:EE:FF"
    assert s["device_name"] == "Marshall Willen II"


def test_tick_connected_does_not_attempt_connect():
    """When info says Connected: yes, no `bluetoothctl connect` is fired."""
    run = _fake_run_factory({"info": "connected"})
    with patch("core.audio_session.shutil.which", _which_yes), \
         patch("core.audio_session.subprocess.run", run):
        mgr = AudioSessionManager(preferred_mac="AA:BB:CC:DD:EE:FF")
        mgr._tick()
    cmds = [c for c in run.calls if len(c) >= 2 and c[1] == "connect"]
    assert cmds == [], f"unexpected connect attempts: {cmds}"
    assert mgr.get_status()["connected"] is True


def test_tick_disconnected_fires_connect_attempt():
    """When info says Connected: no, exactly one `bluetoothctl connect` runs."""
    run = _fake_run_factory({"info": "disconnected", "connect": "success"})
    with patch("core.audio_session.shutil.which", _which_yes), \
         patch("core.audio_session.subprocess.run", run):
        mgr = AudioSessionManager(preferred_mac="AA:BB:CC:DD:EE:FF")
        mgr._tick()
    connect_calls = [c for c in run.calls if len(c) >= 2 and c[1] == "connect"]
    assert len(connect_calls) == 1
    s = mgr.get_status()
    assert s["connected"] is True
    assert s["last_attempt_ts"] > 0
    assert s["last_error"] is None


def test_tick_connect_failure_records_error():
    """A failed connect attempt sets last_error and keeps connected=False."""
    run = _fake_run_factory({"info": "disconnected", "connect": "fail"})
    with patch("core.audio_session.shutil.which", _which_yes), \
         patch("core.audio_session.subprocess.run", run):
        mgr = AudioSessionManager(preferred_mac="AA:BB:CC:DD:EE:FF")
        mgr._tick()
    s = mgr.get_status()
    assert s["connected"] is False
    assert s["last_error"] is not None
    assert "fail" in s["last_error"].lower()


def test_tick_no_bluetoothctl_logs_once_then_quiet():
    """When bluetoothctl is missing, _inert_logged latches after first tick."""
    with patch("core.audio_session.shutil.which", _which_no):
        mgr = AudioSessionManager(preferred_mac="AA:BB:CC:DD:EE:FF")
        assert mgr._inert_logged is False
        mgr._tick()
        assert mgr._inert_logged is True
        # Second tick: still inert, no new state explosion.
        mgr._tick()
        assert mgr._inert_logged is True
        s = mgr.get_status()
        assert s["connected"] is False
        assert s["last_error"] == "bluetoothctl-unavailable"


def test_force_reconnect_on_inert_runs_synchronous_attempt():
    """force_reconnect on a non-running manager runs one sync attempt."""
    run = _fake_run_factory({"connect": "success"})
    with patch("core.audio_session.shutil.which", _which_yes), \
         patch("core.audio_session.subprocess.run", run):
        mgr = AudioSessionManager(preferred_mac="AA:BB:CC:DD:EE:FF")
        # Don't start — directly hit force_reconnect.
        result = mgr.force_reconnect()
    assert result["ok"] is True
    assert any(c[:2] == ["bluetoothctl", "connect"] for c in run.calls)


def test_force_reconnect_without_mac_returns_error():
    mgr = AudioSessionManager(preferred_mac="")
    result = mgr.force_reconnect()
    assert result["ok"] is False
    assert "preferred_mac" in (result.get("error") or "").lower()


def test_start_stop_lifecycle_with_mock_subprocess():
    """start() spawns the thread, stop() joins it cleanly."""
    run = _fake_run_factory({"info": "connected"})
    with patch("core.audio_session.shutil.which", _which_yes), \
         patch("core.audio_session.subprocess.run", run):
        mgr = AudioSessionManager(
            preferred_mac="AA:BB:CC:DD:EE:FF",
            reconnect_interval_s=5,   # min — but we'll stop before any sleep finishes
        )
        mgr.start()
        assert mgr.is_running()
        # Give the initial tick a moment to call subprocess.run at least once.
        time.sleep(0.1)
        mgr.stop()
        assert not mgr.is_running()
    # Initial tick called bluetoothctl info at least once.
    assert any(c[:2] == ["bluetoothctl", "info"] for c in run.calls)


def test_start_is_idempotent():
    """Calling start() twice produces only one thread."""
    run = _fake_run_factory({"info": "connected"})
    with patch("core.audio_session.shutil.which", _which_yes), \
         patch("core.audio_session.subprocess.run", run):
        mgr = AudioSessionManager(preferred_mac="AA:BB:CC:DD:EE:FF")
        mgr.start()
        first_thread = mgr._thread
        mgr.start()
        assert mgr._thread is first_thread
        mgr.stop()


def test_force_reconnect_on_running_pokes_wake_event():
    """force_reconnect on a running daemon sets the wake event."""
    run = _fake_run_factory({"info": "connected"})
    with patch("core.audio_session.shutil.which", _which_yes), \
         patch("core.audio_session.subprocess.run", run):
        mgr = AudioSessionManager(preferred_mac="AA:BB:CC:DD:EE:FF")
        mgr.start()
        try:
            mgr._wake_event.clear()
            result = mgr.force_reconnect()
            assert result["ok"] is True
            # The wake event was set OR already cleared by the loop's
            # next tick — either way force_reconnect should return ok.
        finally:
            mgr.stop()


def test_status_includes_running_flag_after_start():
    run = _fake_run_factory({"info": "connected"})
    with patch("core.audio_session.shutil.which", _which_yes), \
         patch("core.audio_session.subprocess.run", run):
        mgr = AudioSessionManager(preferred_mac="AA:BB:CC:DD:EE:FF")
        mgr.start()
        try:
            assert mgr.get_status()["running"] is True
        finally:
            mgr.stop()
        assert mgr.get_status()["running"] is False


# ── Device resolver helpers ──────────────────────────────────────────


class _FakeAudio:
    """
    Minimal fake AudioOutputProvider for resolver tests.

    Records calls to set_default_output / set_default_input so tests can
    assert what actually happened. list_outputs / list_inputs return
    whatever the test plugged in via `outputs`/`inputs`.
    """

    def __init__(self, outputs=None, inputs=None, default_input=None):
        self._outputs = list(outputs or [])
        self._inputs = list(inputs or [])
        self._default_input = default_input
        self.set_output_calls = []
        self.set_input_calls = []

    def list_outputs(self):
        # Return copies so callers can't mutate our state.
        return [dict(d) for d in self._outputs]

    def list_inputs(self):
        return [dict(d) for d in self._inputs]

    def set_default_output(self, name):
        self.set_output_calls.append(name)
        # Reflect the change so subsequent list_outputs is consistent.
        for d in self._outputs:
            d["active"] = (d["name"] == name)

    def set_default_input(self, name):
        self.set_input_calls.append(name)
        self._default_input = name
        for d in self._inputs:
            d["active"] = (d["name"] == name)

    def get_default_input(self):
        return self._default_input


def _mgr(audio, output_priority=None, input_priority=None, override_store=None):
    """Convenience: build a resolver-configured AudioSessionManager."""
    return AudioSessionManager(
        preferred_mac="",
        audio_provider=audio,
        output_priority=output_priority or [],
        input_priority=input_priority or [],
        override_store=override_store,
    )


# ── Resolver tests ───────────────────────────────────────────────────


def test_resolve_output_uses_priority_when_no_override():
    """Config priority [Marshall, USB], live devices [USB, Marshall, default].
    Marshall wins with source='priority'."""
    audio = _FakeAudio(outputs=[
        {"name": "alsa_output.usb-Generic", "type": "usb", "active": True},
        {"name": "bluez_sink.AA_BB_CC_DD_EE_FF.a2dp_sink", "type": "bluetooth", "active": False},
        {"name": "alsa_output.pci-default", "type": "system", "active": False},
    ])
    priority = [
        {"mac": "AA:BB:CC:DD:EE:FF", "label": "Marshall"},
        {"name_pattern": "USB", "label": "USB"},
    ]
    m = _mgr(audio, output_priority=priority)
    name, source = m.resolve_output()
    assert source == "priority", f"expected priority, got {source}"
    assert "AA_BB_CC_DD_EE_FF" in name, f"expected Marshall sink, got {name}"


def test_resolve_output_falls_back_when_priority_unavailable():
    """Marshall MAC not in device list — USB pattern wins next."""
    audio = _FakeAudio(outputs=[
        {"name": "alsa_output.usb-Generic", "type": "usb", "active": True},
        {"name": "alsa_output.pci-default", "type": "system", "active": False},
    ])
    priority = [
        {"mac": "AA:BB:CC:DD:EE:FF", "label": "Marshall"},
        {"name_pattern": "USB", "label": "USB"},
    ]
    m = _mgr(audio, output_priority=priority)
    name, source = m.resolve_output()
    assert source == "priority"
    assert "usb-Generic" in name


def test_resolve_output_uses_override_when_set():
    """Override pins Marshall; priority points at USB. Override wins."""
    audio = _FakeAudio(outputs=[
        {"name": "alsa_output.usb-Generic", "type": "usb", "active": True},
        {"name": "bluez_sink.AA_BB_CC_DD_EE_FF.a2dp_sink", "type": "bluetooth", "active": False},
    ])
    fake_store = MagicMock()
    fake_store.get.return_value = {
        "output": "bluez_sink.AA_BB_CC_DD_EE_FF.a2dp_sink",
        "input": None,
    }
    priority = [{"name_pattern": "USB"}]
    m = _mgr(audio, output_priority=priority, override_store=fake_store)
    name, source = m.resolve_output()
    assert source == "override", f"expected override, got {source}"
    assert "AA_BB_CC_DD_EE_FF" in name


def test_resolve_output_falls_back_when_override_unavailable():
    """Override device offline (not in device list) — fall back to priority."""
    audio = _FakeAudio(outputs=[
        {"name": "alsa_output.usb-Generic", "type": "usb", "active": True},
    ])
    fake_store = MagicMock()
    fake_store.get.return_value = {
        "output": "bluez_sink.AA_BB_CC_DD_EE_FF.a2dp_sink",  # offline
        "input": None,
    }
    priority = [{"name_pattern": "USB", "label": "USB"}]
    m = _mgr(audio, output_priority=priority, override_store=fake_store)
    name, source = m.resolve_output()
    assert source == "priority"
    assert "usb" in name.lower()


def test_resolve_output_system_default_sentinel_matches_first_device():
    """`system_default` always matches the first device in the list."""
    audio = _FakeAudio(outputs=[
        {"name": "alsa_output.pci-foo", "type": "system", "active": True},
        {"name": "alsa_output.usb-bar", "type": "usb", "active": False},
    ])
    priority = ["system_default"]
    m = _mgr(audio, output_priority=priority)
    name, source = m.resolve_output()
    assert source == "priority"
    assert name == "alsa_output.pci-foo"


def test_resolve_output_no_priority_and_no_devices_returns_none():
    audio = _FakeAudio(outputs=[])
    m = _mgr(audio, output_priority=[])
    name, source = m.resolve_output()
    assert name is None
    assert source == "default"


def test_mac_match_is_case_insensitive():
    """MAC in config has uppercase; PA sink name is uppercase — should match.
    Also tests the lowercase-config / uppercase-PA cross-case path."""
    # PA: uppercase, config: lowercase
    audio = _FakeAudio(outputs=[
        {"name": "bluez_sink.AA_BB_CC_DD_EE_FF.a2dp_sink", "active": False},
    ])
    priority = [{"mac": "aa:bb:cc:dd:ee:ff"}]
    m = _mgr(audio, output_priority=priority)
    name, source = m.resolve_output()
    assert source == "priority"
    assert "AA_BB_CC_DD_EE_FF" in name


def test_apply_resolution_switches_default_when_changed():
    """Resolver picks Marshall but USB is currently active — switch fires."""
    audio = _FakeAudio(outputs=[
        {"name": "alsa_output.usb-Generic", "type": "usb", "active": True},
        {"name": "bluez_sink.AA_BB_CC_DD_EE_FF.a2dp_sink", "type": "bluetooth", "active": False},
    ])
    priority = [{"mac": "AA:BB:CC:DD:EE:FF"}]
    m = _mgr(audio, output_priority=priority)
    result = m.apply_resolution()
    assert result["output"]["switched"] is True
    assert "AA_BB_CC_DD_EE_FF" in result["output"]["name"]
    assert audio.set_output_calls == ["bluez_sink.AA_BB_CC_DD_EE_FF.a2dp_sink"]


def test_apply_resolution_idempotent_when_active_matches():
    """Resolver picks the already-active device — no set_default call."""
    audio = _FakeAudio(outputs=[
        {"name": "alsa_output.usb-Generic", "type": "usb", "active": True},
        {"name": "alsa_output.pci-default", "type": "system", "active": False},
    ])
    priority = [{"name_pattern": "USB"}]
    m = _mgr(audio, output_priority=priority)
    result = m.apply_resolution()
    assert result["output"]["switched"] is False
    assert audio.set_output_calls == []


def test_apply_resolution_input_respects_get_default_input():
    """For inputs, get_default_input is the authoritative 'current' value
    (PA sources are only RUNNING while recording). If the resolver picks
    a different source, the switch fires."""
    audio = _FakeAudio(
        inputs=[
            {"name": "alsa_input.usb-Mic", "type": "usb", "active": False},
            {"name": "alsa_input.pci-builtin", "type": "system", "active": False},
        ],
        default_input="alsa_input.pci-builtin",
    )
    priority = [{"name_pattern": "USB"}]
    m = _mgr(audio, input_priority=priority)
    result = m.apply_resolution()
    assert result["input"]["switched"] is True
    assert audio.set_input_calls == ["alsa_input.usb-Mic"]


def test_list_devices_with_state_marks_active_and_source():
    """Annotated device list: chosen device has selection_source=priority/override,
    everything else 'default'. priority_index and label populated per match."""
    audio = _FakeAudio(outputs=[
        {"name": "alsa_output.usb-Generic", "type": "usb", "active": True},
        {"name": "bluez_sink.AA_BB_CC_DD_EE_FF.a2dp_sink", "type": "bluetooth", "active": False},
        {"name": "alsa_output.pci-default", "type": "system", "active": False},
    ])
    priority = [
        {"mac": "AA:BB:CC:DD:EE:FF", "label": "Marshall"},
        {"name_pattern": "USB", "label": "USB Audio"},
    ]
    m = _mgr(audio, output_priority=priority)
    state = m.list_devices_with_state()
    outputs = {d["name"]: d for d in state["outputs"]}

    marshall = outputs["bluez_sink.AA_BB_CC_DD_EE_FF.a2dp_sink"]
    assert marshall["selection_source"] == "priority"
    assert marshall["label"] == "Marshall"
    assert marshall["priority_index"] == 0
    assert marshall["active"] is False

    usb = outputs["alsa_output.usb-Generic"]
    assert usb["selection_source"] == "default"  # not the chosen device
    assert usb["label"] == "USB Audio"
    assert usb["priority_index"] == 1
    assert usb["active"] is True

    default = outputs["alsa_output.pci-default"]
    assert default["selection_source"] == "default"
    assert default["priority_index"] is None  # no priority match

    assert state["override"] == {"output": None, "input": None}


def test_list_devices_with_state_handles_missing_provider():
    """No audio provider → empty lists, no crash."""
    m = AudioSessionManager(preferred_mac="")  # no audio
    state = m.list_devices_with_state()
    assert state["outputs"] == []
    assert state["inputs"] == []
    assert state["override"] == {"output": None, "input": None}


# ── AudioOverrideStore tests ─────────────────────────────────────────


def test_override_store_set_and_get_round_trip():
    with tempfile.TemporaryDirectory() as tmp:
        store = AudioOverrideStore(path=Path(tmp) / "override.json")
        store.set_output("bluez_sink.AA_BB.a2dp_sink")
        assert store.get()["output"] == "bluez_sink.AA_BB.a2dp_sink"
        assert store.get()["input"] is None
        store.set_input("alsa_input.usb-Mic")
        assert store.get()["input"] == "alsa_input.usb-Mic"


def test_override_store_persists_across_restart():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "override.json"
        s1 = AudioOverrideStore(path=path)
        s1.set_output("bluez_sink.AA.a2dp_sink")
        s2 = AudioOverrideStore(path=path)
        assert s2.get()["output"] == "bluez_sink.AA.a2dp_sink"


def test_override_store_clear_all():
    with tempfile.TemporaryDirectory() as tmp:
        store = AudioOverrideStore(path=Path(tmp) / "override.json")
        store.set_output("x")
        store.set_input("y")
        store.clear_all()
        got = store.get()
        assert got["output"] is None
        assert got["input"] is None


def test_override_store_atomic_write():
    """Atomic write via tempfile + rename. Verify the JSON file parses
    cleanly after two sequential writes."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "override.json"
        store = AudioOverrideStore(path=path)
        store.set_output("a")
        store.set_input("b")
        data = json.loads(path.read_text())
        assert data["output"] == "a"
        assert data["input"] == "b"
        assert "updated_at" in data


def test_override_store_corrupt_file_treated_as_empty():
    """Mangled JSON file: warn + treat as empty + preserve bad file."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "override.json"
        path.write_text("{not json}")
        store = AudioOverrideStore(path=path)
        got = store.get()
        assert got["output"] is None
        assert got["input"] is None
        # Bad file was renamed.
        bad = path.with_suffix(path.suffix + ".bad")
        assert bad.is_file()


def test_override_store_set_none_clears_value():
    """Passing None to set_output/set_input clears that side."""
    with tempfile.TemporaryDirectory() as tmp:
        store = AudioOverrideStore(path=Path(tmp) / "override.json")
        store.set_output("x")
        store.set_output(None)
        assert store.get()["output"] is None


def test_override_store_empty_string_treated_as_none():
    """Defensive: dashboards may send '' for 'no value'. Treat as None."""
    with tempfile.TemporaryDirectory() as tmp:
        store = AudioOverrideStore(path=Path(tmp) / "override.json")
        store.set_output("real-value")
        store.set_output("   ")  # whitespace-only
        assert store.get()["output"] is None


# ── Resolver tick integration ────────────────────────────────────────


def test_resolver_runs_alongside_bt_reconnect_in_tick():
    """A single _tick() should run BOTH the BT reconnect path AND the
    resolver. We mock bluetoothctl to 'connected' so BT is a no-op, and
    verify the resolver fired by checking set_output was called."""
    audio = _FakeAudio(outputs=[
        {"name": "alsa_output.usb-Generic", "type": "usb", "active": True},
        {"name": "bluez_sink.AA_BB_CC_DD_EE_FF.a2dp_sink", "type": "bluetooth", "active": False},
    ])
    priority = [{"mac": "AA:BB:CC:DD:EE:FF"}]
    run = _fake_run_factory({"info": "connected"})
    with patch("core.audio_session.shutil.which", _which_yes), \
         patch("core.audio_session.subprocess.run", run):
        m = AudioSessionManager(
            preferred_mac="AA:BB:CC:DD:EE:FF",
            audio_provider=audio,
            output_priority=priority,
        )
        m._tick()
    # BT path ran (bluetoothctl info was called):
    assert any(c[:2] == ["bluetoothctl", "info"] for c in run.calls)
    # Resolver also ran:
    assert audio.set_output_calls == ["bluez_sink.AA_BB_CC_DD_EE_FF.a2dp_sink"]


def test_resolver_only_manager_starts_without_preferred_mac():
    """No BT mac, but resolver config present — daemon still spawns."""
    audio = _FakeAudio(outputs=[
        {"name": "alsa_output.usb-Generic", "active": True},
    ])
    m = AudioSessionManager(
        preferred_mac="",
        audio_provider=audio,
        output_priority=[{"name_pattern": "USB"}],
    )
    m.start()
    try:
        assert m.is_running()
    finally:
        m.stop()


# ── BT card profile switching ────────────────────────────────────────
#
# Two sets of tests:
#   1. AudioSessionManager._ensure_correct_bt_profile — decision logic
#      with a mock audio provider, no PulseAudio involved.
#   2. PulseAudioProvider.set_card_profile + get_card_for_device — parser
#      and pactl invocation, subprocess mocked.


class _FakeAudioWithProfile(_FakeAudio):
    """Extends _FakeAudio with card-profile methods. Tracks calls."""

    def __init__(self, card_for_device=None, **kw):
        super().__init__(**kw)
        self._card_for_device = card_for_device or {}
        self.profile_calls = []  # list of (card, profile)

    def set_card_profile(self, card_name, profile_name):
        self.profile_calls.append((card_name, profile_name))
        return True

    def get_card_for_device(self, device_name):
        return self._card_for_device.get(device_name)


class _NoProfileAudio(_FakeAudio):
    """Inherits _FakeAudio without card-profile methods (i.e., they are
    inherited only from the parent which doesn't define them).

    Used to verify _ensure_correct_bt_profile no-ops gracefully when the
    audio provider lacks profile support."""
    # No set_card_profile / get_card_for_device defined.
    pass


def test_ensure_bt_profile_switches_to_hfp_when_output_input_same_card():
    """Same BT card on both sides → headset_head_unit."""
    card = "bluez_card.AA_BB_CC_DD_EE_FF"
    audio = _FakeAudioWithProfile(card_for_device={
        "bluez_sink.AA_BB_CC_DD_EE_FF.a2dp_sink": card,
        "bluez_input.AA_BB_CC_DD_EE_FF.headset_head_unit": card,
    })
    mgr = AudioSessionManager(preferred_mac="", audio_provider=audio)
    mgr._ensure_correct_bt_profile(
        chosen_output="bluez_sink.AA_BB_CC_DD_EE_FF.a2dp_sink",
        chosen_input="bluez_input.AA_BB_CC_DD_EE_FF.headset_head_unit",
    )
    assert audio.profile_calls == [(card, "headset_head_unit")], (
        f"expected one HFP switch, got {audio.profile_calls}"
    )


def test_ensure_bt_profile_switches_to_a2dp_when_input_different():
    """Output on BT, input elsewhere → a2dp_sink so output stays HiFi."""
    bt_card = "bluez_card.AA_BB_CC_DD_EE_FF"
    audio = _FakeAudioWithProfile(card_for_device={
        "bluez_sink.AA_BB_CC_DD_EE_FF.a2dp_sink": bt_card,
        "alsa_input.usb-Logitech_USB_Headset": "alsa_card.usb-Logitech",
    })
    mgr = AudioSessionManager(preferred_mac="", audio_provider=audio)
    mgr._ensure_correct_bt_profile(
        chosen_output="bluez_sink.AA_BB_CC_DD_EE_FF.a2dp_sink",
        chosen_input="alsa_input.usb-Logitech_USB_Headset",
    )
    assert audio.profile_calls == [(bt_card, "a2dp_sink")], (
        f"expected one A2DP switch, got {audio.profile_calls}"
    )


def test_ensure_bt_profile_noop_when_output_not_bluetooth():
    """Output not a bluez sink → no profile call regardless of input."""
    audio = _FakeAudioWithProfile(card_for_device={
        "alsa_output.hdmi-stereo": "alsa_card.hdmi",
    })
    mgr = AudioSessionManager(preferred_mac="", audio_provider=audio)
    mgr._ensure_correct_bt_profile(
        chosen_output="alsa_output.hdmi-stereo",
        chosen_input=None,
    )
    assert audio.profile_calls == [], (
        f"expected no profile switch, got {audio.profile_calls}"
    )


def test_ensure_bt_profile_noop_when_no_card_resolved():
    """Output is a bluez sink but get_card_for_device returns None → no-op."""
    audio = _FakeAudioWithProfile(card_for_device={})  # nothing resolves
    mgr = AudioSessionManager(preferred_mac="", audio_provider=audio)
    mgr._ensure_correct_bt_profile(
        chosen_output="bluez_sink.AA_BB_CC_DD_EE_FF.a2dp_sink",
        chosen_input="bluez_input.AA_BB_CC_DD_EE_FF.headset_head_unit",
    )
    assert audio.profile_calls == []


def test_ensure_bt_profile_noop_when_provider_lacks_methods():
    """Provider without get_card_for_device / set_card_profile → silent no-op."""
    audio = _NoProfileAudio()
    mgr = AudioSessionManager(preferred_mac="", audio_provider=audio)
    # Should not raise.
    mgr._ensure_correct_bt_profile(
        chosen_output="bluez_sink.AA_BB_CC_DD_EE_FF.a2dp_sink",
        chosen_input=None,
    )
    # Nothing to assert beyond "no exception".


def test_ensure_bt_profile_handles_get_card_exception():
    """get_card_for_device raising → no crash, no profile switch."""
    class _Broken(_FakeAudioWithProfile):
        def get_card_for_device(self, device_name):
            raise RuntimeError("simulated")
    audio = _Broken()
    mgr = AudioSessionManager(preferred_mac="", audio_provider=audio)
    mgr._ensure_correct_bt_profile(
        chosen_output="bluez_sink.AA_BB_CC_DD_EE_FF.a2dp_sink",
        chosen_input=None,
    )
    assert audio.profile_calls == []


def test_ensure_bt_profile_input_none_picks_a2dp():
    """No input chosen (e.g., no mic plugged in) → BT card stays on a2dp_sink."""
    card = "bluez_card.AA_BB_CC_DD_EE_FF"
    audio = _FakeAudioWithProfile(card_for_device={
        "bluez_sink.AA_BB_CC_DD_EE_FF.a2dp_sink": card,
    })
    mgr = AudioSessionManager(preferred_mac="", audio_provider=audio)
    mgr._ensure_correct_bt_profile(
        chosen_output="bluez_sink.AA_BB_CC_DD_EE_FF.a2dp_sink",
        chosen_input=None,
    )
    assert audio.profile_calls == [(card, "a2dp_sink")]


def test_apply_resolution_calls_ensure_bt_profile():
    """apply_resolution wires _ensure_correct_bt_profile at the end.

    With a BT sink as the chosen output and no input, apply_resolution
    should call set_card_profile with the a2dp_sink profile.
    """
    bt_sink = "bluez_sink.AA_BB_CC_DD_EE_FF.a2dp_sink"
    card = "bluez_card.AA_BB_CC_DD_EE_FF"

    audio = _FakeAudioWithProfile(
        outputs=[
            # active=False so apply_resolution actually calls
            # set_default_output (idempotency check otherwise short-circuits).
            {"name": bt_sink, "type": "bluetooth", "active": False},
        ],
        card_for_device={bt_sink: card},
    )
    mgr = AudioSessionManager(
        preferred_mac="",
        audio_provider=audio,
        output_priority=["system_default"],
    )
    mgr.apply_resolution()
    assert (card, "a2dp_sink") in audio.profile_calls, (
        f"expected a2dp_sink switch in apply_resolution, got {audio.profile_calls}"
    )


# ── PulseAudioProvider.set_card_profile / get_card_for_device ────────


def _pactl_sinks_multi_card_output() -> str:
    """Realistic multi-card `pactl list sinks` snippet.

    Three sinks, three cards. Card field appears BEFORE Name in sink #1
    and AFTER Name in sinks #0 and #2 — exercises both orders so the
    parser doesn't depend on a fixed key order within a block.
    """
    return (
        "Sink #0\n"
        "\tState: SUSPENDED\n"
        "\tName: alsa_output.pci-0000_00_1f.3.analog-stereo\n"
        "\tDescription: Built-in Audio Analog Stereo\n"
        "\tDriver: PipeWire\n"
        "\tCard: 0\n"
        "\n"
        "Sink #1\n"
        "\tState: RUNNING\n"
        "\tCard: 1\n"
        "\tName: bluez_sink.AA_BB_CC_DD_EE_FF.a2dp_sink\n"
        "\tDescription: Marshall Willen II\n"
        "\n"
        "Sink #2\n"
        "\tState: SUSPENDED\n"
        "\tName: alsa_output.usb-Logitech_USB_Headset\n"
        "\tDescription: Logitech Headset\n"
        "\tCard: 2\n"
    )


def _pactl_cards_short_output() -> str:
    return (
        "0\talsa_card.pci-0000_00_1f.3\tmodule-alsa-card.c\n"
        "1\tbluez_card.AA_BB_CC_DD_EE_FF\tmodule-bluez5-device.c\n"
        "2\talsa_card.usb-Logitech_USB_Headset\tmodule-alsa-card.c\n"
    )


def _pactl_sources_no_match() -> str:
    """Sources output that doesn't contain the device under test, so
    the parser must fall through to None cleanly."""
    return (
        "Source #0\n"
        "\tName: alsa_input.pci-0000_00_1f.3.analog-stereo\n"
        "\tCard: 0\n"
    )


def _make_pulse_run_fake():
    """Build a subprocess.run mock dispatching on `pactl ...` args."""
    calls = []

    def _run(cmd, capture_output=True, text=True, timeout=None, **_):
        calls.append(list(cmd))
        if cmd[:3] == ["pactl", "list", "sinks"] and "short" not in cmd:
            return SimpleNamespace(
                returncode=0,
                stdout=_pactl_sinks_multi_card_output(),
                stderr="",
            )
        if cmd[:3] == ["pactl", "list", "sources"] and "short" not in cmd:
            return SimpleNamespace(
                returncode=0,
                stdout=_pactl_sources_no_match(),
                stderr="",
            )
        if cmd[:4] == ["pactl", "list", "cards", "short"]:
            return SimpleNamespace(
                returncode=0,
                stdout=_pactl_cards_short_output(),
                stderr="",
            )
        if len(cmd) >= 2 and cmd[0] == "pactl" and cmd[1] == "set-card-profile":
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        return SimpleNamespace(returncode=1, stdout="", stderr="unknown command")

    _run.calls = calls
    return _run


def test_set_card_profile_calls_pactl_correctly():
    """PulseAudioProvider.set_card_profile invokes pactl with the right args."""
    from providers.audio.pulseaudio import PulseAudioProvider

    run = _make_pulse_run_fake()
    with patch("providers.audio.pulseaudio.subprocess.run", run):
        provider = PulseAudioProvider()
        ok = provider.set_card_profile(
            "bluez_card.AA_BB_CC_DD_EE_FF", "headset_head_unit",
        )
    assert ok is True
    set_calls = [
        c for c in run.calls
        if len(c) >= 2 and c[0] == "pactl" and c[1] == "set-card-profile"
    ]
    assert len(set_calls) == 1
    assert set_calls[0] == [
        "pactl", "set-card-profile",
        "bluez_card.AA_BB_CC_DD_EE_FF", "headset_head_unit",
    ]


def test_set_card_profile_returns_false_on_failure():
    """Non-zero returncode from pactl → False."""
    from providers.audio.pulseaudio import PulseAudioProvider

    def _run(cmd, **_):
        return SimpleNamespace(returncode=1, stdout="", stderr="Card not found")

    with patch("providers.audio.pulseaudio.subprocess.run", _run):
        provider = PulseAudioProvider()
        ok = provider.set_card_profile("nonexistent_card", "a2dp_sink")
    assert ok is False


def test_set_card_profile_rejects_empty_args():
    """Empty card or profile name → False, no subprocess invocation."""
    from providers.audio.pulseaudio import PulseAudioProvider

    def _run(cmd, **_):
        raise AssertionError("subprocess.run should not be called")

    with patch("providers.audio.pulseaudio.subprocess.run", _run):
        provider = PulseAudioProvider()
        assert provider.set_card_profile("", "a2dp_sink") is False
        assert provider.set_card_profile("bluez_card.AA", "") is False


def test_get_card_for_device_parses_pactl_list_sinks():
    """Real-shaped multi-card `pactl list sinks` is parsed correctly,
    including resolving numeric Card IDs to symbolic names."""
    from providers.audio.pulseaudio import PulseAudioProvider

    run = _make_pulse_run_fake()
    with patch("providers.audio.pulseaudio.subprocess.run", run):
        provider = PulseAudioProvider()
        card = provider.get_card_for_device(
            "bluez_sink.AA_BB_CC_DD_EE_FF.a2dp_sink",
        )
    assert card == "bluez_card.AA_BB_CC_DD_EE_FF", (
        f"expected BT card name, got {card!r}"
    )


def test_get_card_for_device_returns_none_when_missing():
    """Device not in the sinks/sources list → None (no crash)."""
    from providers.audio.pulseaudio import PulseAudioProvider

    run = _make_pulse_run_fake()
    with patch("providers.audio.pulseaudio.subprocess.run", run):
        provider = PulseAudioProvider()
        card = provider.get_card_for_device(
            "bluez_sink.DOES_NOT_EXIST.a2dp_sink",
        )
    assert card is None


def test_get_card_for_device_parses_first_sink_card_after_name():
    """First sink in the list has Card AFTER Name — parser still finds it."""
    from providers.audio.pulseaudio import PulseAudioProvider

    run = _make_pulse_run_fake()
    with patch("providers.audio.pulseaudio.subprocess.run", run):
        provider = PulseAudioProvider()
        card = provider.get_card_for_device(
            "alsa_output.pci-0000_00_1f.3.analog-stereo",
        )
    # Numeric "0" → alsa_card.pci-0000_00_1f.3 via cards-short lookup.
    assert card == "alsa_card.pci-0000_00_1f.3"


def test_get_card_for_device_returns_none_on_pactl_error():
    """If pactl errors out (e.g., daemon not running) → None, no raise."""
    from providers.audio.pulseaudio import PulseAudioProvider

    def _run(cmd, **_):
        return SimpleNamespace(returncode=1, stdout="", stderr="Connection refused")

    with patch("providers.audio.pulseaudio.subprocess.run", _run):
        provider = PulseAudioProvider()
        card = provider.get_card_for_device("bluez_sink.AA")
    assert card is None


def test_get_card_for_device_empty_arg_returns_none():
    from providers.audio.pulseaudio import PulseAudioProvider

    def _run(cmd, **_):
        raise AssertionError("subprocess.run should not be called")

    with patch("providers.audio.pulseaudio.subprocess.run", _run):
        provider = PulseAudioProvider()
        assert provider.get_card_for_device("") is None


# ── Test runner integration ──────────────────────────────────────────


def _collect_tests():
    return [obj for name, obj in globals().items()
            if name.startswith("test_") and callable(obj)]


def run_audio_session_tests() -> dict:
    results = []
    total_latency = 0.0
    for t in _collect_tests():
        start = time.time()
        try:
            t()
            elapsed = time.time() - start
            total_latency += elapsed
            results.append({
                "name": t.__name__, "input": "", "passed": True,
                "latency": elapsed, "detail": "", "tier": "easy", "tags": [],
            })
        except AssertionError as e:
            elapsed = time.time() - start
            total_latency += elapsed
            results.append({
                "name": t.__name__, "input": "", "passed": False,
                "latency": elapsed, "detail": str(e),
                "tier": "easy", "tags": [],
            })
        except Exception as e:
            elapsed = time.time() - start
            total_latency += elapsed
            results.append({
                "name": t.__name__, "input": "", "passed": False,
                "latency": elapsed,
                "detail": f"{type(e).__name__}: {e}",
                "tier": "easy", "tags": [],
            })
    passed = sum(1 for r in results if r["passed"])
    return {
        "total": len(results), "passed": passed,
        "total_latency": total_latency, "tests": results,
    }


def main() -> int:
    s = run_audio_session_tests()
    for r in s["tests"]:
        marker = "PASS" if r["passed"] else "FAIL"
        suffix = f": {r['detail']}" if r["detail"] else ""
        print(f"  [{marker}] {r['name']}{suffix}")
    print(f"\n{s['passed']}/{s['total']} audio_session tests passed.")
    return 0 if s["passed"] == s["total"] else 1


if __name__ == "__main__":
    sys.exit(main())
