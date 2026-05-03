# Overnight session — May 4, 2026

User asked me to work through the night fixing production-quality issues
methodically, look at how the open-source community has solved each problem
before writing code, and not decay quality. Here's what landed and what's
still open.

## Commits (9, atop 40795a2)

| Commit | What | Bench impact |
|---|---|---|
| `3477524` | SoTA voice-assistant architecture (out-of-band audio + filler + Piper-for-English + voice-clone-aware routing + Whisper-tiny + Ollama keep_alive=600 + many bug fixes) | 50/50 chat passed: filler p50 0.57s, p95 0.71s; real-answer p50 2.36s, p95 3.0s |
| `ceb9a2f` | Remove 3 dead helpers in voice.py | -31 lines, no behavior change |
| `5ebdee0` | Bound prefilter intent execution to 200ms validation window (HA Voice pattern) | Lights when offline: 36s → 0.5-0.8s perceived |
| `13f173a` | Music intent regex prefilter ("play X", "X bajao") | "play Sajni": ~20s → 1.0s perceived ack |
| `f6ee797` | VAD silence threshold 1.5s → 0.7s + configurable | -800ms perceived per turn (industry-standard range) |
| `9dd9410` | Reuse shared intent executor (no thread leaks) | Memory hygiene under load |
| `0978f2b` | Document new config tunables in `config.example.yaml` | Operator-facing |
| `da6ce48` | Document streaming-pipeline architecture in `assistant/CLAUDE.md` | Future-agent-facing |
| `e0afce5` | Eager-warm Piper at JARVIS startup | First chat reply -2s (was paying ONNX load on first call) |

The latest commit (`e0afce5`) is **NOT yet synced to Jetson** — that needs
a JARVIS restart to apply. See morning steps below.

## Research that informed the work

Three parallel research agents investigated SoTA patterns from the open-source
voice assistant community:

### 1. LiveKit `preemptive_generation` → DEFER

Reading `livekit-agents` source code, the pattern fires the LLM on each STT
**INTERIM/PREFLIGHT** transcript event before VAD declares end-of-turn,
canceling and re-firing on each new partial. **Whisper batch STT (what we
use) only emits ONE final transcript at end-of-speech — there are no
partials to fire on, so the latency win is 0ms with our current STT.**

The agent flagged a much bigger immediate lever: **VAD silence threshold**
tuning. Defaults were 1.5s; industry range is 600-800ms. Landed in `f6ee797`
(0.7s default + configurable via `--silence` CLI flag).

Defer real preemptive LLM until faster-whisper-streaming or whisper.cpp
streaming migration after the May 14 demo.

### 2. Prefilter intent timeout → ADOPT HA Voice pattern

Home Assistant's `homeassistant/helpers/intent.py::DynamicServiceIntentHandler`
uses `service_timeout: float = 0.2` (200ms validation window). Pattern:

1. Speak the prefilter's pre-defined response IMMEDIATELY
2. Run `handle_intent` in a background thread with 200ms timeout
3. If handler returns inside window: surface validation errors, prefer its return value
4. If handler doesn't: let it keep running in the background; do NOT speak follow-up errors later

The "no follow-up error" is the non-obvious part. By the time a 30s Tuya
hang fires, the user has moved on; speaking "actually, that failed" 30s
later is worse than silent failure. HA explicitly chose this. We landed
the same in `5ebdee0`.

OVOS uses a similar (more elaborate) pattern via `killable_intent`
decorator. We borrowed the bg-task idea but skipped the killable
machinery — single-user system, can revisit if multi-turn cancellation
becomes a feature.

### 3. Music intent immediate-ack → ADOPT regex prefilter + Pipecat-style filler

