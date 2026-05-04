/**
 * ConfettiLayer — celebratory particle overlay.
 *
 * Two modes, both rendered with framer-motion (no extra deps):
 *
 *   1. **Burst** — a one-shot heavy spray (~100 pieces) falling from the
 *      top, rotating + drifting, that settles in 3-4 seconds. Triggered
 *      by `window.dispatchEvent(new CustomEvent('vesper:confetti-burst'))`
 *      or via the dev hook `window.__triggerConfettiBurst()`.
 *
 *   2. **Ambient** — sparse, gentle, ongoing confetti (5-10 pieces in
 *      flight at any time) that runs continuously while the active event
 *      is "today". A new piece is spawned every ~600-1200ms; each piece
 *      removes itself when its drift animation completes.
 *
 * Performance notes (Jetson Chromium kiosk @ 60fps):
 *   - Each piece is a `motion.div` animated via the GPU-accelerated
 *     transform pipeline (translate + rotate). No layout thrash.
 *   - `pointer-events: none` on the layer so confetti never steals taps.
 *   - `position: fixed` + `inset: 0` to cover the viewport regardless of
 *     scroll. z-index is below the ErrorBoundary fallback (z=9999) but
 *     above the dashboard's normal stacking context.
 *   - When the event ends or the component unmounts, AnimatePresence
 *     drains the pieces, the spawn timer is cleared, and the listener is
 *     removed. No zombie animations.
 *
 * Brand-agnostic palette: colors come from CSS vars at spawn time
 *   (`--personality-accent`, `--time-current-accent_glow`, etc.) plus a
 *   small set of warm neutrals so the confetti tracks the personality /
 *   event theme rather than locking to pinks/golds.
 *
 * Triggering:
 *   - Ambient: independently polls `/api/events/current` every 60s and
 *     gates on `is_today`. (TODO: switch to `is_triggered` once Phase
 *     1.2 ships; currently the field is always false in the API.) Also
 *     listens for `event-sim-change` to react to
 *     `window.__setSimulatedEvent(...)` instantly.
 *   - Burst: listens for `'vesper:confetti-burst'` window events.
 *
 * Dev hooks:
 *   - `window.__triggerConfettiBurst()` — fire a burst regardless of
 *     event state. Mirrors the `__setSimulatedHour` / `__setSimulatedEvent`
 *     pattern.
 */

import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'

// ─── Types ────────────────────────────────────────────────────────────────────

type PieceShape = 'rect' | 'circle'

interface ConfettiPiece {
  id: number
  /** Horizontal start position as % of viewport width (0-100). */
  startX: number
  /** Horizontal drift in vw units (signed: -20..20). */
  driftVW: number
  /** Falling distance in vh units (always positive, 100-130). */
  fallVH: number
  /** Rotation in degrees over the lifetime (-720..720). */
  rotation: number
  /** Animation duration in seconds. */
  duration: number
  /** Spawn delay in seconds (used to stagger burst pieces). */
  delay: number
  /** Piece size in px (4-12). */
  size: number
  /** Piece aspect ratio for rectangles (1 = square, up to 3 = streamer). */
  aspect: number
  shape: PieceShape
  color: string
}

