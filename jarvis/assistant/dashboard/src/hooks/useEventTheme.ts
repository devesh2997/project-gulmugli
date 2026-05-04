/**
 * useEventTheme — applies the active event pack's theme tokens on top of
 * the personality + time-of-day layers.
 *
 * Polls `GET /api/events/current` every 60s (and on mount). When an event
 * is active (is_today / is_eve / is_aftermath), fetches the pack's
 * `theme_url` and writes the returned tokens directly to
 * `document.documentElement.style` using their canonical CSS-var names
 * (e.g. `--personality-accent`, `--animation-orb-breathe-duration`).
 *
 * Layering choice — OVERRIDE existing vars (vs introducing
 * `--event-current-*`):
 * The component layer already consumes `--personality-accent`, the
 * `-rgb` variant, and the time-of-day-driven canvas vars. Introducing a
 * new prefix would require every consumer to grow a fallback chain
 * (`var(--event-current-accent, var(--time-current-..., var(...))))`).
 * Inline-style writes on `document.documentElement` win against the
 * CSS-set values from TokenProvider/useTimeOfDay (style-attribute
 * specificity > stylesheet declarations on :root), which gives us the
 * desired precedence order for free:
 *
 *   base personality colors  (TokenProvider — :root via setProperty)
 *     ↓
 *   time-of-day palette       (useTimeOfDay — :root via setProperty)
 *     ↓
 *   EVENT THEME (this hook)   (:root via setProperty — *last writer wins
 *                              for the same property*; we also track keys
 *                              so cleanup reverts cleanly)
 *     ↓
 *   user overrides            (TokenProvider also handles these)
 *
 * The trick: TokenProvider's effect re-runs on token changes and rewrites
 * its values, but it only touches the keys it owns. We track which keys
 * we've written and on cleanup call `removeProperty` for each — at that
 * point the cascade falls back to whatever the next layer set.
 *
 * No flicker: failed polls (network blip / WS reconnect) are logged to
 * console.info but DO NOT clear the active theme. The theme is only
 * cleared when a poll definitively succeeds AND returns null.
 *
 * Dev hook: `window.__setSimulatedEvent(eventData | null)` mirrors
 * `useTimeOfDay`'s `__setSimulatedHour` pattern — it short-circuits the
 * fetch and lets you preview the birthday theme without changing the
 * system clock.
 */

import { useEffect, useRef } from 'react'

import type { TokenValue } from '../types/assistant'

// ─── Types ────────────────────────────────────────────────────────────────────

/** Shape of `GET /api/events/current` (or `null` when no event is active). */
export interface ActiveEventResponse {
  event_id: string
  display_name: string
  days_until: number
  is_today: boolean
  is_eve: boolean
  is_aftermath: boolean
  features: string[]
  trigger: {
    auto_midnight: boolean
    manual_phrases: string[]
  }
  is_triggered: boolean
  theme_url: string
  avatar_url: string
}

/**
 * Event theme tokens are a flat map of CSS-var-name → value (string,
 * number, boolean). We accept the same TokenValue union so a future
 * pack can ship nested objects, but the flat form is the canonical
 * shape for now.
 *
 * Empty object (`{}`) means "the pack opts not to override anything" —
 * a valid response, treated as a no-op.
 */
export type EventThemeTokens = Record<string, TokenValue>

// ─── Globals (dev hook) ───────────────────────────────────────────────────────

declare global {
  interface Window {
    __setSimulatedEvent?: (event: ActiveEventResponse | null) => void
  }
}

let simulatedEvent: ActiveEventResponse | null | undefined = undefined
//                                                          ^^^^^^^^^
// `undefined` = no simulation, fall through to real fetch.
// `null`      = simulate "no active event".
// object      = simulate this active event.