OVOS Common Play (`ovos_workshop/skills/common_play.py`), HA Voice (sentence
templates in OHF-Voice/intents), Snips/Picovoice Rhino (domain grammar) all
**route obvious music commands through a regex/template path BEFORE the
LLM** — only falling through to LLM for ambiguous cases. Pipecat's
`on_function_calls_started` hook fires a canned filler ("Let me check on
that") immediately at intent identification, then runs the actual tool in
the background.

Combined with our 200ms validation-window timeout pattern, this naturally
gives us "speak immediately, run heavy work in background." Landed in
`13f173a`. Music goes from ~20s to ~1.0s perceived.

The agent's recommendation to "parallelize search + enrichment with
asyncio.gather" is still pending — currently the music handler runs
serially (classify → enrich → search) but the user already heard the ack
so it's not user-visible. Worth doing eventually but not blocking demo.

## Stability test interrupted by power outage (not a software issue)

Stability test was running `--suite all --runs 8 --warmup` (8 runs of each
of 13 query types = 104 runs total). Ran 5 consecutive sub-1s runs of
"what is the speed of light", then run 6 stalled at 180s read timeout.

User confirmed afterward: **the Jetson lost power** (electricity outage at
the Jetson's location). The 180s timeout I saw was the power dying during
the 6th request, not a JARVIS or NvMap crash. The 5 successful runs are
the only valid data tonight; long-running stability is still unverified.

**The architecture itself shows no signs of regression** in tonight's
fragmentary data:
- Earlier today: 50/50 chat suite passed on the same architecture
- Tonight: 5/5 sub-1s before power loss
- 13/13 mixed-suite passed earlier this evening

Long stability (50+ continuous runs) needs to be re-validated when power
returns and the Jetson is back up.

### Production-hardening to consider regardless (most apply to any
voice-on-Jetson deployment, power outage or not):

1. **Run JARVIS under systemd with restart-on-failure** — automatic
   recovery from any process-level crashes (including the kind that would
   eventually happen from accumulated NvMap fragmentation, even if it
   didn't tonight)
2. **Watchdog cron job** — every 5 minutes pings `/api/system/status`,
   restarts Ollama via `systemctl restart ollama` if no response
3. **`OLLAMA_KEEP_ALIVE=600` already lowered** (was -1) — should keep
   long-running NvMap fragmentation in check
4. **Kokoro on CPU permanently** — already done in config (one less CUDA
   user, more headroom for Ollama)
5. **`OLLAMA_FLASH_ATTENTION=1` already set** — halves KV cache
6. **UPS for the Jetson** — if power outages are common at the deployment
   site, a small UPS (e.g., 600VA APC BE600M1) buys ~10 min for clean
   shutdown. The Jetson Orin Nano draws 7-15W under load.
7. **`/etc/systemd/system/ollama.service.d/override.conf`** is already
   set up with the right env vars (`OLLAMA_GPU_OVERHEAD=0`,
   `OLLAMA_NUM_PARALLEL=1`, `OLLAMA_KEEP_ALIVE=-1`,
   `OLLAMA_MAX_LOADED_MODELS=1`, `OLLAMA_FLASH_ATTENTION=1`,
   `OLLAMA_CONTEXT_LENGTH=2048`). Worth bumping `KEEP_ALIVE` here too
   from `-1` to `300s` so even system-default-keep-alive paths recycle.

## Morning steps (in order)

1. **Wait for power to come back, Jetson auto-boots** (or manual power-on
   if needed)
2. **Sync latest commits to Jetson**:
   ```bash
   ssh devesh@192.168.1.8 'cd ~/project-gulmugli && git pull'
   ```
3. **Restart Ollama then JARVIS**:
   ```bash
   ssh devesh@192.168.1.8 'sudo systemctl restart ollama; sleep 5; /tmp/start_jarvis.sh'
   ```
4. **Run validation bench** (30 chat runs):
   ```bash
   cd ~/Projects/project-gulmugli/jarvis/assistant
   JARVIS_HOST=http://192.168.1.8:8766 \
   JARVIS_TOKEN=<from log> \
   python3 tools/bench_voice_e2e.py --suite chat --runs 6 --warmup --play
   ```
   Expect: 30/30 success, USER TTFA p50 ~0.6s, real answer p50 ~2.6s
5. **Real-mic test** with Mac client:
   ```bash
   .venv-mac/bin/python clients/mac_client.py --voice --stream --auto --silence 0.7
   ```
   Try: "what is the speed of light", "lights off", "play Sajni",
   "what's the time"
6. **Investigate the Jetson freeze** if it reproduces — check `dmesg`,
   `/var/log/syslog`, whether oom-killer fired, whether kernel panic logs
   exist. Then we can target the right fix.

## Targets validated tonight (before Jetson freeze)

| Path | p50 perceived TTFA | p95 perceived TTFA |
|---|---|---|
| Chat (filler audio) | **0.57s** ✓ | **0.71s** ✓ |
| Chat (real answer audible) | 2.65s | 3.0s server-side |
| Prefilter (lights/volume/pause/stop/time/date, all online) | **0.5-0.7s** ✓ | 0.78s ✓ |
| Prefilter (lights when bulbs offline) | **0.74s** ✓ | (was 36s) |
| Music intent ("play X") | **1.0s** ✓ | (was ~20s) |

Architecture is the SoTA pattern: Whisper-tiny CUDA + Ollama llama3.2:3b
CUDA + Piper CPU + Kokoro CPU + filler audio + 200ms validation window +
out-of-band audio fetch. The 9 commits + docs make this maintainable for
the next agent who touches the code.