/** Shape of `GET /api/events/current`; mirrors useEventTheme's type. */
interface ActiveEventResponse {
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

declare global {
  interface Window {
    __triggerConfettiBurst?: () => void
  }
}

// ─── Palette ──────────────────────────────────────────────────────────────────

/**
 * Warm fallback palette — used in addition to the live theme accent so
 * a single-accent personality still reads as celebratory. These are
 * intentionally muted pastels (not Crayola) so they sit nicely against
 * the canvas's deep gradient.
 */
const WARM_FALLBACK_PALETTE = [
  '#f5d486', // soft gold
  '#f0a89e', // warm coral
  '#d9c2e3', // dusk lilac
  '#a8d5d0', // pale teal
  '#f7e9c4', // cream
] as const

/**
 * Read CSS custom properties that the personality + event + time-of-day
 * layers populate. Returns a deduped list of hex colors for confetti
 * pieces. Called fresh per spawn so theme changes propagate without
 * needing to re-render the layer.
 */
function readActivePalette(): string[] {
  if (typeof document === 'undefined') return [...WARM_FALLBACK_PALETTE]
  const cs = getComputedStyle(document.documentElement)

  const candidates = [
    cs.getPropertyValue('--personality-accent').trim(),
    cs.getPropertyValue('--time-current-accent_glow').trim(),
    cs.getPropertyValue('--event-confetti-accent').trim(),
  ].filter((v) => v.length > 0 && v.startsWith('#'))

  const merged = [...candidates, ...WARM_FALLBACK_PALETTE]
  // Dedupe while preserving order so the active accent wins.
  return Array.from(new Set(merged))
}

// ─── Piece generation ─────────────────────────────────────────────────────────

let nextPieceId = 1

function pickColor(palette: string[]): string {
  return palette[Math.floor(Math.random() * palette.length)]!
}

function makeBurstPiece(palette: string[]): ConfettiPiece {
  const id = nextPieceId++
  const shape: PieceShape = Math.random() < 0.35 ? 'circle' : 'rect'
  const size = 4 + Math.random() * 8 // 4-12
  return {
    id,
    startX: Math.random() * 100,
    driftVW: (Math.random() - 0.5) * 40, // -20..20
    fallVH: 105 + Math.random() * 25, // 105-130
    rotation: (Math.random() - 0.5) * 1440, // -720..720
    duration: 2.6 + Math.random() * 1.6, // 2.6-4.2s
    delay: Math.random() * 0.4, // 0-400ms stagger
    size,
    aspect: shape === 'circle' ? 1 : 1 + Math.random() * 2,
    shape,
    color: pickColor(palette),
  }
}

function makeAmbientPiece(palette: string[]): ConfettiPiece {
  const id = nextPieceId++
  const shape: PieceShape = Math.random() < 0.4 ? 'circle' : 'rect'
  const size = 4 + Math.random() * 6 // 4-10 — slightly smaller for ambient
  return {
    id,
    startX: Math.random() * 100,
    driftVW: (Math.random() - 0.5) * 24,
    fallVH: 110 + Math.random() * 20,
    rotation: (Math.random() - 0.5) * 720,
    duration: 6 + Math.random() * 4, // 6-10s — slow drift
    delay: 0,
    size,
    aspect: shape === 'circle' ? 1 : 1 + Math.random() * 1.6,
    shape,
    color: pickColor(palette),
  }
}

// ─── Piece component ──────────────────────────────────────────────────────────

interface PieceProps {
  piece: ConfettiPiece
  onComplete: (id: number) => void
}

function Piece({ piece, onComplete }: PieceProps): React.ReactElement {
  const width = piece.size * piece.aspect
  const height = piece.size

  return (
    <motion.div
      initial={{
        x: `${piece.startX}vw`,
        y: '-10vh',
        rotate: 0,
        opacity: 0,
      }}
      animate={{
        x: `calc(${piece.startX}vw + ${piece.driftVW}vw)`,
        y: `${piece.fallVH}vh`,
        rotate: piece.rotation,
        opacity: [0, 1, 1, 0.85, 0],
      }}
      transition={{
        duration: piece.duration,
        delay: piece.delay,
        ease: 'easeIn',
        opacity: {
          duration: piece.duration,
          delay: piece.delay,
          times: [0, 0.05, 0.7, 0.9, 1],
          ease: 'linear',
        },
      }}
      onAnimationComplete={() => onComplete(piece.id)}
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width,
        height,
        backgroundColor: piece.color,
        borderRadius: piece.shape === 'circle' ? '50%' : 1,
        // Compose with mix-blend-mode so pieces brighten the canvas
        // without looking pasted on. `screen` is a soft bloom that
        // tracks the underlying gradient nicely.
        mixBlendMode: 'screen',
        willChange: 'transform, opacity',
      }}
    />
  )
}

// ─── Main component ──────────────────────────────────────────────────────────

const POLL_INTERVAL_MS = 60_000
const AMBIENT_SPAWN_MIN_MS = 600
const AMBIENT_SPAWN_MAX_MS = 1200
const AMBIENT_MAX_INFLIGHT = 10
const BURST_PIECE_COUNT = 100