if (typeof window !== 'undefined') {
  window.__setSimulatedEvent = (event: ActiveEventResponse | null) => {
    simulatedEvent = event
    console.log(
      `[useEventTheme] Simulated event:`,
      event === null ? 'OFF (no event)' : event.event_id,
    )
    window.dispatchEvent(new CustomEvent('event-sim-change'))
  }
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

/** Parse a 6-digit hex to "r, g, b" so we can also set the `-rgb` variant. */
function hexToRgbString(hex: string): string | null {
  if (typeof hex !== 'string' || !hex.startsWith('#')) return null
  const clean = hex.replace('#', '').slice(0, 6)
  if (clean.length < 6) return null
  const n = parseInt(clean, 16)
  if (isNaN(n)) return null
  return `${(n >> 16) & 0xff}, ${(n >> 8) & 0xff}, ${n & 0xff}`
}

/**
 * Flatten a (possibly nested) tokens object to a flat list of
 * `[--var-name, value]` pairs. Mirrors the convention used in
 * TokenProvider.flattenToCSSVars: keys joined with `-`, leading `--`
 * added if missing.
 */
function flattenTokens(
  tokens: EventThemeTokens,
  prefix = '',
): Array<[string, string]> {
  const out: Array<[string, string]> = []
  for (const [rawKey, value] of Object.entries(tokens)) {
    if (value === null || value === undefined) continue
    // If the key already starts with `--`, it's a fully-qualified CSS
    // var name — use it as-is. Otherwise treat it as a nested segment.
    const isCSSVar = rawKey.startsWith('--')
    const segment = isCSSVar
      ? rawKey
      : prefix
        ? `${prefix}-${rawKey}`
        : rawKey

    if (typeof value === 'object' && !Array.isArray(value)) {
      // Nested object — recurse. Skip recursing if the parent key was
      // already a `--` var, which doesn't make sense as a parent.
      if (!isCSSVar) {
        out.push(...flattenTokens(value as EventThemeTokens, segment))
      }
      continue
    }
    if (
      typeof value === 'string' ||
      typeof value === 'number' ||
      typeof value === 'boolean'
    ) {
      const property = segment.startsWith('--') ? segment : `--${segment}`
      out.push([property, String(value)])
    }
  }
  return out
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

const POLL_INTERVAL_MS = 60_000

export function useEventTheme(): void {
  // Track which CSS vars we've applied so cleanup can remove exactly
  // those (and not blow away anything TokenProvider/useTimeOfDay set).
  const appliedKeysRef = useRef<Set<string>>(new Set())

  // Track the currently applied event id so we don't re-fetch + re-apply
  // on every poll if nothing has changed.
  const appliedEventIdRef = useRef<string | null>(null)

  useEffect(() => {
    let cancelled = false

    /** Apply a flat tokens map to :root, replacing any previous event vars. */
    const applyTokens = (tokens: EventThemeTokens, eventId: string): void => {
      const root = document.documentElement.style
      const flat = flattenTokens(tokens)
      const newKeys = new Set<string>()

      // Set the new vars + their `-rgb` variant for hex colors.
      for (const [property, value] of flat) {
        root.setProperty(property, value)
        newKeys.add(property)
        const rgb = hexToRgbString(value)
        if (rgb) {
          const rgbProp = `${property}-rgb`
          root.setProperty(rgbProp, rgb)
          newKeys.add(rgbProp)
        }
      }

      // Remove vars that were set last time but aren't in this payload —
      // important when the same event ships different tokens after a reload.
      for (const oldKey of appliedKeysRef.current) {
        if (!newKeys.has(oldKey)) {
          root.removeProperty(oldKey)
        }
      }

      appliedKeysRef.current = newKeys
      appliedEventIdRef.current = eventId
    }

    /** Remove every event-applied var so the cascade reverts. */
    const clearTokens = (): void => {
      const root = document.documentElement.style
      for (const key of appliedKeysRef.current) {
        root.removeProperty(key)
      }
      appliedKeysRef.current = new Set()
      appliedEventIdRef.current = null
    }

    /**
     * Single poll cycle. Order:
     *   1. Decide what event (if any) is "active" — simulated or real.
     *   2. If none, clear tokens and return.
     *   3. Otherwise fetch theme tokens and apply.
     *
     * Network failures DO NOT clear the active theme — they're logged
     * and the existing theme stays put until the next successful poll.
     */
    const runPoll = async (): Promise<void> => {
      try {
        let event: ActiveEventResponse | null

        if (simulatedEvent !== undefined) {
          event = simulatedEvent
        } else {
          const res = await fetch('/api/events/current', {
            headers: { 'Accept': 'application/json' },
          })
          if (!res.ok) {
            console.info(
              `[useEventTheme] /api/events/current returned ${res.status}; keeping current theme`,
            )
            return
          }
          // The endpoint returns `null` (literally) when no event is
          // active. JSON.parse(null) === null, so res.json() will give
          // us either null or the ActiveEventResponse object.
          event = (await res.json()) as ActiveEventResponse | null
        }

        if (cancelled) return

        if (event === null) {
          if (appliedEventIdRef.current !== null) {
            clearTokens()
          }
          return
        }

        // Theme gating policy:
        //   - On the day itself: gate on `is_triggered` so the surprise
        //     stays dormant until Devesh fires the manual phrase / app
        //     button. (For 2027+ where auto_midnight may flip true, the
        //     backend will start returning is_triggered=true at 00:00,
        //     same effect.)
        //   - In the eve/aftermath windows: the theme can show as a
        //     soft pre-/post-celebration ramp without waiting for the
        //     trigger. eve = "tomorrow's the day, gentle hint." aftermath
        //     = "yesterday was special, soft glow."
        const showOnEveOrAftermath = event.is_eve || event.is_aftermath
        const showToday = event.is_today && event.is_triggered
        if (!showToday && !showOnEveOrAftermath) {
          if (appliedEventIdRef.current !== null) {
            clearTokens()
          }
          return
        }

        // If we already have this event's tokens applied, no-op (avoids
        // a flicker on every 60s poll cycle).
        if (appliedEventIdRef.current === event.event_id) {
          return
        }

        // Fetch theme tokens — same simulation path applies: when
        // simulated, look at the simulated event's theme_url IF the
        // dev attaches one, otherwise treat as empty.
        let tokens: EventThemeTokens = {}
        try {
          const themeRes = await fetch(event.theme_url, {
            headers: { 'Accept': 'application/json' },
          })
          if (themeRes.ok) {
            const body = (await themeRes.json()) as unknown
            if (body && typeof body === 'object' && !Array.isArray(body)) {
              tokens = body as EventThemeTokens
            }
          } else {
            console.info(
              `[useEventTheme] theme_url ${event.theme_url} returned ${themeRes.status}`,
            )
          }
        } catch (err) {
          console.info('[useEventTheme] theme fetch failed:', err)
        }

        if (cancelled) return

        // Strip the `_comment` key (used in the placeholder JSON) and
        // anything else that starts with `_` so authors can drop notes
        // into the file without polluting the CSS namespace.
        const cleaned: EventThemeTokens = {}
        for (const [k, v] of Object.entries(tokens)) {
          if (!k.startsWith('_')) cleaned[k] = v
        }

        applyTokens(cleaned, event.event_id)
      } catch (err) {
        // Top-level network errors (DNS down, server unreachable, etc.)
        // — log and keep the existing theme.
        console.info('[useEventTheme] poll failed:', err)
      }
    }

    // Fire immediately so the dashboard is right on first paint.
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
      // Also remove any event-applied vars so the dashboard reverts
      // cleanly if the hook unmounts (HMR, parent re-mounts, etc.).
      clearTokens()
      // Drop the dev hook so a future remount installs a fresh one
      // (avoids stale closures pointing at a torn-down hook instance).
      if (typeof window !== 'undefined') {
        delete window.__setSimulatedEvent
      }
    }
  }, [])
}
