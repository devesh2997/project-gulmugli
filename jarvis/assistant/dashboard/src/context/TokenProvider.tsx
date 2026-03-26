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
function syncCSSVars(tokens: Record<string, any>): void {
  const vars = flattenToCSSVars(tokens)
  for (const [property, value] of vars) {
    document.documentElement.style.setProperty(property, value)
  }
}

// ─── Initial token state ──────────────────────────────────────────────────────

const DEFAULT_PERSONALITY = 'jarvis'

function buildInitialTokens(): Record<string, any> {
  return {
    animation: animationTokens,
    layout: layoutTokens,
    time: timeTokens,
    ui: uiTokens,
    // Active personality tokens merged under `personality` key
    personality: (personalitiesTokens as Record<string, any>)[DEFAULT_PERSONALITY] ?? {},
  }
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

  const getToken = useCallback(
    (path: string) => getNestedValue(tokens, path),
    [tokens],
  )

  const updateToken = useCallback((path: string, value: any) => {
    setTokens((prev) => setNestedValue(prev, path, value))
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
      // Merge personality tokens under the `personality` key
      next.personality = personalityData

      // Also push accent + glow up to canvas-level CSS vars so components can
      // reference --personality-accent and --personality-glow_color directly
      // without knowing about nested paths.
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
