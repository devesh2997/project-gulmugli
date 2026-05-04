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

import type { TokenTree, TokenValue } from '../types/assistant'

interface TokenContextValue {
  tokens: TokenTree
  /**
   * Read a token by dot-notation path. Returns `unknown` because the
   * caller knows what the leaf type should be (color hex string,
   * pixel size string, animation duration etc.) — make them narrow
   * at the call site.
   */
  getToken: (path: string) => TokenValue | undefined
  updateToken: (path: string, value: TokenValue) => void
  currentPersonality: string
  setPersonality: (id: string) => void
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

/**
 * Walk a nested token tree using dot-notation path.
 * Returns `undefined` for any missing segment.
 */
function getNestedValue(obj: TokenTree, path: string): TokenValue | undefined {
  let current: TokenValue | undefined = obj
  for (const key of path.split('.')) {
    if (current == null || typeof current !== 'object') return undefined
    current = (current as TokenTree)[key]
  }
  return current
}

/**
 * Deep-set a value at a dot-notation path on a cloned copy of `obj`.
 * Creates intermediate objects as needed.
 */
function setNestedValue(
  obj: TokenTree,
  path: string,
  value: TokenValue,
): TokenTree {
  const clone = structuredClone(obj) as TokenTree
  const keys = path.split('.')
  let cursor: TokenTree = clone

  for (let i = 0; i < keys.length - 1; i++) {
    const key = keys[i]
    const next = cursor[key]
    if (next == null || typeof next !== 'object') {
      cursor[key] = {}
    }
    cursor = cursor[key] as TokenTree
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
  obj: Record<string, TokenValue>,
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

function syncCSSVars(tokens: TokenTree): void {
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
    accent:          '#e8c070', // warm gold — rich and alive
    glow_color:      '#e8c07035',
    background_tint: '#12110e', // nearly invisible warm tint
    glow_soft:       '#d4a86040', // warm golden ambient glow
  },
  devesh: {
    accent:          '#5cd8b8', // vivid teal — POPS against dark bg
    glow_color:      '#5cd8b835',
    background_tint: '#0e1210', // barely visible green
    glow_soft:       '#5cd8b840', // vibrant teal glow
  },
  girlfriend: {
    accent:          '#f0a0a8', // soft but bright pink-rose
    glow_color:      '#f0a0a835',
    background_tint: '#120e0e', // barely visible warmth
    glow_soft:       '#f0a0a840', // warm rose ambient glow
  },
  chandler: {
    accent:          '#c8a8f0', // bright lavender — clearly visible
    glow_color:      '#c8a8f035',
    background_tint: '#100e14', // barely visible violet
    glow_soft:       '#c8a8f040', // vivid purple glow
  },
}

/**
 * Merge warm palette overrides onto a personality's base JSON data.
 * Preserves avatarType, mood_default, tint from the JSON but replaces
 * accent and glow_color with warm values, and adds new warm-specific tokens.
 */
function applyWarmPalette(
  baseData: TokenTree,
  personalityId: string,
): TokenTree {
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

// Type-guard helper: a personality JSON entry is shaped like a TokenTree
// (string-keyed nested object with primitive leaves).
function asTokenTree(v: unknown): TokenTree {
  return (typeof v === 'object' && v !== null) ? (v as TokenTree) : {}
}

function buildInitialTokens(): TokenTree {
  const personalitiesAsTree = personalitiesTokens as Record<string, TokenTree>
  const basePersonality = personalitiesAsTree[DEFAULT_PERSONALITY] ?? {}
  const warmPersonality = applyWarmPalette(basePersonality, DEFAULT_PERSONALITY)

  let tokens: TokenTree = {
    animation: asTokenTree(animationTokens),
    layout: asTokenTree(layoutTokens),
    time: asTokenTree(timeTokens),
    ui: {
      ...asTokenTree(uiTokens),
      backgroundMode: 'gradient', // default background mode: "gradient" | "texture" | "glass"
    },
    personality: warmPersonality,
  }

  // Restore persisted token overrides (colors, timing tweaks, etc.)
  try {
    const saved = localStorage.getItem(TOKEN_OVERRIDES_KEY)
    if (saved) {
      const overrides = JSON.parse(saved) as Record<string, TokenValue>
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
  const [tokens, setTokens] = useState<TokenTree>(buildInitialTokens)
  const [currentPersonality, setCurrentPersonality] = useState(DEFAULT_PERSONALITY)

  // Sync CSS vars whenever tokens change
  useEffect(() => {
    syncCSSVars(tokens)
  }, [tokens])

  // `getToken` should be stable across renders (consumers memoize by it),
  // but its return value must reflect the LATEST tokens. The previous
  // implementation wrote to a ref during render — an anti-pattern that
  // can return stale values under React 19's concurrent rendering. Use
  // an effect to keep the ref in sync with the committed tokens, and
  // make getToken stable via empty-deps useCallback.
  const tokensRef = React.useRef(tokens)
  React.useEffect(() => { tokensRef.current = tokens }, [tokens])

  const getToken = useCallback(
    (path: string) => getNestedValue(tokensRef.current, path),
    [],
  )

  const updateToken = useCallback((path: string, value: TokenValue) => {
    setTokens((prev) => setNestedValue(prev, path, value))

    // Persist override so it survives page refreshes
    try {
      const saved = JSON.parse(localStorage.getItem(TOKEN_OVERRIDES_KEY) || '{}') as Record<string, TokenValue>
      saved[path] = value
      localStorage.setItem(TOKEN_OVERRIDES_KEY, JSON.stringify(saved))
    } catch { /* quota exceeded or private mode — ignore */ }
  }, [])

  const setPersonality = useCallback((id: string) => {
    const personalitiesAsTree = personalitiesTokens as Record<string, TokenTree>
    const personalityData = personalitiesAsTree[id]
    if (!personalityData) {
      console.warn(`[TokenProvider] Unknown personality id: "${id}"`)
      return
    }

    setCurrentPersonality(id)
    setTokens((prev) => {
      let next = structuredClone(prev) as TokenTree
      // Replace personality block with the new personality's data + warm palette.
      next.personality = applyWarmPalette(personalityData, id)

      // Re-apply any persisted token overrides on top, so user-chosen values
      // (e.g. a custom avatarType, accent override) survive personality switches.
      try {
        const saved = localStorage.getItem(TOKEN_OVERRIDES_KEY)
        if (saved) {
          const overrides = JSON.parse(saved) as Record<string, TokenValue>
          for (const [path, value] of Object.entries(overrides)) {
            next = setNestedValue(next, path, value)
          }
        }
      } catch {
        // Corrupted localStorage — ignore
      }

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
