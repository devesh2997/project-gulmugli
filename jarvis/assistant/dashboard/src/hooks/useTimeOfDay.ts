/**
 * useTimeOfDay — adaptive palette interpolation based on current time.
 *
 * Reads the three palettes from time.json (via TokenProvider), determines
 * which two to blend based on the current hour, calculates a linear `t`
 * (0-1) within the 1-hour transition window around each boundary, and
 * writes interpolated values to `time.current.*` tokens every 60 seconds.
 *
 * Warm palette overrides: The base time palettes from time.json are
 * overridden here with warm tones (peach mornings, golden afternoons,
 * deep navy nights) before interpolation. This keeps the JSON file as
 * the structural source of truth while the hook owns the actual colours.
 *
 * Transitions:
 *   morning -> afternoon: window 11:00-13:00 (boundary at 12)
 *   afternoon -> night:   window 20:00-22:00 (boundary at 21)
 *   night -> morning:     window 05:00-07:00 (boundary at 6, crosses midnight)
 *
 * Outside transition windows the palette is constant -- t is clamped to 0 or 1.
 *
 * Call once at the app root level (inside <TokenProvider>). The hook fires
 * immediately on mount so the palette is correct before the first render.
 */

import { useEffect, useRef } from 'react'
import { useTokens } from '../context/TokenProvider'

// -- Types -------------------------------------------------------------------

interface TimePalette {
  canvas_gradient_start: string
  canvas_gradient_end: string
  accent_primary: string
  accent_glow: string
  text_primary_opacity: number
  orb_breathe_duration: string
  brightness: number
}

// -- Warm palette overrides --------------------------------------------------
// These replace the dark/neon values from time.json with warm, inviting tones.
// NO pure black anywhere.

const WARM_PALETTES: Record<PaletteName, TimePalette> = {
  morning: {
    canvas_gradient_start: '#2c2824', // warm medium grey — noticeably lighter than night
    canvas_gradient_end:   '#35302a', // warm taupe
    accent_primary:        '#e8c4a0', // soft warm cream
    accent_glow:           '#d4a878', // muted gold
    text_primary_opacity:  0.85,
    orb_breathe_duration:  '4s',
    brightness:            0.85,
  },
  afternoon: {
    canvas_gradient_start: '#363230', // warm grey — the BRIGHTEST mode
    canvas_gradient_end:   '#3e3a36', // light warm charcoal
    accent_primary:        '#c9a87c', // warm gold
    accent_glow:           '#b89468', // amber
    text_primary_opacity:  0.9,
    orb_breathe_duration:  '4s',
    brightness:            1.0,
  },
  night: {
    canvas_gradient_start: '#121420', // deep midnight blue — the DARKEST mode
    canvas_gradient_end:   '#181a28', // dark slate with blue undertone
    accent_primary:        '#8b7db5', // muted lavender
    accent_glow:           '#6b5d99', // deep purple
    text_primary_opacity:  0.5,
    orb_breathe_duration:  '6s',
    brightness:            0.4,
  },
}

// -- Colour helpers ----------------------------------------------------------

/** Parse a 6-digit hex string (with or without #) to [r, g, b] 0-255. */
function hexToRgb(hex: string): [number, number, number] {
  const clean = hex.replace('#', '')
  const n = parseInt(clean, 16)
  return [(n >> 16) & 0xff, (n >> 8) & 0xff, n & 0xff]
}

/** Convert [r, g, b] 0-255 back to a lowercase hex string like "#2d2118". */
function rgbToHex(r: number, g: number, b: number): string {
  const clamp = (v: number) => Math.max(0, Math.min(255, Math.round(v)))
  return '#' + [r, g, b].map((c) => clamp(c).toString(16).padStart(2, '0')).join('')
}

/** Linearly interpolate two hex colours. t=0 -> a, t=1 -> b. */
function lerpHex(a: string, b: string, t: number): string {
  const [ar, ag, ab] = hexToRgb(a)
  const [br, bg, bb] = hexToRgb(b)
  return rgbToHex(ar + (br - ar) * t, ag + (bg - ag) * t, ab + (bb - ab) * t)
}

/** Interpolate a CSS duration string like "4s" or "6s". Returns "Xs" format. */
function lerpDuration(a: string, b: string, t: number): string {
  const parseSeconds = (s: string) => parseFloat(s.replace(/[^0-9.]/g, ''))
  const unit = a.replace(/[0-9. ]/g, '') || 's'
  const va = parseSeconds(a)
  const vb = parseSeconds(b)
  return (va + (vb - va) * t).toFixed(2).replace(/\.?0+$/, '') + unit
}

/** Interpolate a single palette property generically. */
function lerpValue(a: unknown, b: unknown, t: number): unknown {
  if (typeof a === 'number' && typeof b === 'number') {
    return a + (b - a) * t
  }
  if (typeof a === 'string' && typeof b === 'string') {
    if (a.startsWith('#') && b.startsWith('#')) return lerpHex(a, b, t)
    // duration strings ("4s", "6s")
    if (/^[\d.]+[a-z]+$/i.test(a) && /^[\d.]+[a-z]+$/i.test(b)) return lerpDuration(a, b, t)
  }
  // Fallback: snap to b when t >= 0.5, else stay at a
  return t >= 0.5 ? b : a
}

