/**
 * Canvas -- full-screen background layer with three switchable modes.
 *
 * Reads `--ui-backgroundMode` from CSS vars to determine which mode to render:
 *
 *   "gradient" (default) -- Soft warm gradient that shifts with time-of-day.
 *       Morning: peach/cream, Afternoon: golden/amber, Night: deep navy/indigo.
 *       Personality colour bleeds through as a centred radial tint.
 *
 *   "texture" -- Animated CSS-only texture (layered gradients + SVG noise filter).
 *       Simulates a soft fabric/watercolour feel. Personality colour appears as
 *       ambient highlights through the grain.
 *
 *   "glass" -- Frosted glass effect with warm undertones. The personality colour
 *       shows as an ambient backlight behind a frosted/blurred layer.
 *
 * All three modes:
 *   - Use the time-interpolated gradient as their base warmth
 *   - Layer the personality accent colour as an ambient tint
 *   - Transition smoothly between modes via CSS transitions
 *   - Never use pure black (#000000) or near-black
 *
 * Sits at z-index 0 so every other UI element renders above it.
 * No props -- reads everything from CSS vars set by TokenProvider + useTimeOfDay.
 */

import { useEffect, useState } from 'react'

type BackgroundMode = 'gradient' | 'texture' | 'glass'

/** Read the current background mode from the CSS variable on :root. */
function readMode(): BackgroundMode {
  if (typeof document === 'undefined') return 'gradient'
  const val = getComputedStyle(document.documentElement)
    .getPropertyValue('--ui-backgroundMode')
    .trim()
  if (val === 'texture' || val === 'glass') return val
  return 'gradient'
}

// ---- Shared base style (all modes) -----------------------------------------

const baseStyle: React.CSSProperties = {
  position: 'fixed',
  inset: 0,
  zIndex: 0,
  transition: 'background 1.2s ease, filter 1.2s ease',
}

// ---- SVG noise filter (embedded once, used by texture mode) ----------------

function NoiseFilter() {
  return (
    <svg style={{ position: 'absolute', width: 0, height: 0 }} aria-hidden="true">
      <defs>
        <filter id="canvas-noise" x="0%" y="0%" width="100%" height="100%">
          <feTurbulence
            type="fractalNoise"
            baseFrequency="0.65"
            numOctaves="4"
            stitchTiles="stitch"
            result="noise"
          />
          <feColorMatrix
            type="saturate"
            values="0"
            in="noise"
            result="gray-noise"
          />
          <feBlend in="SourceGraphic" in2="gray-noise" mode="soft-light" />
        </filter>
      </defs>
    </svg>
  )
}

// ---- Gradient mode ---------------------------------------------------------

function GradientBackground() {
  return (
    <div
      style={{
        ...baseStyle,
        background: [
          'linear-gradient(160deg, var(--time-current-canvas_gradient_start), var(--time-current-canvas_gradient_end))',
        ].join(', '),
      }}
    >
      {/* Personality ambient tint -- centred warm radial, generous glow */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background: 'radial-gradient(ellipse at 50% 45%, rgba(var(--personality-accent-rgb), 0.18) 0%, transparent 65%)',
          transition: 'background 1.2s ease',
        }}
      />
      {/* Secondary warmth layer -- bottom edge glow */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background: 'radial-gradient(ellipse at 50% 100%, rgba(var(--personality-accent-rgb), 0.1) 0%, transparent 45%)',
          transition: 'background 1.2s ease',
        }}
      />
      {/* Top-left subtle ambient wash for depth */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background: 'radial-gradient(ellipse at 20% 20%, rgba(var(--personality-accent-rgb), 0.06) 0%, transparent 50%)',
          transition: 'background 1.2s ease',
        }}
      />
    </div>
  )
}

// ---- Texture mode ----------------------------------------------------------

