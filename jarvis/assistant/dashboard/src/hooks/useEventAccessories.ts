/**
 * useEventAccessories — exposes the active event pack's avatar accessories.
 *
 * Mirrors `useEventTheme`'s polling shape (60s interval + on
 * `event-sim-change` custom event) but lives in its own hook so the theme
 * hook stays focused on CSS-var application. Same source of truth though:
 * `GET /api/events/current` -> if an event is active and within its day
 * window, fetch `event.avatar_url` (resolves to
 * `/api/events/{pack}/theme/avatar`) and read `.accessories`.
 *
 * Returns `[]` when:
 *   - No active event
 *   - Event is outside its is_today/is_eve/is_aftermath window
 *   - The pack has no `theme/avatar.json` (the endpoint returns `{}`)
 *   - Network blip (we keep returning `[]` rather than crashing)
 *
 * Network failures DO NOT clear the last successful list — they're logged
 * and the existing accessories stay put until the next definitive poll
 * (matches `useEventTheme`'s no-flicker philosophy).
 *
 * Dev hook: `window.__setSimulatedAccessories(accessories | null)` mirrors
 * `__setSimulatedEvent`. Pass `null` to drop back to real fetch, or an
 * array (incl. empty) to short-circuit to a fixed value.
 */

import { useEffect, useState } from 'react'

import type { ActiveEventResponse } from './useEventTheme'

// ─── Globals (dev hook) ───────────────────────────────────────────────────────

declare global {
  interface Window {
    __setSimulatedAccessories?: (accessories: string[] | null) => void
  }
}

// `undefined` = no simulation (real fetch wins).
// `string[]`  = simulate this list (incl. []).
// The exposed dev setter accepts `null` as "go back to real fetch", which
// we collapse to `undefined` internally so the runtime check is a single
// `!== undefined` (and TS narrowing matches that).
let simulatedAccessories: string[] | undefined = undefined

if (typeof window !== 'undefined') {
  window.__setSimulatedAccessories = (accessories: string[] | null) => {
    simulatedAccessories = accessories === null ? undefined : accessories
    console.log(
      '[useEventAccessories] Simulated accessories:',
      accessories === null ? 'OFF (real fetch)' : accessories,
    )
    // Reuse the existing event-sim-change channel so a single dispatch
    // wakes up both useEventTheme and this hook (they cover the same
    // dev workflow — set the event, then set the accessories).
    window.dispatchEvent(new CustomEvent('event-sim-change'))
  }
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

const POLL_INTERVAL_MS = 60_000

interface AvatarAccessoriesResponse {
  accessories?: string[]
}

export function useEventAccessories(): string[] {
  const [accessories, setAccessories] = useState<string[]>([])

  useEffect(() => {
    let cancelled = false

    const runPoll = async (): Promise<void> => {
      try {
        // Simulation short-circuit — same precedence as useEventTheme.
        if (simulatedAccessories !== undefined) {
          if (!cancelled) setAccessories(simulatedAccessories)
          return
        }

        const eventRes = await fetch('/api/events/current', {
          headers: { 'Accept': 'application/json' },
        })
        if (!eventRes.ok) {
          console.info(
            `[useEventAccessories] /api/events/current returned ${eventRes.status}; keeping current list`,
          )
          return
        }
        const event = (await eventRes.json()) as ActiveEventResponse | null
        if (cancelled) return

        if (event === null) {
          setAccessories([])
          return
        }

        // Only render accessories within the event's day window. Matches
        // useEventTheme — outside the window, the pack effectively
        // "isn't active" from a UI standpoint.
        const isWithinWindow =
          event.is_today || event.is_eve || event.is_aftermath
        if (!isWithinWindow) {
          setAccessories([])
          return
        }

        const avatarRes = await fetch(event.avatar_url, {
          headers: { 'Accept': 'application/json' },
        })
        if (!avatarRes.ok) {
          console.info(
            `[useEventAccessories] avatar_url ${event.avatar_url} returned ${avatarRes.status}`,
          )
          return
        }
        const body = (await avatarRes.json()) as AvatarAccessoriesResponse
        if (cancelled) return

        const next = Array.isArray(body?.accessories)
          ? body.accessories.filter((a): a is string => typeof a === 'string')
          : []
        setAccessories(next)
      } catch (err) {
        console.info('[useEventAccessories] poll failed:', err)
      }
    }

    void runPoll()
    const intervalId = setInterval(() => {
      void runPoll()
    }, POLL_INTERVAL_MS)

    const onSimChange = () => {
      void runPoll()
    }
    window.addEventListener('event-sim-change', onSimChange)

    return () => {
      cancelled = true
      clearInterval(intervalId)
      window.removeEventListener('event-sim-change', onSimChange)
      // Drop the dev hook so a future remount installs a fresh closure
      // (avoids stale references to a torn-down hook instance — same
      // pattern as useEventTheme's __setSimulatedEvent cleanup).
      if (typeof window !== 'undefined') {
        delete window.__setSimulatedAccessories
      }
    }
  }, [])

  return accessories
}