/** Interpolate all properties between two palettes at position t. */
function lerpPalettes(from: TimePalette, to: TimePalette, t: number): TimePalette {
  return {
    canvas_gradient_start: lerpHex(from.canvas_gradient_start, to.canvas_gradient_start, t),
    canvas_gradient_end: lerpHex(from.canvas_gradient_end, to.canvas_gradient_end, t),
    accent_primary: lerpHex(from.accent_primary, to.accent_primary, t),
    accent_glow: lerpHex(from.accent_glow, to.accent_glow, t),
    text_primary_opacity: lerpValue(from.text_primary_opacity, to.text_primary_opacity, t) as number,
    orb_breathe_duration: lerpDuration(from.orb_breathe_duration, to.orb_breathe_duration, t),
    brightness: lerpValue(from.brightness, to.brightness, t) as number,
  }
}

// -- Time logic --------------------------------------------------------------

const TRANSITIONS = [
  { from: 'morning' as const,   to: 'afternoon' as const, windowStart: 11, windowEnd: 13 },
  { from: 'afternoon' as const, to: 'night' as const,     windowStart: 20, windowEnd: 22 },
  { from: 'night' as const,     to: 'morning' as const,   windowStart: 5,  windowEnd: 7  },
] as const

type PaletteName = 'morning' | 'afternoon' | 'night'

interface BlendResult {
  fromName: PaletteName
  toName: PaletteName
  t: number
}

/**
 * Given fractional hours (e.g. 14.5 = 14:30), determine which two palettes
 * to blend and return the interpolation factor t in [0, 1].
 */
function computeBlend(fractionalHour: number): BlendResult {
  for (const { from, to, windowStart, windowEnd } of TRANSITIONS) {
    if (fractionalHour >= windowStart && fractionalHour <= windowEnd) {
      const t = (fractionalHour - windowStart) / (windowEnd - windowStart)
      return { fromName: from, toName: to, t }
    }
  }

  let steady: PaletteName
  const h = fractionalHour
  if (h >= 7 && h < 11) {
    steady = 'morning'
  } else if (h >= 13 && h < 20) {
    steady = 'afternoon'
  } else {
    steady = 'night'
  }

  return { fromName: steady, toName: steady, t: 0 }
}

// -- Hook --------------------------------------------------------------------

/**
 * Expose a global testing API: window.__setSimulatedHour(14.5) sets 2:30pm.
 * Call window.__setSimulatedHour(null) to return to real time.
 */
let simulatedHour: number | null = null

if (typeof window !== 'undefined') {
  (window as any).__setSimulatedHour = (hour: number | null) => {
    simulatedHour = hour
    console.log(`[useTimeOfDay] Simulated hour: ${hour === null ? 'OFF (real time)' : hour}`)
    window.dispatchEvent(new CustomEvent('time-sim-change'))
  }
}

export function useTimeOfDay(): void {
  const { updateToken } = useTokens()

  const updateTokenRef = useRef(updateToken)
  updateTokenRef.current = updateToken

  useEffect(() => {
    function update() {
      // Use warm palette overrides instead of the JSON values
      const palettes = WARM_PALETTES

      let fractionalHour: number
      if (simulatedHour !== null) {
        fractionalHour = simulatedHour
      } else {
        const now = new Date()
        fractionalHour = now.getHours() + now.getMinutes() / 60 + now.getSeconds() / 3600
      }

      const { fromName, toName, t } = computeBlend(fractionalHour)
      const interpolated = lerpPalettes(palettes[fromName], palettes[toName], t)

      // Determine the current phase name for Canvas background mode
      let phase: PaletteName
      if (fromName === toName) {
        phase = fromName
      } else {
        phase = t >= 0.5 ? toName : fromName
      }

      // Check for manual brightness override (0-100). -1 or absent = auto (time-based).
      // This lets the user lighten or darken the background independently.
      const root = document.documentElement.style
      const overrideStr = getComputedStyle(document.documentElement)
        .getPropertyValue('--ui-brightness-override').trim()
      const override = overrideStr ? parseFloat(overrideStr) : -1

      let final = interpolated
      if (override >= 0 && override <= 100) {
        // Override brightness: 0 = darkest (night-like), 50 = current auto, 100 = brightest (afternoon-like)
        // We lerp the canvas gradient colours between the extremes
        const darkest = WARM_PALETTES.night
        const brightest = WARM_PALETTES.afternoon
        const factor = override / 100
        final = {
          ...interpolated,
          canvas_gradient_start: lerpHex(darkest.canvas_gradient_start, brightest.canvas_gradient_start, factor),
          canvas_gradient_end: lerpHex(darkest.canvas_gradient_end, brightest.canvas_gradient_end, factor),
          text_primary_opacity: darkest.text_primary_opacity + (brightest.text_primary_opacity - darkest.text_primary_opacity) * factor,
          brightness: darkest.brightness + (brightest.brightness - darkest.brightness) * factor,
        }
      }

      for (const [key, value] of Object.entries(final)) {
        root.setProperty(`--time-current-${key}`, String(value))
        if (typeof value === 'string' && value.startsWith('#')) {
          const clean = value.replace('#', '').slice(0, 6)
          const n = parseInt(clean, 16)
          if (!isNaN(n)) {
            root.setProperty(`--time-current-${key}-rgb`, `${(n >> 16) & 0xff}, ${(n >> 8) & 0xff}, ${n & 0xff}`)
          }
        }
      }

      // Expose the current phase and blend factor so Canvas can use them
      root.setProperty('--time-current-phase', phase)
      root.setProperty('--time-current-blend_t', String(t))
    }

    update()

    const intervalId = setInterval(update, 60_000)

    const onSimChange = () => update()
    window.addEventListener('time-sim-change', onSimChange)

    return () => {
      clearInterval(intervalId)
      window.removeEventListener('time-sim-change', onSimChange)
    }
  }, [])
}