function TextureBackground() {
  return (
    <div
      style={{
        ...baseStyle,
        background: [
          // Layer 1: base warm gradient (time-shifted)
          'linear-gradient(160deg, var(--time-current-canvas_gradient_start), var(--time-current-canvas_gradient_end))',
        ].join(', '),
      }}
    >
      <NoiseFilter />

      {/* Personality colour wash -- soft, diffused */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background: [
            'radial-gradient(ellipse at 30% 20%, rgba(var(--personality-accent-rgb), 0.12) 0%, transparent 60%)',
            'radial-gradient(ellipse at 70% 80%, rgba(var(--personality-accent-rgb), 0.08) 0%, transparent 50%)',
          ].join(', '),
          transition: 'background 1.2s ease',
        }}
      />

      {/* Animated grain overlay -- CSS-only noise via SVG filter */}
      <div
        style={{
          position: 'absolute',
          inset: '-50%',
          width: '200%',
          height: '200%',
          background: 'transparent',
          filter: 'url(#canvas-noise)',
          opacity: 0.04,
          animation: 'canvas-grain-drift 20s linear infinite',
          pointerEvents: 'none',
        }}
      />

      {/* Soft watercolour blobs -- layered radial gradients that drift */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background: [
            'radial-gradient(ellipse at 20% 40%, rgba(var(--personality-accent-rgb), 0.07) 0%, transparent 45%)',
            'radial-gradient(ellipse at 80% 30%, rgba(var(--time-current-accent_glow-rgb, var(--personality-accent-rgb)), 0.05) 0%, transparent 40%)',
            'radial-gradient(ellipse at 50% 90%, rgba(var(--personality-accent-rgb), 0.06) 0%, transparent 50%)',
          ].join(', '),
          animation: 'canvas-watercolour-shift 30s ease-in-out infinite alternate',
          transition: 'background 1.2s ease',
        }}
      />

      {/* Inject keyframes */}
      <style>{`
        @keyframes canvas-grain-drift {
          0% { transform: translate(0, 0); }
          100% { transform: translate(-10%, -10%); }
        }
        @keyframes canvas-watercolour-shift {
          0% { opacity: 1; transform: scale(1) translate(0, 0); }
          50% { opacity: 0.8; transform: scale(1.05) translate(1%, -1%); }
          100% { opacity: 1; transform: scale(1) translate(-1%, 1%); }
        }
      `}</style>
    </div>
  )
}

// ---- Glass mode ------------------------------------------------------------

function GlassBackground() {
  return (
    <div
      style={{
        ...baseStyle,
        background: [
          'linear-gradient(160deg, var(--time-current-canvas_gradient_start), var(--time-current-canvas_gradient_end))',
        ].join(', '),
      }}
    >
      {/* Backlight layer -- personality colour as a large ambient glow behind glass */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background: [
            'radial-gradient(ellipse at 50% 40%, rgba(var(--personality-accent-rgb), 0.18) 0%, transparent 60%)',
            'radial-gradient(ellipse at 50% 100%, rgba(var(--personality-accent-rgb), 0.1) 0%, transparent 40%)',
          ].join(', '),
          transition: 'background 1.2s ease',
        }}
      />

      {/* Frosted glass layer */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          backdropFilter: 'blur(60px) saturate(1.3)',
          WebkitBackdropFilter: 'blur(60px) saturate(1.3)',
          background: 'rgba(var(--personality-accent-rgb), 0.04)',
          transition: 'background 1.2s ease, backdrop-filter 1.2s ease',
        }}
      />

      {/* Subtle warm overlay to prevent the glass from feeling cold */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background: 'linear-gradient(180deg, rgba(180, 140, 100, 0.03) 0%, rgba(140, 100, 80, 0.02) 100%)',
          pointerEvents: 'none',
        }}
      />
    </div>
  )
}

// ---- Main export -----------------------------------------------------------

export function Canvas() {
  const [mode, setMode] = useState<BackgroundMode>(readMode)

  // Watch for backgroundMode token changes via MutationObserver on :root style
  useEffect(() => {
    const check = () => {
      const newMode = readMode()
      setMode((prev) => (prev !== newMode ? newMode : prev))
    }

    // Poll on a modest interval since CSS var changes from TokenProvider
    // don't trigger MutationObserver reliably across all browsers.
    const id = setInterval(check, 500)
    return () => clearInterval(id)
  }, [])

  switch (mode) {
    case 'texture':
      return <TextureBackground />
    case 'glass':
      return <GlassBackground />
    case 'gradient':
    default:
      return <GradientBackground />
  }
}
