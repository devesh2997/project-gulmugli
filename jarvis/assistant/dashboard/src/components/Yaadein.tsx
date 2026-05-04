/**
 * Yaadein — full-screen photo slideshow with hand-written captions.
 *
 * Activates when a `yaadein_start` event arrives over the WebSocket
 * (or the dev hook `window.__startYaadein()` fires). Crossfades through
 * the photos with a subtle Ken-Burns zoom; lays a soft gradient
 * caption pad at the bottom in the project_ag style.
 *
 * Design:
 *   - The photo list is fetched ONCE on activation, not on every
 *     render. The hook hot-loads the manifest from `/api/yaadein/list`,
 *     then the component cycles through the photos client-side.
 *   - Each photo shows for ~6s with a 1s crossfade. Both the previous
 *     and next images mount during the transition (AnimatePresence
 *     `mode="sync"`) so the fade is true cross-blend, not pop-in.
 *   - Captions sit on a vertical gradient (transparent → black) that
 *     covers the bottom third. Caption text is the only thing in
 *     this component that gets larger fonts — at kiosk distances
 *     small text disappears.
 *   - Dismissal: Escape OR a click anywhere on the overlay both call
 *     `stop()` from useYaadeinTrigger, which dispatches a stop event
 *     locally AND tells the backend (so server-side state is in sync).
 *
 * Brand-agnostic: no "Astha" string baked in. The header shows
 * `display_name` from the API (for the v1 pack that's "Astha's
 * Birthday" — but for any future pack with photos it'll be that
 * pack's name).
 *
 * z-index: above main content (the avatar, music player, etc.) but
 * below the ErrorBoundary. The kiosk's ErrorBoundary fallback uses
 * z-index 999; we sit at 60 so a render-time crash in this component
 * still shows the recoverable error UI on top.
 */

import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'

import { useYaadeinTrigger } from '../hooks/useYaadeinTrigger'

// ─── Types ────────────────────────────────────────────────────────────

/**
 * Single photo entry as returned by `/api/yaadein/list`. The URL is
 * server-relative; the browser resolves it against the dashboard's
 * origin. Caption can be empty string (the auto-include path), in
 * which case we render the photo without a caption pad.
 */
interface YaadeinPhotoEntry {
  photo_url: string
  caption: string
}

/**
 * Manifest as returned by `/api/yaadein/list`.
 */
interface YaadeinManifest {
  pack_id: string
  display_name: string
  music_url: string | null
  photos: YaadeinPhotoEntry[]
}

// ─── Constants ────────────────────────────────────────────────────────

/** Per-photo display duration. Configurable here, NOT in YAML for v1. */
const PHOTO_DURATION_MS = 6_000

/** Crossfade transition duration. */
const FADE_MS = 1_000

/**
 * Default loop policy: infinite, until the user stops. The component
 * exposes `loop_count` as a hardcoded `Infinity` so the call sites
 * don't have to pass anything; if we ever want a finite loop, swap
 * this and add UI.
 */
const LOOP_COUNT: number = Infinity

// ─── Component ────────────────────────────────────────────────────────

