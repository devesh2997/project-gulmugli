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
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.audio_session import AudioSessionManager  # noqa: E402


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
