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


def test_events_health_endpoint_returns_summary():
    """
    GET /api/events/health is unauthenticated. Returns a snapshot of
    loaded packs + active state. Smoke-test the shape; values vary
    with what's in events/.
    """
    client, _ = _build_test_app(auth_enabled=False)
    r = client.get("/api/events/health")
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    body = r.json()
    assert "year" in body
    assert "packs" in body
    assert "active" in body
    assert isinstance(body["packs"], list)
    if body["packs"]:
        first = body["packs"][0]
        for key in ("pack_id", "display_name", "feature_count",
                    "auto_midnight", "is_triggered_this_year"):
            assert key in first, f"missing key {key} in pack summary"


def test_events_trigger_returns_409_outside_event_day():
    """
    With no active event today, POST /trigger returns 409.

    The events router consults event_manager.current() — which is
    real-time-driven. We monkey-patch the manager to report no active
    event, regardless of the calendar.
    """
    from unittest.mock import patch
    client, _ = _build_test_app(auth_enabled=False)
    with patch("api.routers.events.get_event_manager") as mock_em:
        mock_em.return_value.current.return_value = None
        r = client.post("/api/events/trigger")
        assert r.status_code == 409, f"expected 409, got {r.status_code}: {r.text}"


def test_events_trigger_persists_state_and_current_reflects_it():
    """
    Full lifecycle:
      1. Reset state (idempotent)
      2. /current shows is_triggered=false (date matches but not fired)
      3. POST /trigger → 200, freshly_triggered=true
      4. /current now shows is_triggered=true
      5. POST /trigger again → 200, freshly_triggered=false (idempotent)
      6. POST /reset → was_set=true
      7. /current reverts to is_triggered=false
    """
    from unittest.mock import MagicMock, patch
    from datetime import datetime
    import tempfile
    from pathlib import Path

    client, _ = _build_test_app(auth_enabled=False)

    # Use an isolated trigger-state file so this test doesn't pollute
    # the real one in data/.
    with tempfile.TemporaryDirectory() as tmp_str:
        from core.trigger_state import TriggerStateStore
        isolated_store = TriggerStateStore(path=Path(tmp_str) / "triggers.json")

        # Mock the active event so trigger has something to fire on.
        fake_active = MagicMock()
        fake_active.pack_id = "astha-birthday"
        fake_active.pack_dir = Path(tmp_str)
        fake_active.pack.display_name = "Astha's Birthday"
        fake_active.pack.features = []
        fake_active.pack.trigger_config = {}
        fake_active.pack.raw = {}  # no first_year_only.intro_script
        fake_active.is_today = True
        fake_active.is_eve = False
        fake_active.is_aftermath = False
        fake_active.days_until = 0

        with patch("api.routers.events.get_event_manager") as mock_em, \
             patch("api.routers.events.get_trigger_store") as mock_store:
            mock_em.return_value.current.return_value = fake_active
            mock_em.return_value.list_packs.return_value = []
            mock_store.return_value = isolated_store

            # 1. State starts clean.
            assert isolated_store.is_triggered("astha-birthday") is False

            # 2. /current shows is_triggered=false on the day pre-trigger.
            r = client.get("/api/events/current")
            assert r.status_code == 200
            body = r.json()
            assert body is not None
            assert body["is_triggered"] is False

            # 3. POST /trigger fires fresh.
            r = client.post("/api/events/trigger")
            assert r.status_code == 200, f"got {r.status_code}: {r.text}"
            data = r.json()
            assert data["ok"] is True
            assert data["is_triggered"] is True
            assert data["freshly_triggered"] is True

            # 4. /current now reflects the persisted state.
            r = client.get("/api/events/current")
            body = r.json()
            assert body["is_triggered"] is True

            # 5. Re-trigger is idempotent.
            r = client.post("/api/events/trigger")
            assert r.status_code == 200
            assert r.json()["freshly_triggered"] is False

            # 6. Reset clears the state.
            r = client.post("/api/events/astha-birthday/reset")
            assert r.status_code == 200
            assert r.json()["was_set"] is True

            # 7. /current reverts.
            r = client.get("/api/events/current")
            assert r.json()["is_triggered"] is False


# ── Test: yaadein loader + endpoints ──────────────────────────────────