export function ConfettiLayer(): React.ReactElement {
  const [pieces, setPieces] = useState<ConfettiPiece[]>([])
  const [ambientActive, setAmbientActive] = useState<boolean>(false)

  // Always-fresh refs so timer callbacks see current values without
  // resubscribing.
  const ambientActiveRef = useRef(ambientActive)
  useEffect(() => {
    ambientActiveRef.current = ambientActive
  }, [ambientActive])

  // ── Burst trigger ──────────────────────────────────────────────────────
  useEffect(() => {
    const fireBurst = (): void => {
      const palette = readActivePalette()
      const burst: ConfettiPiece[] = []
      for (let i = 0; i < BURST_PIECE_COUNT; i += 1) {
        burst.push(makeBurstPiece(palette))
      }
      setPieces((prev) => [...prev, ...burst])
    }

    const onWindowEvent = (): void => fireBurst()
    window.addEventListener('vesper:confetti-burst', onWindowEvent)

    // Dev hook — mirrors __setSimulatedEvent / __setSimulatedHour.
    window.__triggerConfettiBurst = fireBurst

    return () => {
      window.removeEventListener('vesper:confetti-burst', onWindowEvent)
      if (window.__triggerConfettiBurst === fireBurst) {
        delete window.__triggerConfettiBurst
      }
    }
  }, [])

  // ── Ambient gate: poll /api/events/current ────────────────────────────
  useEffect(() => {
    let cancelled = false

    const evaluate = async (): Promise<void> => {
      try {
        const res = await fetch('/api/events/current', {
          headers: { Accept: 'application/json' },
        })
        if (!res.ok) {
          // Don't flip ambient state on transient errors — keep whatever
          // we last decided. (Mirrors useEventTheme's no-flicker rule.)
          console.info(
            `[ConfettiLayer] /api/events/current returned ${res.status}; keeping ambient state`,
          )
          return
        }
        const body = (await res.json()) as ActiveEventResponse | null
        if (cancelled) return

        // TODO: switch to `is_triggered` once Phase 1.2 ships. Today the
        // backend always returns is_triggered=false, so we'd never spawn
        // anything. Gating on is_today gives the right behavior for the
        // launch-day window.
        const shouldRun = body !== null && body.is_today === true
        setAmbientActive(shouldRun)
      } catch (err) {
        console.info('[ConfettiLayer] poll failed:', err)
      }
    }

    void evaluate()
    const intervalId = window.setInterval(() => {
      void evaluate()
    }, POLL_INTERVAL_MS)

    // React to window.__setSimulatedEvent immediately (the simulated
    // event is internal to useEventTheme — we re-poll, which will skip
    // the simulation, but the event-sim-change signal still nudges us
    // into refreshing whichever way is more correct).
    const onSimChange = (): void => {
      void evaluate()
    }
    window.addEventListener('event-sim-change', onSimChange)

    return () => {
      cancelled = true
      window.clearInterval(intervalId)
      window.removeEventListener('event-sim-change', onSimChange)
    }
  }, [])

  // ── Ambient spawner ────────────────────────────────────────────────────
  useEffect(() => {
    if (!ambientActive) return

    let timeoutId: number | undefined

    const scheduleNext = (): void => {
      const delay =
        AMBIENT_SPAWN_MIN_MS +
        Math.random() * (AMBIENT_SPAWN_MAX_MS - AMBIENT_SPAWN_MIN_MS)
      timeoutId = window.setTimeout(() => {
        if (!ambientActiveRef.current) return
        const palette = readActivePalette()
        setPieces((prev) => {
          // Cap the in-flight ambient pieces so a long-running session
          // doesn't pile up memory if the spawner outruns the falling.
          if (prev.length >= AMBIENT_MAX_INFLIGHT) return prev
          return [...prev, makeAmbientPiece(palette)]
        })
        scheduleNext()
      }, delay)
    }

    scheduleNext()

    return () => {
      if (timeoutId !== undefined) window.clearTimeout(timeoutId)
    }
  }, [ambientActive])

  // ── Piece cleanup ──────────────────────────────────────────────────────
  // Each piece removes itself via onAnimationComplete; AnimatePresence
  // isn't strictly needed because we have no exit animation, but using
  // it lets us add one later without restructuring.
  const removePiece = (id: number): void => {
    setPieces((prev) => prev.filter((p) => p.id !== id))
  }

  return (
    <div
      aria-hidden
      style={{
        position: 'fixed',
        inset: 0,
        pointerEvents: 'none',
        // Above dashboard content (which tops out around z=50 for the
        // sleep overlay) but below the ErrorBoundary fallback (z=9999).
        zIndex: 100,
        overflow: 'hidden',
      }}
    >
      <AnimatePresence>
        {pieces.map((piece) => (
          <Piece key={piece.id} piece={piece} onComplete={removePiece} />
        ))}
      </AnimatePresence>
    </div>
  )
}

export default ConfettiLayer
