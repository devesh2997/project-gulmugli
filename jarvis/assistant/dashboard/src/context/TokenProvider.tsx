/**
 * TokenProvider — runtime token store with CSS variable sync.
 *
 * Loads all design tokens at startup, exposes them via context, and keeps
 * CSS custom properties on :root in sync whenever tokens change.
 *
 * The `updateToken` function is the WebSocket runtime API: when the Python
 * backend sends a `token_update` message, App.tsx reads `updateToken` from
 * `useTokens()` and passes it to `useAssistant` as a callback.
 */

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react'

import animationTokens from '../tokens/animation.json'
import layoutTokens from '../tokens/layout.json'
import personalitiesTokens from '../tokens/personalities.json'
import timeTokens from '../tokens/time.json'
import uiTokens from '../tokens/ui.json'

// ─── Types ────────────────────────────────────────────────────────────────────

interface TokenContextValue {
  tokens: Record<string, any>
  getToken: (path: string) => any
  updateToken: (path: string, value: any) => void
  currentPersonality: string
  setPersonality: (id: string) => void
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

/**
 * Walk a nested object using dot-notation path.
 * Returns `undefined` for any missing segment.
 */
function getNestedValue(obj: Record<string, any>, path: string): any {
  return path.split('.').reduce<any>((current, key) => {
    if (current == null || typeof current !== 'object') return undefined
    return current[key]
  }, obj)
}

/**
 * Deep-set a value at a dot-notation path on a cloned copy of `obj`.
 * Creates intermediate objects as needed.
 */
function setNestedValue(
  obj: Record<string, any>,
  path: string,
  value: any,
): Record<string, any> {
  const clone = structuredClone(obj)
  const keys = path.split('.')
  let cursor: Record<string, any> = clone

  for (let i = 0; i < keys.length - 1; i++) {
    const key = keys[i]
    if (cursor[key] == null || typeof cursor[key] !== 'object') {
      cursor[key] = {}
    }
    cursor = cursor[key]
  }

  cursor[keys[keys.length - 1]] = value
  return clone
}

/**
 * Flatten a nested object to CSS custom property format.
 * Only leaf values (string | number | boolean) are emitted.
 *
 * Example: `{ animation: { orb: { breathe_duration: "4s" } } }`
 *   → `"--animation-orb-breathe_duration"` (underscores preserved, dots → dashes)
 *
 * Convention: dots become dashes, underscores stay as-is so token names are
 * predictable (animation.orb.breathe_duration → --animation-orb-breathe_duration).
 */
function flattenToCSSVars(
  obj: Record<string, any>,
  prefix = '',
): Array<[string, string]> {
  const result: Array<[string, string]> = []

  for (const [key, value] of Object.entries(obj)) {
    const segment = prefix ? `${prefix}-${key}` : key

    if (value === null || value === undefined) continue

    if (typeof value === 'object' && !Array.isArray(value)) {
      result.push(...flattenToCSSVars(value, segment))
    } else if (
      typeof value === 'string' ||
      typeof value === 'number' ||
      typeof value === 'boolean'
    ) {
      result.push([`--${segment}`, String(value)])
    }
    // Arrays are skipped (e.g. animation.orb.scale_range)
  }

  return result
}

/**
 * Apply all CSS custom properties to :root.
 */
/**
 * Parse a hex color to "r, g, b" string for use with rgba().
 * Returns null for non-hex values.
 */
function hexToRgbString(hex: string): string | null {
  if (typeof hex !== 'string' || !hex.startsWith('#')) return null
  const clean = hex.replace('#', '').slice(0, 6) // strip alpha suffix if present
  if (clean.length < 6) return null
  const n = parseInt(clean, 16)
  if (isNaN(n)) return null
  return `${(n >> 16) & 0xff}, ${(n >> 8) & 0xff}, ${n & 0xff}`
}

function syncCSSVars(tokens: Record<string, any>): void {
  const vars = flattenToCSSVars(tokens)
  const root = document.documentElement.style
  for (const [property, value] of vars) {
    root.setProperty(property, value)
    // Auto-generate -rgb variant for hex colors so components can use rgba()
    // e.g. --personality-accent: #c99568 → --personality-accent-rgb: 201, 149, 104
    const rgb = hexToRgbString(value)
    if (rgb) {
      root.setProperty(`${property}-rgb`, rgb)
    }
  }
}

// ─── Warm personality palettes ────────────────────────────────────────────────
// Override the neon/cyan accents from personalities.json with warm, personal tones.
// Each palette defines: accent (primary UI colour), glow_color (ambient background
// tint with alpha), background_tint (warm base for Canvas backgrounds), and
// glow_soft (subtle ambient light colour).

interface WarmPalette {
  accent: string
  glow_color: string
  background_tint: string
  glow_soft: string
}

const WARM_PERSONALITY_PALETTES: Record<string, WarmPalette> = {
  jarvis: {
    accent:          '#e0b87a', // warm gold — bright enough to pop
    glow_color:      '#e0b87a30',
    background_tint: '#1e1c18', // very subtle warm tint
    glow_soft:       '#d4a06835', // soft golden glow
  },
  devesh: {
    accent:          '#6ec2aa', // fresh teal — vibrant but not neon
    glow_color:      '#6ec2aa30',
    background_tint: '#181e1c', // barely-there green tint
    glow_soft:       '#6ec2aa35', // fresh teal glow
  },
  girlfriend: {
    accent:          '#e8a0a0', // soft warm pink — visible, not muddy
    glow_color:      '#e8a0a030',
    background_tint: '#1e1818', // very subtle rose warmth
    glow_soft:       '#e8a0a035', // gentle rose glow
  },
  chandler: {
    accent:          '#b89fd8', // clear lavender — readable
    glow_color:      '#b89fd830',
    background_tint: '#1a181e', // barely-there violet
    glow_soft:       '#b89fd835', // soft purple glow
  },
}

/**
 * Merge warm palette overrides onto a personality's base JSON data.
 * Preserves avatarType, mood_default, tint from the JSON but replaces
 * accent and glow_color with warm values, and adds new warm-specific tokens.
 */
function applyWarmPalette(
  baseData: Record<string, any>,
  personalityId: string,
): Record<string, any> {
  const warm = WARM_PERSONALITY_PALETTES[personalityId]
  if (!warm) return baseData
  return {
    ...baseData,
    accent:          warm.accent,
    glow_color:      warm.glow_color,
    background_tint: warm.background_tint,
    glow_soft:       warm.glow_soft,
  }
}

// ─── Initial token state ──────────────────────────────────────────────────────

const DEFAULT_PERSONALITY = 'jarvis'
const TOKEN_OVERRIDES_KEY = 'jarvis-token-overrides'

function buildInitialTokens(): Record<string, any> {
  const basePersonality = (personalitiesTokens as Record<string, any>)[DEFAULT_PERSONALITY] ?? {}
  const warmPersonality = applyWarmPalette(basePersonality, DEFAULT_PERSONALITY)

  let tokens: Record<string, any> = {
    animation: animationTokens,
    layout: layoutTokens,
    time: timeTokens,
    ui: {
      ...uiTokens,
      backgroundMode: 'gradient', // default background mode: "gradient" | "texture" | "glass"
    },
    personality: warmPersonality,
  }

  // Restore persisted token overrides (colors, timing tweaks, etc.)
  try {
    const saved = localStorage.getItem(TOKEN_OVERRIDES_KEY)
    if (saved) {
      const overrides: Record<string, any> = JSON.parse(saved)
      for (const [path, value] of Object.entries(overrides)) {
        tokens = setNestedValue(tokens, path, value)
      }
    }
  } catch {
    // Corrupted localStorage — ignore
  }

  return tokens
}

// ─── Context ──────────────────────────────────────────────────────────────────

const TokenContext = createContext<TokenContextValue | null>(null)

// ─── Provider ─────────────────────────────────────────────────────────────────

export function TokenProvider({ children }: { children: React.ReactNode }) {
  const [tokens, setTokens] = useState<Record<string, any>>(buildInitialTokens)
  const [currentPersonality, setCurrentPersonality] = useState(DEFAULT_PERSONALITY)

  // Sync CSS vars whenever tokens change
  useEffect(() => {
    syncCSSVars(tokens)
  }, [tokens])

  // Use a ref so getToken always reads current tokens without causing re-renders
  const tokensRef = React.useRef(tokens)
  tokensRef.current = tokens

  const getToken = useCallback(
    (path: string) => getNestedValue(tokensRef.current, path),
    [],
  )

  const updateToken = useCallback((path: string, value: any) => {
    setTokens((prev) => setNestedValue(prev, path, value))

    // Persist override so it survives page refreshes
    try {
      const saved = JSON.parse(localStorage.getItem(TOKEN_OVERRIDES_KEY) || '{}')
      saved[path] = value
      localStorage.setItem(TOKEN_OVERRIDES_KEY, JSON.stringify(saved))
    } catch { /* quota exceeded or private mode — ignore */ }
  }, [])

  const setPersonality = useCallback((id: string) => {
    const personalityData = (personalitiesTokens as Record<string, any>)[id]
    if (!personalityData) {
      console.warn(`[TokenProvider] Unknown personality id: "${id}"`)
      return
    }

    setCurrentPersonality(id)
    setTokens((prev) => {
      const next = structuredClone(prev)
      // Merge personality tokens under the `personality` key,
      // applying warm palette overrides for the new personality.
      next.personality = applyWarmPalette(personalityData, id)
      return next
    })
  }, [])

  const value = useMemo<TokenContextValue>(
    () => ({ tokens, getToken, updateToken, currentPersonality, setPersonality }),
    [tokens, getToken, updateToken, currentPersonality, setPersonality],
  )

  return <TokenContext.Provider value={value}>{children}</TokenContext.Provider>
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function useTokens(): TokenContextValue {
  const ctx = useContext(TokenContext)
  if (ctx === null) {
    throw new Error('useTokens() must be called inside <TokenProvider>')
  }
  return ctx
}
