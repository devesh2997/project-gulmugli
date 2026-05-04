#!/usr/bin/env python3
"""
healthcheck.py — assistant liveness and degradation probe.

Pings the assistant and Ollama, classifies state, exits with a Nagios-style code:

    0  OK         — both healthy, recent voice request worked
    1  WARNING    — degraded (Ollama slow, model hot-reload, etc.)
    2  CRITICAL   — assistant or Ollama unreachable, runner crashed, etc.
    3  UNKNOWN    — can't even reach the host (network down, Jetson off)

Designed to be cron-friendly. Quiet on success, verbose on failure (so
syslog / mail forwarder doesn't spam, and a human reading mail diagnoses
fast). Suggested cron entries:

  # Every 5 min, log a one-liner status; alert if CRITICAL or UNKNOWN
  */5 * * * * /usr/bin/python3 /path/to/healthcheck.py --quiet || \\
              /usr/bin/wall "Assistant health: $(/usr/bin/python3 /path/to/healthcheck.py)"

  # Once an hour, full report to a logfile (for trend analysis)
  0 * * * *   /usr/bin/python3 /path/to/healthcheck.py --verbose >> /var/log/assistant_health.log

If you have systemd, prefer a Timer + Service unit instead of cron.

Usage:
    healthcheck.py                # one-shot, prints summary
    healthcheck.py --quiet        # quiet on OK, verbose on failure
    healthcheck.py --verbose      # always print full diagnostic
    healthcheck.py --watch        # loop with 30s interval (foreground)
    healthcheck.py --json         # machine-readable output

Env:
    ASSISTANT_HOST   default http://192.168.1.8:8766
                     (legacy JARVIS_HOST also accepted)
    ASSISTANT_TOKEN  required for full /api/voice probe; status endpoint is open
                     (legacy JARVIS_TOKEN also accepted)
    OLLAMA_HOST      default http://localhost:11434 (must run on the same box)

Note: this tool is intentionally brand-agnostic — uses generic "assistant"
terminology so it survives any future rebrand without code changes.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any

# Exit codes (Nagios convention — widely understood by monitoring tools)
EXIT_OK = 0
EXIT_WARNING = 1
EXIT_CRITICAL = 2
EXIT_UNKNOWN = 3


def _ms(start: float) -> int:
    return int((time.time() - start) * 1000)


def _http_get(url: str, token: str | None = None, timeout: float = 5.0):
    import urllib.request, urllib.error
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read()


def check_assistant_status(host: str, token: str | None) -> dict[str, Any]:
    """Probe /api/system/status. Captures uptime + which providers loaded."""
    out: dict[str, Any] = {"name": "assistant_status", "ok": False}
    t0 = time.time()
    try:
        status, body = _http_get(f"{host}/api/system/status", token, timeout=5.0)
        out["latency_ms"] = _ms(t0)
        if status != 200:
            out["error"] = f"HTTP {status}"
            return out
        data = json.loads(body.decode())
        out.update({
            "ok": True,
            # `brand_name` lets the summary line greet the user with the
            # current brand ("Vesper", "Jarvis", etc.) without baking it
            # into this script. Falls back to "assistant" if absent.
            "brand_name": data.get("name"),
            "version": data.get("version"),
            "personality": data.get("personality"),
            "uptime_seconds": data.get("uptime_seconds"),
            "providers": data.get("providers", {}),
        })
    except Exception as e:
        out["latency_ms"] = _ms(t0)
        out["error"] = f"{type(e).__name__}: {e}"
    return out


def check_ollama(ollama_host: str = "http://localhost:11434",
                 model: str = "llama3.2:3b") -> dict[str, Any]:
    """
    Probe Ollama via /api/tags (lists loaded models — cheap) and a tiny
    `/api/generate num_predict=1` to detect runner crashes early.
    Returns dict with diagnostics. The runner crash check is the one
    that catches the failure mode we hit overnight (NvMap fragmentation
    → runner terminated silently).
    """
    out: dict[str, Any] = {"name": "ollama", "ok": False}
    # Step 1: tags endpoint
    t0 = time.time()
    try:
        status, body = _http_get(f"{ollama_host}/api/tags", timeout=3.0)
        out["tags_latency_ms"] = _ms(t0)
        if status != 200:
            out["error"] = f"tags HTTP {status}"
            return out
        models = json.loads(body.decode()).get("models", [])
        out["models_loaded"] = [m.get("name") for m in models]
    except Exception as e:
        out["tags_latency_ms"] = _ms(t0)
        out["error"] = f"tags unreachable: {type(e).__name__}: {e}"
        return out

    # Step 2: tiny generate to catch silent runner crashes
    t0 = time.time()
    try:
        import urllib.request
        req = urllib.request.Request(
            f"{ollama_host}/api/generate",
            data=json.dumps({
                "model": model, "prompt": "hi", "stream": False,
                "options": {"num_predict": 1},
            }).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=20.0) as r:
            data = json.loads(r.read().decode())
        out["gen_latency_ms"] = _ms(t0)
        if "error" in data:
            out["error"] = f"gen error: {data['error']}"
            return out
        if not data.get("response") and not data.get("done"):
            out["error"] = "gen returned empty response (silent crash?)"
            return out
        out["ok"] = True
    except Exception as e:
        out["gen_latency_ms"] = _ms(t0)
        out["error"] = f"gen unreachable: {type(e).__name__}: {e}"
    return out


def classify(assistant: dict, ollama: dict) -> tuple[int, str]:
    """
    Combine probes into a single Nagios state + summary line.

    Logic:
      - Assistant unreachable → UNKNOWN (host down, network split, etc.)
      - Ollama unreachable → CRITICAL (assistant will fail every chat request)
      - Ollama runner crashed (empty response or "terminated") → CRITICAL
      - Ollama gen latency > 10s → WARNING (degraded but limping along)
      - Otherwise → OK
    """
    if not assistant.get("ok"):
        err = assistant.get("error", "")
        # Distinguish "host unreachable" (unknown) vs "assistant responded
        # with an error" (critical).
        if "ConnectionRefused" in err or "Host is down" in err or "URLError" in err:
            return EXIT_UNKNOWN, f"assistant unreachable: {err}"
        return EXIT_CRITICAL, f"assistant error: {err}"

    if not ollama.get("ok"):
        err = ollama.get("error", "")
        if "silent crash" in err or "runner" in err.lower():
            return EXIT_CRITICAL, (
                f"Ollama runner crash: {err}. Recover with: "
                f"sudo systemctl restart ollama"
            )
        return EXIT_CRITICAL, f"Ollama error: {err}"

    gen_ms = ollama.get("gen_latency_ms", 0)
    if gen_ms > 10_000:
        return EXIT_WARNING, f"Ollama slow: gen {gen_ms}ms"

    # Show the assistant's brand name in the summary if the API reported
    # it, otherwise fall back to "assistant".
    label = assistant.get("brand_name") or "assistant"
    summary = (
        f"OK | {label} uptime={assistant.get('uptime_seconds', '?')}s "
        f"personality={assistant.get('personality', '?')} "
        f"ollama gen={gen_ms}ms models={len(ollama.get('models_loaded', []))}"
    )
    return EXIT_OK, summary


def run_once(host: str, token: str | None, ollama_host: str,
             ollama_model: str) -> tuple[int, dict, dict, str]:
    a = check_assistant_status(host, token)
    o = check_ollama(ollama_host, ollama_model)
    code, summary = classify(a, o)
    return code, a, o, summary


def fmt_human(code: int, assistant: dict, ollama: dict, summary: str,
              verbose: bool) -> str:
    label = {EXIT_OK: "OK", EXIT_WARNING: "WARNING",
             EXIT_CRITICAL: "CRITICAL", EXIT_UNKNOWN: "UNKNOWN"}[code]
    lines = [f"[{label}] {summary}"]
    if verbose:
        lines.append(f"  assistant: {json.dumps(assistant, default=str)}")
        lines.append(f"  ollama: {json.dumps(ollama, default=str)}")
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(
        description="Assistant + Ollama liveness probe (Nagios-style exit codes)"
    )
    # ASSISTANT_HOST is the canonical env var; JARVIS_HOST kept as fallback
    # so cron entries that already use the old name keep working.
    default_host = (
        os.environ.get("ASSISTANT_HOST")
        or os.environ.get("JARVIS_HOST")
        or "http://192.168.1.8:8766"
    )
    default_token = (
        os.environ.get("ASSISTANT_TOKEN") or os.environ.get("JARVIS_TOKEN")
    )
    p.add_argument("--host", default=default_host)
    p.add_argument("--token", default=default_token)
    p.add_argument("--ollama-host", default=os.environ.get(
        "OLLAMA_HOST", "http://localhost:11434"))
    p.add_argument("--ollama-model", default="llama3.2:3b",
                   help="Model to probe Ollama with (default llama3.2:3b)")
    p.add_argument("--quiet", action="store_true",
                   help="Print nothing on OK; print failure summary otherwise")
    p.add_argument("--verbose", action="store_true",
                   help="Always print full diagnostic JSON")
    p.add_argument("--json", action="store_true",
                   help="Machine-readable JSON output")
    p.add_argument("--watch", type=float, metavar="SECONDS",
                   help="Loop with this interval in foreground (Ctrl+C to exit)")
    args = p.parse_args()

    def one_pass():
        code, assistant, ollama, summary = run_once(
            args.host, args.token, args.ollama_host, args.ollama_model,
        )
        if args.json:
            print(json.dumps({
                "code": code, "summary": summary,
                "assistant": assistant, "ollama": ollama,
                "ts": time.time(),
            }))
        elif args.quiet:
            if code != EXIT_OK:
                print(fmt_human(code, assistant, ollama, summary, verbose=True))
        else:
            print(fmt_human(code, assistant, ollama, summary,
                            verbose=args.verbose))
        return code

    if args.watch is None:
        sys.exit(one_pass())

    # --watch mode: loop forever
    sys.stderr.write(f"healthcheck loop @ {args.watch}s — Ctrl+C to exit\n")
    while True:
        try:
            one_pass()
        except KeyboardInterrupt:
            sys.exit(0)
        time.sleep(args.watch)


if __name__ == "__main__":
    main()