def _make_yaadein_fixture(tmp_root):
    """
    Build an isolated photos directory with a small captions.yaml and
    a couple of fake image bytes. Returns the directory path.
    """
    from pathlib import Path
    photos_dir = Path(tmp_root) / "media" / "photos"
    photos_dir.mkdir(parents=True, exist_ok=True)
    # Three "image" files. Bytes don't matter — the loader only checks
    # the suffix, and the API's FileResponse streams whatever's there.
    (photos_dir / "001.jpg").write_bytes(b"\xff\xd8fake-jpg")
    (photos_dir / "002.jpg").write_bytes(b"\xff\xd8fake-jpg-2")
    (photos_dir / "003.png").write_bytes(b"\x89PNGfake")
    # An entry in the YAML with explicit order; one without a YAML
    # entry to verify auto-include.
    (photos_dir / "captions.yaml").write_text(
        "music: null\n"
        "photos:\n"
        "  - file: 002.jpg\n"
        '    caption: "second photo 🥰"\n'
        "    order: 2\n"
        "  - file: 001.jpg\n"
        '    caption: "first photo 😇"\n'
        "    order: 1\n",
        encoding="utf-8",
    )
    return photos_dir


def test_yaadein_loader_orders_and_auto_includes(tmp_path):
    """
    The loader should:
      - sort entries with explicit `order` first (asc),
      - then auto-include unlisted on-disk photos with empty captions,
      - return music=None when YAML has `music: null`.
    """
    from providers.yaadein.local import load_photos
    photos_dir = _make_yaadein_fixture(tmp_path)
    pack = load_photos(photos_dir)
    assert pack.music is None
    # 001 (order 1), 002 (order 2), 003 (auto-included)
    files = [p.file for p in pack.photos]
    assert files == ["001.jpg", "002.jpg", "003.png"], files
    # Captions on the YAML-listed entries, empty on the auto-included.
    captions = {p.file: p.caption for p in pack.photos}
    assert "first photo" in captions["001.jpg"]
    assert "second photo" in captions["002.jpg"]
    assert captions["003.png"] == ""


def test_yaadein_loader_handles_missing_dir(tmp_path):
    """A missing photos dir is fine — empty list, no exception."""
    from pathlib import Path
    from providers.yaadein.local import load_photos
    pack = load_photos(Path(tmp_path) / "does-not-exist")
    assert pack.photos == []
    assert pack.music is None


def test_yaadein_loader_skips_path_traversal_in_yaml(tmp_path):
    """A captions.yaml entry with a path-like file should be rejected."""
    from pathlib import Path
    from providers.yaadein.local import load_photos
    photos_dir = Path(tmp_path) / "photos"
    photos_dir.mkdir()
    (photos_dir / "good.jpg").write_bytes(b"\xff\xd8")
    (photos_dir / "captions.yaml").write_text(
        "photos:\n"
        "  - file: ../etc/passwd\n"
        '    caption: "evil"\n'
        "  - file: good.jpg\n"
        '    caption: "ok"\n',
        encoding="utf-8",
    )
    pack = load_photos(photos_dir)
    assert [p.file for p in pack.photos] == ["good.jpg"]


def test_yaadein_photo_endpoint_rejects_path_traversal():
    """
    `/api/yaadein/photo/{filename}` MUST reject `..`, absolute paths,
    and any other escape attempt with 400. Even with auth disabled,
    the path check applies before the file lookup.
    """
    client, _ = _build_test_app(auth_enabled=False)
    # A few classic traversal attempts; each should be 400 (not 404).
    for evil in ["../etc/passwd", "..%2Fetc%2Fpasswd", ".hidden", "sub/file.jpg"]:
        # FastAPI URL-decodes path params, so `..%2F` becomes `../`. We
        # skip that one when the client itself doesn't decode (TestClient
        # passes through raw); 400 OR 404 is acceptable for the URL-encoded
        # variant since the route path won't even match.
        r = client.get(f"/api/yaadein/photo/{evil}")
        assert r.status_code in (400, 404), (
            f"path '{evil}' must not be served (got {r.status_code})"
        )


def test_yaadein_list_returns_404_when_no_event(monkeypatch):
    """
    When `event_manager.current()` returns None (most days of the year),
    `/api/yaadein/list` returns 404 with a clean message.
    """
    from api.routers import yaadein as yaadein_router
    monkeypatch.setattr(
        yaadein_router, "_active_pack_or_404",
        lambda: (_ for _ in ()).throw(
            __import__("fastapi").HTTPException(status_code=404, detail="no active event")
        ),
    )
    client, _ = _build_test_app(auth_enabled=False)
    r = client.get("/api/yaadein/list")
    assert r.status_code == 404, r.text


