"""
Import sanity test — verifies the whole codebase wires up.

Runs in <1s and catches:
  - Circular imports introduced by a refactor
  - A module that's syntactically valid but fails at import time
  - Missing optional dependencies that are required by some path
  - A new feature that was added without being importable from the
    expected entry points

Each test imports a module and checks that the public symbol survives.
No network, no Ollama, no audio, no Jetson.
"""

from __future__ import annotations

import importlib
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# Birthday-pack modules added in 2026-05-05 shipping cycle. These
# should all import cleanly even with optional deps missing — the
# modules themselves use guarded imports for those.
BIRTHDAY_PACK_MODULES = [
    "core.audio_playback",
    "core.event_manager",
    "core.event_scheduler",
    "core.intro_runner",
    "core.astha_jokes",
    "core.birthday_quiz",
    "core.custom_playlist",
    "core.voice_memos",
    "core.trigger_state",
    "core.branding",
]

CORE_MODULES = [
    "core.config",
    "core.interfaces",
    "core.intent_handler",
    "core.logger",
    "core.personality",
    "core.pipeline",
    "core.prefilter",
    "core.voice_router",
]

API_MODULES = [
    "api.app",
    "api.auth",
    "api.deps",
    "api.discovery",
    "api.schemas",
    "api.routers.events",
    "api.routers.system",
    "api.routers.yaadein",
    "api.voice.audio_cache",
    "api.voice.chat_fast",
    "api.voice.filler",
]

PROVIDER_MODULES = [
    "providers.brain.ollama",
    "providers.memory.sqlite",
    "providers.yaadein.local",
]


def _import_all(modules: list[str]) -> None:
    """Import each module and surface the first failure with a clear msg."""
    for m in modules:
        try:
            importlib.import_module(m)
        except Exception as e:
            raise AssertionError(
                f"Module {m!r} failed to import: {type(e).__name__}: {e}"
            ) from e


def test_birthday_pack_modules_import():
    _import_all(BIRTHDAY_PACK_MODULES)


def test_core_modules_import():
    _import_all(CORE_MODULES)


def test_api_modules_import():
    _import_all(API_MODULES)


def test_provider_modules_import():
    _import_all(PROVIDER_MODULES)


def test_branding_resolves_with_default_config():
    """branding.brand should resolve without raising even with a
    minimal config — exercises the property fallbacks."""
    from core.branding import brand
    name = brand.name
    assert isinstance(name, str) and len(name) > 0
    proto = brand.protocol_id
    assert isinstance(proto, str) and len(proto) > 0
    mdns = brand.mdns_service_type
    assert mdns.startswith("_") and mdns.endswith(".local.")


def test_event_manager_singleton_loads():
    """get_event_manager() should construct without raising and find
    at least the astha-birthday pack we shipped."""
    from core.event_manager import get_event_manager
    em = get_event_manager()
    pack_ids = {p.pack_id for p in em.list_packs()}
    assert "astha-birthday" in pack_ids, (
        f"Expected astha-birthday pack to be loaded; got {sorted(pack_ids)}"
    )


def test_dispatch_table_loads():
    """The intent dispatch dict should be populated at module-load."""
    from core.intent_handler import _DISPATCH
    assert len(_DISPATCH) >= 20, (
        f"Expected at least 20 dispatch entries; got {len(_DISPATCH)}: "
        f"{sorted(_DISPATCH.keys())}"
    )


# ── Test runner integration ──────────────────────────────────────────


def _collect_tests():
    return [obj for name, obj in globals().items()
            if name.startswith("test_") and callable(obj)]


def run_imports_tests() -> dict:
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
    s = run_imports_tests()
    for r in s["tests"]:
        marker = "PASS" if r["passed"] else "FAIL"
        suffix = f": {r['detail']}" if r["detail"] else ""
        print(f"  [{marker}] {r['name']}{suffix}")
    print(f"\n{s['passed']}/{s['total']} imports tests passed.")
    return 0 if s["passed"] == s["total"] else 1


if __name__ == "__main__":
    sys.exit(main())
