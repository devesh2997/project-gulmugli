/**
 * useYaadeinTrigger — listens on the existing assistant WebSocket for
 * `yaadein_start` / `yaadein_stop` events and exposes the trigger
 * state to <Yaadein />.
 *
 * Why a window-event bridge (vs threading another field through
 * `useAssistant`):
 *   The assistant WebSocket already routes through `useAssistant.ts`,
 *   which has a typed `case` block for every message. Adding two new
 *   cases there would mean (a) extending the InternalState shape,
 *   (b) extending the AssistantStore contract, (c) plumbing the new
 *   field through every consumer that touches the store. For an
 *   ephemeral overlay that's only active for ~5 minutes a year, that's
 *   too much churn.
 *
 *   Instead, useAssistant's default branch logs unknown messages but
 *   doesn't crash. We tap the same WebSocket source from a parallel
 *   listener that just dispatches a window CustomEvent. The Yaadein
 *   component listens for the window event. Single responsibility,
 *   zero touch on the typed assistant store.
 *
 *   Tradeoff: we open a second WebSocket to the same URL. On a kiosk
 *   that's negligible. If we ever multiplex more ephemeral overlays
 *   like this, consider building a shared "ephemeral events" hook
 *   that consolidates one WebSocket and fans out to listeners.
 *
 * Dev hooks:
 *   - `window.__startYaadein()` — starts the slideshow without a
 *     backend connection.
 *   - `window.__stopYaadein()` — stops it.
 *   Both dispatch the same internal CustomEvent the WS listener fires.
 */

import { useEffect, useState } from 'react'

// ─── Types ────────────────────────────────────────────────────────────

/**
 * Payload that arrives with `yaadein_start`. `music` is the optional
 * filename declared at the top of captions.yaml. The component plays it
 * via `/api/yaadein/music` regardless of the filename — but we surface
 * it here so the component can decide "no music? skip the audio
 * element" without an extra HEAD request.
 */
export interface YaadeinStartDetail {
  music?: string | null
}

declare global {
  interface Window {
    __startYaadein?: (detail?: YaadeinStartDetail) => void
    __stopYaadein?: () => void
  }
}

// ─── Constants ────────────────────────────────────────────────────────

/**
 * The internal CustomEvent names that <Yaadein /> listens on. WS
 * messages, dev hooks, and any future trigger paths all funnel
 * through these two events.
 */
const YAADEIN_START_EVENT = 'jarvis-yaadein-start'
const YAADEIN_STOP_EVENT = 'jarvis-yaadein-stop'

// Reuse the same WS URL that App.tsx passes to useAssistant.
const DEFAULT_WS_URL = 'ws://localhost:8765'

// ─── Hook ─────────────────────────────────────────────────────────────

interface YaadeinTriggerState {
  active: boolean
  detail: YaadeinStartDetail
  /**
   * Stops the slideshow locally AND notifies the backend so it can
   * sync its own state (the backend has no view into "user dismissed
   * by Escape" otherwise).
   */
  stop: () => void
}

/**
 * Bridge the assistant WS + dev hooks into a simple active/detail
 * tuple. The component re-renders on every transition.
 */
export function useYaadeinTrigger(wsUrl: string = DEFAULT_WS_URL): YaadeinTriggerState {
  const [active, setActive] = useState(false)
  const [detail, setDetail] = useState<YaadeinStartDetail>({})

  // Window-event listeners — the only place state actually flips.
  useEffect(() => {
    const onStart = (e: Event): void => {
      const ce = e as CustomEvent<YaadeinStartDetail>
      setDetail(ce.detail || {})
      setActive(true)
    }
    const onStop = (): void => {
      setActive(false)
    }
    window.addEventListener(YAADEIN_START_EVENT, onStart)
    window.addEventListener(YAADEIN_STOP_EVENT, onStop)

    // Dev hooks. Mirror useEventTheme's `__setSimulatedEvent` shape.
    window.__startYaadein = (d?: YaadeinStartDetail) => {
      window.dispatchEvent(
        new CustomEvent<YaadeinStartDetail>(YAADEIN_START_EVENT, {
          detail: d ?? {},
        }),
      )
    }
    window.__stopYaadein = () => {
      window.dispatchEvent(new Event(YAADEIN_STOP_EVENT))
    }

    return () => {
      window.removeEventListener(YAADEIN_START_EVENT, onStart)
      window.removeEventListener(YAADEIN_STOP_EVENT, onStop)
      delete window.__startYaadein
      delete window.__stopYaadein
    }
  }, [])

  // Parallel WebSocket — taps the same backend URL as useAssistant but
  // only listens for yaadein_* messages. Failures are silent (the dev
  // hooks still work).
  useEffect(() => {
    let ws: WebSocket | null = null
    let cancelled = false
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null
    let reconnectDelay = 1000

    const connect = (): void => {
      if (cancelled) return
      try {
        ws = new WebSocket(wsUrl)
      } catch (err) {
        console.info('[useYaadeinTrigger] WS open failed:', err)
        scheduleReconnect()
        return
      }

      ws.onopen = () => {
        reconnectDelay = 1000
      }

      ws.onmessage = (event: MessageEvent) => {
        try {
          const raw = JSON.parse(event.data) as { type?: string } & Record<string, unknown>
          if (!raw || typeof raw.type !== 'string') return
          if (raw.type === 'yaadein_start') {
            const music = typeof raw.music === 'string' ? raw.music : null
            window.dispatchEvent(
              new CustomEvent<YaadeinStartDetail>(YAADEIN_START_EVENT, {
                detail: { music },
              }),
            )
          } else if (raw.type === 'yaadein_stop') {
            window.dispatchEvent(new Event(YAADEIN_STOP_EVENT))
          }
        } catch {
          // Non-JSON or unexpected — ignore. useAssistant logs broadly,
          // we don't need to double-log.
        }
      }

      ws.onclose = () => {
        scheduleReconnect()
      }

      ws.onerror = () => {
        try {
          ws?.close()
        } catch {
          // already closing
        }
      }
    }

    const scheduleReconnect = (): void => {
      if (cancelled || reconnectTimer) return
      const delay = reconnectDelay
      reconnectTimer = setTimeout(() => {
        reconnectTimer = null
        reconnectDelay = Math.min(delay * 2, 10_000)
        connect()
      }, delay)
    }

    connect()

    return () => {
      cancelled = true
      if (reconnectTimer) clearTimeout(reconnectTimer)
      try {
        ws?.close()
      } catch {
        // already closed
      }
    }
  }, [wsUrl])

  // Stop helper — local set + dispatch so any other components / dev
  // tools observing the same event get the signal.
  const stop = (): void => {
    setActive(false)
    window.dispatchEvent(new Event(YAADEIN_STOP_EVENT))
  }

  return { active, detail, stop }
}
