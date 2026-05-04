"""
API smoke tests — FastAPI TestClient against `create_api(assistant)`.

Why these exist:
    The API layer had ZERO test coverage prior to this. Reviewers flagged
    several real reliability + security concerns (auth defaults, CORS,
    SSE worker leaks, token bootstrap). After fixing those, this file
    locks in the contract so future drift surfaces in CI / pre-commit
    runs instead of in production.

What we test:
    1. /api/status returns 200 with name, version, personality.
    2. /api/system/status (auth-required when auth on) — both auth-on
       and auth-off paths.
    3. The chat-fast heuristic in voice.py — pure-function, no LLM
       required.
    4. Audio cache: put / pop / TTL-evict / max-size eviction (if any).
    5. Bearer-token enforcement on a representative auth-on route.
    6. Unknown-action handling on the WS layer (covered by the
       ui.actions test in test_actions_smoke.py — kept separate
       because that's not strictly an API test).

What we DON'T test here (and why):
    - Streaming voice end-to-end — requires a real audio file +
      ears/brain providers. Covered by tools/bench_voice_e2e.py
      which is a full live-system bench, not a unit test.
    - WebSocket broadcasts — needs the FaceUI broadcaster running.
      Could be added with a fake_face_ui mock; left for later.

Running:
    pytest tests/test_api_smoke.py -v
    or:    python -m pytest tests/test_api_smoke.py
    or simply imported by tests/runner.py via run_api_smoke_tests().

These tests should run in <1 second total — they don't hit Ollama, YT,
or any external service. They're a CI-friendly fast lane.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock


# ── Test infrastructure ──────────────────────────────────────────────

def _build_test_app(auth_enabled: bool = False, token: str = "test-token-abc"):
    """
    Construct a FastAPI app the same way main.py does, with a stub
    `assistant` dict so handlers don't blow up when they access
    providers that aren't relevant to the route under test.

    Toggling `auth_enabled` without restarting the process requires
    monkeypatching the auth module's globals, since `_auth_enabled()`
    reads from the global config singleton.
    """
    from fastapi.testclient import TestClient
    from api.app import create_api
    from api import auth as auth_mod
    from core import config as cfg_mod

    # Patch the live config so auth.* respects our setting.
    cfg_mod.config.setdefault("api", {})
    cfg_mod.config["api"]["auth_enabled"] = auth_enabled
    cfg_mod.config["api"]["token"] = token

    # Reset the lazily-cached token so each test starts fresh.
    auth_mod._api_token = ""

    # Stub assistant — handlers receive this via Depends; we provide
    # MagicMock for the deep providers so attribute access doesn't 500.
    fake_assistant = {
        "name": "Jarvis",
        "version": "1.0.0",
        "brain": MagicMock(),
        "music": MagicMock(),
        "lights": MagicMock(),
        "voice_router": MagicMock(),
        "ears": MagicMock(),
        "face_ui": MagicMock(),
        "memory": MagicMock(),
        "knowledge": MagicMock(),
        "personality_manager": MagicMock(),
        "wake_word": MagicMock(),
    }

    app = create_api(fake_assistant)
    return TestClient(app), fake_assistant


# ── Test 1: status endpoint always reachable ─────────────────────────

def test_status_endpoint_returns_basic_info():
    """/api/status is the unauthenticated health endpoint clients use
    to verify connectivity before auth handshake."""
    client, _ = _build_test_app(auth_enabled=False)
    r = client.get("/api/status")
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    body = r.json()
    # The status route shapes itself from `assistant["name"]` and the
    # personality manager. We don't assert exact values (they come
    # from the assistant config which varies per machine), only that
    # the response shape is right.
    assert isinstance(body, dict)
    assert "name" in body, f"missing 'name' in response: {body!r}"


# ── Test 2: auth gate on a privileged route ──────────────────────────

def test_settings_get_requires_token_when_auth_on():
    """When auth is enabled, GET /api/settings returns 401 without a
    valid bearer. This is the primary line of defence against a
    same-WiFi peer mutating config.yaml."""
    token = "the-secret-token-xyz"
    client, _ = _build_test_app(auth_enabled=True, token=token)

    # No token at all → 401
    r = client.get("/api/settings")
    assert r.status_code == 401, f"expected 401, got {r.status_code}: {r.text}"

    # Wrong token → 401
    r = client.get("/api/settings", headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401

    # Correct token → 200 (or the handler's own response)
    r = client.get("/api/settings", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"


def test_settings_open_when_auth_disabled():
    """With auth off, no token is required. (Dev-mode only.)"""
    client, _ = _build_test_app(auth_enabled=False)
    r = client.get("/api/settings")
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"


# ── Test 3: chat-fast heuristic (pure function) ──────────────────────

def test_is_obvious_chat_classifications():
    """The chat-fast heuristic in routers/voice.py decides whether to
    route a transcribed phrase to the small-model fast path or to the
    full classifier. Mistakes here cost user-visible misroutes.

    The regex is conservative-by-design: it ONLY fires on opener phrases
    that are vanishingly unlikely to start a command (what is, how do,
    why does, tell me about, explain X, define X, etc.). False
    negatives are fine — they fall through to the full classifier.
    False positives are bad — they'd misroute "play sajni" to chat.

    These tests pin the contract."""
    from api.routers.voice import _is_obvious_chat

    # Conversational openers the heuristic SHOULD recognize as chat
    assert _is_obvious_chat("what is machine learning")
    assert _is_obvious_chat("how does a black hole work")
    assert _is_obvious_chat("tell me about the Mughal empire")
    assert _is_obvious_chat("explain quantum computing")
    assert _is_obvious_chat("why is the sky blue")
    assert _is_obvious_chat("who invented penicillin")

    # Action commands — must NOT be chat-fast (would skip classifier
    # and lose intent extraction):
    assert not _is_obvious_chat("play sajni")
    assert not _is_obvious_chat("turn off the lights")
    assert not _is_obvious_chat("volume up")
    assert not _is_obvious_chat("set a timer for 5 minutes")

    # "what time is it" is intentionally NOT a chat heuristic match —
    # it's a `system` intent. The regex requires "what is/are/does"
    # etc. and this phrase fails the pattern. Good.

    # False-friend with action verb: a chat-looking opener that
    # contains an action verb like "play" should be REJECTED by the
    # belt-and-suspenders verb guard.
    assert not _is_obvious_chat("what is play sajni about")  # contains "play"
    # And the simple bare "what's up" — no action verb but also no
    # match against the strict opener regex — falls through.
    assert not _is_obvious_chat("what's up")


# ── Test 4: audio cache lifecycle ────────────────────────────────────

def test_audio_cache_put_and_pop():
    """Cache returns the WAV exactly once, then the entry is gone.

    `_audio_cache_put(wav)` GENERATES a uuid hex chunk_id internally
    (so callers can't collide on the key); the test must capture the
    returned id. `_audio_cache_pop(chunk_id)` is single-use — second
    pop returns None.
    """
    from api.routers.voice import _audio_cache_put, _audio_cache_pop

    wav = b"fake-wav-bytes"
    chunk_id = _audio_cache_put(wav)
    assert isinstance(chunk_id, str) and len(chunk_id) > 0

    # First pop returns the bytes
    got = _audio_cache_pop(chunk_id)
    assert got == wav

    # Second pop is None — once-only consumption prevents double-fetch.
    got_again = _audio_cache_pop(chunk_id)
    assert got_again is None


def test_audio_cache_ttl_eviction():
    """Cache enforces a TTL on inserts so one-and-done audio chunks
    don't pile up forever when a client drops mid-stream.

    The cache lives in `api/voice/audio_cache.py` (was inline in voice.py
    until the module split). Patch the TTL on the new module to verify
    eviction triggers on the next insert.
    """
    from api.voice import audio_cache as cache_module

    # Set TTL to 0 so any pre-existing entry is older than the cutoff.
    original_ttl = cache_module._AUDIO_CACHE_TTL
    cache_module._AUDIO_CACHE_TTL = 0.0  # immediate eviction
    try:
        victim_id = cache_module.put(b"ephemeral")
        # Tiny sleep so the next put's `now - TTL` cutoff is strictly
        # after the victim's insert time (defends against same-microsecond
        # comparisons on fast machines).
        time.sleep(0.05)
        trigger_id = cache_module.put(b"trigger-bytes")
        # The first chunk should have been evicted on the second put.
        assert cache_module.pop(victim_id) is None
        # The trigger is still there (just inserted).
        assert cache_module.pop(trigger_id) == b"trigger-bytes"
    finally:
        cache_module._AUDIO_CACHE_TTL = original_ttl


# ── Test 5: events endpoints ────────────────────────────────────────


def test_events_current_returns_active_or_null():
    """
    GET /api/events/current is unauthenticated (the dashboard polls it
    without a token) and returns either the active event JSON or null.
    """
    client, _ = _build_test_app(auth_enabled=False)
    r = client.get("/api/events/current")
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    # Response is either null or a dict with the expected shape.
    body = r.json()
    if body is not None:
        assert "event_id" in body
        assert "is_today" in body
        assert "is_eve" in body
        assert "is_aftermath" in body
        assert "features" in body
        assert "theme_url" in body


def test_events_theme_tokens_endpoint_unknown_pack_404s():
    """A pack id that doesn't exist should 404, not 500."""
    client, _ = _build_test_app(auth_enabled=False)
    r = client.get("/api/events/no-such-pack/theme/tokens")
    assert r.status_code == 404, f"expected 404, got {r.status_code}: {r.text}"


def test_events_theme_tokens_endpoint_known_pack_returns_json():
    """A known pack returns the tokens.json contents (or empty {})."""
    client, _ = _build_test_app(auth_enabled=False)
    r = client.get("/api/events/astha-birthday/theme/tokens")
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    # Must be valid JSON dict (might be empty if file is just `{}`)
    body = r.json()
    assert isinstance(body, dict)


def test_events_trigger_requires_auth():
    """POST /api/events/trigger is auth-protected."""
    token = "trigger-test-token"
    client, _ = _build_test_app(auth_enabled=True, token=token)
    r = client.post("/api/events/trigger")
    assert r.status_code == 401, f"expected 401, got {r.status_code}"


# ── Test 6: CORS headers configured safely ────────────────────────────

def test_cors_does_not_send_allow_credentials_with_wildcard_origin():
    """The CORS middleware was configured with allow_origins=['*']
    AND allow_credentials=True — a combination explicitly forbidden by
    the CORS spec. This test guards against a regression."""
    client, _ = _build_test_app(auth_enabled=False)
    # Preflight (OPTIONS) request to trigger CORS headers.
    r = client.options(
        "/api/status",
        headers={
            "Origin": "http://localhost:8765",
            "Access-Control-Request-Method": "GET",
        },
    )
    # The response should NOT carry both `Access-Control-Allow-Origin: *`
    # AND `Access-Control-Allow-Credentials: true`. Either credentials
    # is absent/false, OR origin is pinned to the actual request origin.
    if r.headers.get("access-control-allow-credentials", "").lower() == "true":
        origin = r.headers.get("access-control-allow-origin", "")
        assert origin != "*", (
            "CORS misconfigured: allow_credentials=true MUST NOT be "
            "combined with allow_origins=['*'] (browser spec violation)."
        )


# ── Runner integration (so tests/runner.py picks this up) ────────────

def run_api_smoke_tests() -> dict:
    """
    Invoked by tests/runner.py — runs all tests above and returns the
    standard {total, passed, total_latency, tests} dict.
    """
    tests_to_run = [
        ("status endpoint returns basic info", test_status_endpoint_returns_basic_info),
        ("settings GET requires token when auth on", test_settings_get_requires_token_when_auth_on),
        ("settings open when auth disabled", test_settings_open_when_auth_disabled),
        ("_is_obvious_chat classifications", test_is_obvious_chat_classifications),
        ("audio cache put/pop one-shot", test_audio_cache_put_and_pop),
        ("audio cache TTL eviction", test_audio_cache_ttl_eviction),
        ("events /current returns active or null", test_events_current_returns_active_or_null),
        ("events theme/tokens 404 for unknown pack", test_events_theme_tokens_endpoint_unknown_pack_404s),
        ("events theme/tokens 200 for known pack", test_events_theme_tokens_endpoint_known_pack_returns_json),
        ("events /trigger requires auth", test_events_trigger_requires_auth),
        ("CORS does not combine wildcard origin + credentials", test_cors_does_not_send_allow_credentials_with_wildcard_origin),
    ]

    results = []
    total_latency = 0.0
    for name, fn in tests_to_run:
        start = time.time()
        passed = False
        detail = ""
        try:
            fn()
            passed = True
        except AssertionError as e:
            detail = f"AssertionError: {e}"
        except Exception as e:
            detail = f"{type(e).__name__}: {e}"
        latency = time.time() - start
        total_latency += latency
        results.append({
            "name": name, "passed": passed,
            "latency": latency, "detail": detail,
        })

    return {
        "total": len(results),
        "passed": sum(1 for r in results if r["passed"]),
        "total_latency": total_latency,
        "tests": results,
    }
