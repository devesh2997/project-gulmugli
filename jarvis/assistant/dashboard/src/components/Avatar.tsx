/**
 * Avatar — dispatches to the correct avatar component based on the active
 * personality's avatarType token.
 *
 * Avatar types are registered in AVATAR_REGISTRY. To add a new avatar:
 *   1. Create the component in src/components/avatars/AvatarMyType.tsx
 *   2. Import it here and add to AVATAR_REGISTRY
 *   3. Set avatarType: "mytype" in the personality's config
 *
 * Each personality can use any avatar type — they're decoupled.
 * The active avatarType can be changed at runtime via token update.
 */

import { AnimatePresence } from 'framer-motion'
import type { AssistantMood, AssistantState } from '../types/assistant'
import { useTokens } from '../context/TokenProvider'
import { AvatarOrb } from './avatars/AvatarOrb'
import { AvatarPixel } from './avatars/AvatarPixel'
import { AvatarLight } from './avatars/AvatarLight'
import { AvatarCaricature } from './avatars/AvatarCaricature'
import { AvatarCozmo } from './avatars/AvatarCozmo'

export interface AvatarComponentProps {
  size: number
  state: AssistantState
  mood: AssistantMood
}

/**
 * Avatar component registry.
 * Add new avatar types here — the key becomes the avatarType string
 * used in personalities.json and config.yaml.
 */
export const AVATAR_REGISTRY: Record<string, React.ComponentType<AvatarComponentProps>> = {
  orb: AvatarOrb,
  pixel: AvatarPixel,
  light: AvatarLight,
  caricature: AvatarCaricature,
  cozmo: AvatarCozmo,
}

/** Get list of all registered avatar type names. */
export function getAvatarTypes(): string[] {
  return Object.keys(AVATAR_REGISTRY)
}

interface AvatarProps {
  size: number
  state: AssistantState
  mood: AssistantMood
}

export function Avatar({ size, state, mood }: AvatarProps) {
  const { getToken, currentPersonality } = useTokens()
  const avatarType = (getToken('personality.avatarType') || 'orb') as string
  const Component = AVATAR_REGISTRY[avatarType] || AvatarOrb

  return (
    <AnimatePresence mode="wait">
      <Component key={`${currentPersonality}-${avatarType}`} size={size} state={state} mood={mood} />
    </AnimatePresence>
  )
}