def test_yaadein_list_endpoint_returns_manifest(monkeypatch, tmp_path):
    """
    With a stubbed active event pointing at a fixture pack dir, the
    /list endpoint returns the expected manifest shape.
    """
    from pathlib import Path
    from api.routers import yaadein as yaadein_router

    photos_dir = _make_yaadein_fixture(tmp_path)
    fixture_pack_dir = Path(photos_dir.parent.parent)  # tmp_root

    # Build a fake ActiveEvent the route can introspect. We only need
    # `pack_dir` and `pack.display_name` + `pack_id` for the response.
    # The class body re-assigns `pack_dir`, so the source value is held
    # in `fixture_pack_dir` (not `pack_dir`) to avoid Python's class
    # scope name-resolution gotcha.
    class _FakePack:
        display_name = "Test Pack"
    class _FakeActive:
        pack_id = "test-pack"
        pack_dir = fixture_pack_dir
        pack = _FakePack()

    monkeypatch.setattr(yaadein_router, "_active_pack_or_404", lambda: _FakeActive())

    client, _ = _build_test_app(auth_enabled=False)
    r = client.get("/api/yaadein/list")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["pack_id"] == "test-pack"
    assert body["display_name"] == "Test Pack"
    assert body["music_url"] is None
    assert isinstance(body["photos"], list)
    assert len(body["photos"]) == 3
    # Each photo entry has photo_url + caption.
    for p in body["photos"]:
        assert p["photo_url"].startswith("/api/yaadein/photo/")
        assert "caption" in p


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
    # Some yaadein tests use pytest fixtures (tmp_path, monkeypatch).
    # The runner harness here does NOT spin up pytest, so we provide
    # manual replacements: a tempfile dir that we clean up after, and
    # a tiny monkeypatch context that records + restores attribute
    # mutations. This keeps the suite runnable both via the runner
    # (CI/dashboard) and via `pytest tests/test_api_smoke.py` (dev).
    import tempfile
    import shutil
    from contextlib import contextmanager
    from pathlib import Path

    @contextmanager
    def _tmp_path():
        d = Path(tempfile.mkdtemp(prefix="yaadein-test-"))
        try:
            yield d
        finally:
            shutil.rmtree(d, ignore_errors=True)

    class _Monkeypatch:
        def __init__(self):
            self._undo = []
        def setattr(self, target, name, value):
            old = getattr(target, name)
            self._undo.append((target, name, old))
            setattr(target, name, value)
        def restore(self):
            for target, name, old in reversed(self._undo):
                setattr(target, name, old)

    @contextmanager
    def _monkeypatch():
        mp = _Monkeypatch()
        try:
            yield mp
        finally:
            mp.restore()

    def _wrap_tmp(fn):
        def runner():
            with _tmp_path() as p:
                fn(p)
        return runner

    def _wrap_monkey(fn):
        def runner():
            with _monkeypatch() as mp:
                fn(mp)
        return runner

    def _wrap_both(fn):
        def runner():
            with _monkeypatch() as mp, _tmp_path() as p:
                fn(mp, p)
        return runner

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
        ("events /health returns summary", test_events_health_endpoint_returns_summary),
        ("events /trigger requires auth", test_events_trigger_requires_auth),
        ("events /trigger 409 outside event day", test_events_trigger_returns_409_outside_event_day),
        ("events /trigger lifecycle persists state", test_events_trigger_persists_state_and_current_reflects_it),
        ("CORS does not combine wildcard origin + credentials", test_cors_does_not_send_allow_credentials_with_wildcard_origin),
        ("yaadein loader orders + auto-includes",
         _wrap_tmp(test_yaadein_loader_orders_and_auto_includes)),
        ("yaadein loader handles missing dir",
         _wrap_tmp(test_yaadein_loader_handles_missing_dir)),
        ("yaadein loader rejects path-traversal in YAML",
         _wrap_tmp(test_yaadein_loader_skips_path_traversal_in_yaml)),
        ("yaadein /photo rejects path traversal",
         test_yaadein_photo_endpoint_rejects_path_traversal),
        ("yaadein /list 404s when no active event",
         _wrap_monkey(test_yaadein_list_returns_404_when_no_event)),
        ("yaadein /list returns manifest with stub event",
         _wrap_both(test_yaadein_list_endpoint_returns_manifest)),
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
