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
    canvas_gradient_start: '#0f0f12', // deep near-black with cool warmth
    canvas_gradient_end:   '#16141a', // slightly lighter, subtle depth
    accent_primary:        '#f0c896', // warm peach-gold — VIBRANT
    accent_glow:           '#e0a870', // rich amber glow
    text_primary_opacity:  0.85,
    orb_breathe_duration:  '4s',
    brightness:            0.85,
  },
  afternoon: {
    canvas_gradient_start: '#0e0e11', // deep charcoal — NOT grey, not brown
    canvas_gradient_end:   '#141218', // rich dark with subtle warmth
    accent_primary:        '#e8b880', // warm gold — bright and alive
    accent_glow:           '#d4a060', // rich golden glow
    text_primary_opacity:  0.9,
    orb_breathe_duration:  '4s',
    brightness:            1.0,
  },
  night: {
    canvas_gradient_start: '#08080e', // very deep blue-black
    canvas_gradient_end:   '#0e0e18', // midnight blue
    accent_primary:        '#9088c8', // soft lavender — still visible
    accent_glow:           '#6b60a0', // deep purple glow
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

      // Light mode palette — genuinely bright: warm cream/ivory backgrounds
      // Used when brightness override > 60
      const LIGHT_PALETTE: TimePalette = {
        canvas_gradient_start: '#e8e0d8', // warm cream
        canvas_gradient_end:   '#f0ebe4', // soft ivory
        accent_primary:        '#8a7060', // warm brown accent (for contrast on light bg)
        accent_glow:           '#a08870', // warm glow
        text_primary_opacity:  0.9,
        orb_breathe_duration:  '4s',
        brightness:            1.0,
      }

      let final = interpolated
      if (override >= 0 && override <= 100) {
        // 0-40: dark range (night → current auto darkness)
        // 40-60: auto range (close to time-based)
        // 60-100: light range (auto → genuinely bright cream/ivory)
        const factor = override / 100

        if (factor <= 0.4) {
          // Dark range: lerp from darkest night to current auto
          const t = factor / 0.4
          final = {
            ...interpolated,
            canvas_gradient_start: lerpHex(WARM_PALETTES.night.canvas_gradient_start, interpolated.canvas_gradient_start, t),
            canvas_gradient_end: lerpHex(WARM_PALETTES.night.canvas_gradient_end, interpolated.canvas_gradient_end, t),
            text_primary_opacity: WARM_PALETTES.night.text_primary_opacity + (interpolated.text_primary_opacity - WARM_PALETTES.night.text_primary_opacity) * t,
            brightness: WARM_PALETTES.night.brightness + (interpolated.brightness - WARM_PALETTES.night.brightness) * t,
          }
          root.setProperty('--ui-is-light-mode', '0')
        } else if (factor <= 0.6) {
          // Auto range: use current time-based palette as-is
          final = interpolated
          root.setProperty('--ui-is-light-mode', '0')
        } else {
          // LIGHT range: lerp from current auto to genuinely bright cream/ivory
          const t = (factor - 0.6) / 0.4
          final = {
            ...interpolated,
            canvas_gradient_start: lerpHex(interpolated.canvas_gradient_start, LIGHT_PALETTE.canvas_gradient_start, t),
            canvas_gradient_end: lerpHex(interpolated.canvas_gradient_end, LIGHT_PALETTE.canvas_gradient_end, t),
            text_primary_opacity: interpolated.text_primary_opacity + (LIGHT_PALETTE.text_primary_opacity - interpolated.text_primary_opacity) * t,
            brightness: interpolated.brightness + (LIGHT_PALETTE.brightness - interpolated.brightness) * t,
          }
          // On light backgrounds, we also need to flag that text should be dark
          // Set a CSS var that components can use to flip text colour
          root.setProperty('--ui-is-light-mode', t > 0.5 ? '1' : '0')
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

      // Global text colours that auto-flip for light/dark mode.
      // Components should use these instead of hard-coded rgba(255,255,255,...).
      const lightMode = getComputedStyle(document.documentElement)
        .getPropertyValue('--ui-is-light-mode').trim() === '1'
      root.setProperty('--text-primary', lightMode ? 'rgba(30, 20, 10, 0.85)' : 'rgba(255, 255, 255, 0.8)')
      root.setProperty('--text-secondary', lightMode ? 'rgba(30, 20, 10, 0.5)' : 'rgba(255, 255, 255, 0.4)')
      root.setProperty('--text-tertiary', lightMode ? 'rgba(30, 20, 10, 0.3)' : 'rgba(255, 255, 255, 0.2)')
      root.setProperty('--surface-subtle', lightMode ? 'rgba(0, 0, 0, 0.04)' : 'rgba(255, 255, 255, 0.04)')
      root.setProperty('--border-subtle', lightMode ? 'rgba(0, 0, 0, 0.08)' : 'rgba(255, 255, 255, 0.06)')
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
