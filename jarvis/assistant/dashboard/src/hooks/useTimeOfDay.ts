/**
 * useTimeOfDay — adaptive palette interpolation based on current time.
 *
 * Reads the three palettes from time.json (via TokenProvider), determines
 * which two to blend based on the current hour, calculates a linear `t`
 * (0-1) within the 1-hour transition window around each boundary, and
 * writes interpolated values to `time.current.*` tokens every 60 seconds.
 *
 * Transitions:
 *   morning → afternoon: window 11:00–13:00 (boundary at 12)
 *   afternoon → night:   window 20:00–22:00 (boundary at 21)
 *   night → morning:     window 05:00–07:00 (boundary at 6, crosses midnight)
 *
 * Outside transition windows the palette is constant — t is clamped to 0 or 1.
 *
 * Call once at the app root level (inside <TokenProvider>). The hook fires
 * immediately on mount so the palette is correct before the first render.
 */

import { useEffect } from 'react'
import { useTokens } from '../context/TokenProvider'

// ─── Types ────────────────────────────────────────────────────────────────────

interface TimePalette {
  canvas_gradient_start: string
  canvas_gradient_end: string
  accent_primary: string
  accent_glow: string
  text_primary_opacity: number
  orb_breathe_duration: string
}

// ─── Colour helpers ───────────────────────────────────────────────────────────

/** Parse a 6-digit hex string (with or without #) to [r, g, b] 0-255. */
function hexToRgb(hex: string): [number, number, number] {
  const clean = hex.replace('#', '')
  const n = parseInt(clean, 16)
  return [(n >> 16) & 0xff, (n >> 8) & 0xff, n & 0xff]
}

/** Convert [r, g, b] 0-255 back to a lowercase hex string like "#0d2a2a". */
function rgbToHex(r: number, g: number, b: number): string {
  const clamp = (v: number) => Math.max(0, Math.min(255, Math.round(v)))
  return '#' + [r, g, b].map((c) => clamp(c).toString(16).padStart(2, '0')).join('')
}

/** Linearly interpolate two hex colours. t=0 → a, t=1 → b. */
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
  }
}

// ─── Time logic ───────────────────────────────────────────────────────────────

/**
 * The three named boundaries and their 1-hour transition windows.
 * Each entry describes: which palette transitions into which, and the hour
 * range [start, end] of the full 2-hour window centred on the boundary.
 *
 *   morning→afternoon: boundary 12:00, window [11, 13]
 *   afternoon→night:   boundary 21:00, window [20, 22]
 *   night→morning:     boundary 06:00, window [05, 07]  (crosses midnight)
 */
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
 *
 * t=0 → entirely `from` palette
 * t=1 → entirely `to` palette
 */
function computeBlend(fractionalHour: number): BlendResult {
  for (const { from, to, windowStart, windowEnd } of TRANSITIONS) {
    // Handle midnight wrapping: night→morning window spans ~05–07 which is
    // entirely inside 0-24 so no special case, but windowEnd > windowStart
    // is always true for these specific values — safe to compare directly.
    if (fractionalHour >= windowStart && fractionalHour <= windowEnd) {
      const t = (fractionalHour - windowStart) / (windowEnd - windowStart)
      return { fromName: from, toName: to, t }
    }
  }

  // Outside all transition windows — determine current steady-state palette.
  // Boundaries (holding periods):
  //   morning:   [07, 11)   — after night→morning finishes, before morning→afternoon starts
  //   afternoon: [13, 20)   — after morning→afternoon finishes, before afternoon→night starts
  //   night:     [22, 29)   — after afternoon→night finishes; wraps via %24 to [22,24) ∪ [0,5)
  let steady: PaletteName
  const h = fractionalHour
  if (h >= 7 && h < 11) {
    steady = 'morning'
  } else if (h >= 13 && h < 20) {
    steady = 'afternoon'
  } else {
    // [22, 24) ∪ [0, 5) — night
    steady = 'night'
  }

  return { fromName: steady, toName: steady, t: 0 }
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function useTimeOfDay(): void {
  const { getToken, updateToken } = useTokens()

  useEffect(() => {
    function update() {
      // Read all three palettes from the token store (they live at time.morning, etc.)
      const morning   = getToken('time.morning')   as TimePalette | undefined
      const afternoon = getToken('time.afternoon') as TimePalette | undefined
      const night     = getToken('time.night')     as TimePalette | undefined

      if (!morning || !afternoon || !night) {
        console.warn('[useTimeOfDay] time.* tokens not found — TokenProvider not ready?')
        return
      }

      const palettes: Record<PaletteName, TimePalette> = { morning, afternoon, night }

      const now = new Date()
      const fractionalHour = now.getHours() + now.getMinutes() / 60 + now.getSeconds() / 3600

      const { fromName, toName, t } = computeBlend(fractionalHour)
      const interpolated = lerpPalettes(palettes[fromName], palettes[toName], t)

      // Push each property into the token store under `time.current.*`
      // TokenProvider syncs these to CSS vars automatically as `--time-current-<property>`
      for (const [key, value] of Object.entries(interpolated)) {
        updateToken(`time.current.${key}`, value)
      }
    }

    // Run immediately on mount — don't wait 60 seconds for the first frame.
    update()

    const intervalId = setInterval(update, 60_000)
    return () => clearInterval(intervalId)
  }, [getToken, updateToken])
}
