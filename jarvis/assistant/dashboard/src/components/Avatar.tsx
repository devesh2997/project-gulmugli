import { AnimatePresence } from 'framer-motion'
import type { AssistantMood, AssistantState, AvatarType } from '../types/assistant'
import { useTokens } from '../context/TokenProvider'
import { AvatarOrb } from './avatars/AvatarOrb'
import { AvatarPixel } from './avatars/AvatarPixel'
import { AvatarLight } from './avatars/AvatarLight'
import { AvatarCaricature } from './avatars/AvatarCaricature'

interface AvatarProps {
  size: number
  state: AssistantState
  mood: AssistantMood
}

const AVATAR_COMPONENTS: Record<AvatarType, React.ComponentType<AvatarProps>> = {
  orb: AvatarOrb,
  pixel: AvatarPixel,
  light: AvatarLight,
  caricature: AvatarCaricature,
}

export function Avatar({ size, state, mood }: AvatarProps) {
  const { getToken, currentPersonality } = useTokens()
  const avatarType = (getToken('personality.avatarType') || 'orb') as AvatarType
  const Component = AVATAR_COMPONENTS[avatarType] || AvatarOrb

  return (
    <AnimatePresence mode="wait">
      <Component key={currentPersonality} size={size} state={state} mood={mood} />
    </AnimatePresence>
  )
}