export function Yaadein(): React.ReactElement | null {
  const trigger = useYaadeinTrigger()
  const [manifest, setManifest] = useState<YaadeinManifest | null>(null)
  const [photoIndex, setPhotoIndex] = useState(0)
  const loopCountRef = useRef(0)
  const audioRef = useRef<HTMLAudioElement | null>(null)

  // Fetch the photo manifest once when the slideshow becomes active.
  // We always re-fetch on each (re)activation — on the day-of, photos
  // may be added between sessions and we want the latest list. The
  // cleanup function handles the deactivation reset (so we satisfy
  // react-hooks/set-state-in-effect: state mutations live in async
  // callbacks or the cleanup, not the synchronous effect body).
  useEffect(() => {
    if (!trigger.active) return

    let cancelled = false
    const run = async (): Promise<void> => {
      try {
        const res = await fetch('/api/yaadein/list', {
          headers: { Accept: 'application/json' },
        })
        if (!res.ok) {
          console.info(`[Yaadein] /api/yaadein/list returned ${res.status}`)
          return
        }
        const body = (await res.json()) as YaadeinManifest
        if (cancelled) return
        if (!body || !Array.isArray(body.photos)) {
          console.info('[Yaadein] manifest body has no photos array:', body)
          return
        }
        setManifest(body)
        setPhotoIndex(0)
        loopCountRef.current = 0
      } catch (err) {
        console.info('[Yaadein] manifest fetch failed:', err)
      }
    }
    void run()

    return () => {
      cancelled = true
      // Reset state on deactivation so a re-trigger starts cleanly.
      setManifest(null)
      setPhotoIndex(0)
      loopCountRef.current = 0
    }
  }, [trigger.active])

  // Auto-advance timer. Wraps around at the end; bumps loopCountRef and
  // stops the slideshow once we hit LOOP_COUNT.
  useEffect(() => {
    if (!trigger.active || !manifest || manifest.photos.length === 0) return

    const total = manifest.photos.length
    const id = setTimeout(() => {
      setPhotoIndex(prev => {
        const next = prev + 1
        if (next >= total) {
          loopCountRef.current += 1
          if (loopCountRef.current >= LOOP_COUNT) {
            // Last loop — let `trigger.stop()` fire on the next tick.
            // `stop()` sets active=false which un-mounts this component,
            // so we don't need to clear any local state here.
            trigger.stop()
            return prev
          }
          return 0
        }
        return next
      })
    }, PHOTO_DURATION_MS)

    return () => clearTimeout(id)
  }, [trigger.active, manifest, photoIndex, trigger])

  // Background music — only when the manifest declares one. We use
  // a ref-controlled HTMLAudioElement instead of a JSX <audio> tag so
  // that we can call .pause() during the closing crossfade without a
  // re-render dance.
  useEffect(() => {
    if (!trigger.active || !manifest?.music_url) {
      // Whenever inactive or no music, ensure any leftover audio is
      // paused. Browsers will leak playing audio across mount cycles
      // without this guard if the parent re-renders.
      if (audioRef.current) {
        audioRef.current.pause()
        audioRef.current.currentTime = 0
      }
      return
    }
    const a = new Audio(manifest.music_url)
    a.loop = true
    a.volume = 0.4
    audioRef.current = a
    // play() returns a Promise that rejects if autoplay is blocked.
    // The kiosk runs Chromium in app mode where autoplay-allowlist
    // covers localhost — but we still defensively swallow rejection.
    a.play().catch(err => {
      console.info('[Yaadein] background music autoplay blocked:', err)
    })
    return () => {
      a.pause()
      a.currentTime = 0
      if (audioRef.current === a) {
        audioRef.current = null
      }
    }
  }, [trigger.active, manifest?.music_url])

  // Escape key dismisses. Lives in its own effect so it's only active
  // while the slideshow is. Stable handler — captures the latest
  // `trigger` via closure on every effect re-run.
  useEffect(() => {
    if (!trigger.active) return
    const onKey = (e: KeyboardEvent): void => {
      if (e.key === 'Escape') {
        e.preventDefault()
        trigger.stop()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [trigger.active, trigger])

  if (!trigger.active) return null

  const photos = manifest?.photos ?? []
  const current = photos[photoIndex] ?? null

  // The "no manifest yet" / "empty manifest" states render the same
  // dark backdrop with a centered hint, so the overlay still feels
  // intentional during the brief fetch window.
  return (
    <AnimatePresence mode="wait">
      <motion.div
        key="yaadein-overlay"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.5 }}
        // Click anywhere to dismiss (matching the kiosk gesture
        // affordance — Escape for keyboards, tap for touchscreens).
        onClick={() => trigger.stop()}
        style={{
          position: 'fixed',
          inset: 0,
          zIndex: 60,
          backgroundColor: '#000',
          overflow: 'hidden',
          cursor: 'pointer',
        }}
        role="dialog"
        aria-label={
          manifest?.display_name
            ? `${manifest.display_name} — memories slideshow`
            : 'Memories slideshow'
        }
      >
        {/* Header — pack display name + dismiss hint. */}
        {manifest?.display_name && (
          <div
            style={{
              position: 'absolute',
              top: 24,
              left: 32,
              zIndex: 3,
              color: 'rgba(255, 255, 255, 0.55)',
              fontSize: 18,
              fontWeight: 600,
              letterSpacing: '0.04em',
              pointerEvents: 'none',
            }}
          >
            {manifest.display_name}
            <span
              style={{
                marginLeft: 16,
                fontSize: 12,
                fontWeight: 400,
                color: 'rgba(255, 255, 255, 0.35)',
              }}
            >
              tap or press Esc to close
            </span>
          </div>
        )}

        {/* Photo + caption stack. Each photo gets its own AnimatePresence
            entry so the crossfade is between two real DOM nodes. */}
        <AnimatePresence>
          {current && (
            <motion.div
              key={`${photoIndex}-${current.photo_url}`}
              initial={{ opacity: 0, scale: 1.0 }}
              animate={{ opacity: 1, scale: 1.06 }}
              exit={{ opacity: 0 }}
              transition={{
                opacity: { duration: FADE_MS / 1000 },
                // Ken-Burns: slow scale ramp over the entire dwell time.
                scale: {
                  duration: (PHOTO_DURATION_MS + FADE_MS) / 1000,
                  ease: 'linear',
                },
              }}
              style={{
                position: 'absolute',
                inset: 0,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <img
                src={current.photo_url}
                alt=""
                style={{
                  maxWidth: '100%',
                  maxHeight: '100%',
                  objectFit: 'contain',
                  willChange: 'transform',
                }}
              />

              {current.caption && (
                <CaptionBlock caption={current.caption} />
              )}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Empty / loading state. */}
        {!current && (
          <div
            style={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'rgba(255, 255, 255, 0.5)',
              fontSize: 18,
              letterSpacing: '0.05em',
            }}
          >
            {manifest && manifest.photos.length === 0
              ? 'Yaadein abhi taiyaar nahi hain.'
              : 'Loading memories...'}
          </div>
        )}

        {/* Index dots — small but useful so the user knows where they
            are in the sequence. Pointer-events none so they don't
            interfere with the click-to-dismiss layer. */}
        {photos.length > 1 && (
          <div
            style={{
              position: 'absolute',
              top: 24,
              right: 32,
              zIndex: 3,
              color: 'rgba(255, 255, 255, 0.45)',
              fontSize: 14,
              fontWeight: 500,
              letterSpacing: '0.06em',
              pointerEvents: 'none',
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            {photoIndex + 1} / {photos.length}
          </div>
        )}
      </motion.div>
    </AnimatePresence>
  )
}

// ─── Caption block ────────────────────────────────────────────────────

interface CaptionBlockProps {
  caption: string
}

/**
 * The caption pad — soft transparent-to-dark gradient covering the
 * bottom third, with the caption text laid on top. Project_ag's
 * version was a fixed-alpha grey backdrop; this version is gradient
 * so the photo edge bleeds through naturally. The font size is
 * deliberately large: kiosk viewing distance is 2-3 ft, and short
 * lines of caption text get lost otherwise.
 */
function CaptionBlock({ caption }: CaptionBlockProps): React.ReactElement {
  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.6, delay: 0.2 }}
      style={{
        position: 'absolute',
        left: 0,
        right: 0,
        bottom: 0,
        // Gradient pad — transparent at top, near-opaque at the bottom
        // edge so the caption is always readable regardless of photo
        // contrast. Height scales with viewport so it works on
        // 1080p kiosks AND a 5.5" tablet.
        background:
          'linear-gradient(to top, rgba(0,0,0,0.85) 0%, rgba(0,0,0,0.55) 60%, rgba(0,0,0,0) 100%)',
        padding: '120px 8% 56px 8%',
        textAlign: 'center',
        pointerEvents: 'none',
      }}
    >
      <p
        style={{
          color: '#ffffff',
          fontSize: 'clamp(20px, 2.4vw, 32px)',
          fontWeight: 600,
          lineHeight: 1.45,
          margin: 0,
          textShadow: '0 2px 8px rgba(0, 0, 0, 0.6)',
          letterSpacing: '0.01em',
        }}
      >
        {caption}
      </p>
    </motion.div>
  )
}
