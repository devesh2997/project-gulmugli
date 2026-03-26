/**
 * TransitionDissolver — wraps the Avatar and orchestrates the 3-phase
 * dissolve/reform animation whenever the active personality changes.
 *
 * Timing (from animation.json tokens):
 *   dissolve  600ms  — current avatar fades out (opacity 1→0, scale 1→0.8)
 *   pause     400ms  — dark canvas + radial shimmer in new accent color
 *   reform    800ms  — new avatar fades in (opacity 0→1, scale 0.9→1)
 *
 * CSS token updates happen during the dark pause so the shimmer and the
 * incoming avatar both render with the new personality's accent color.
 */

import { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useTokens } from '../context/TokenProvider'

// Numeric constants parsed from animation.json
const DISSOLVE_MS = 600
const PAUSE_MS = 400
const REFORM_MS = 800

type Phase = 'active' | 'dissolving' | 'paused' | 'reforming'

interface TransitionDissolverProps {
  personality: string
  children: React.ReactNode
}

export function TransitionDissolver({ personality, children }: TransitionDissolverProps) {
  const { setPersonality } = useTokens()
  const [phase, setPhase] = useState<Phase>('active')
  const [displayedPersonality, setDisplayedPersonality] = useState(personality)
  const timeoutsRef = useRef<ReturnType<typeof setTimeout>[]>([])

  // Clear all pending timeouts — used on unmount and before each new transition
  function clearAll() {
    timeoutsRef.current.forEach(clearTimeout)
    timeoutsRef.current = []
  }

  useEffect(() => {
    if (personality !== displayedPersonality && phase === 'active') {
      clearAll()
      setPhase('dissolving')

      const t1 = setTimeout(() => {
        setPhase('paused')
        setPersonality(personality) // CSS vars update here, before shimmer renders

        const t2 = setTimeout(() => {
          setDisplayedPersonality(personality)
          setPhase('reforming')

          const t3 = setTimeout(() => setPhase('active'), REFORM_MS)
          timeoutsRef.current.push(t3)
        }, PAUSE_MS)
        timeoutsRef.current.push(t2)
      }, DISSOLVE_MS)
      timeoutsRef.current.push(t1)
    }
  }, [personality]) // eslint-disable-line react-hooks/exhaustive-deps

  // Cleanup on unmount
  useEffect(() => () => clearAll(), [])

  return (
    <div className="relative w-full h-full flex items-center justify-center">
      {/* Avatar — hidden during dark pause */}
      <AnimatePresence>
        {phase !== 'paused' && (
          <motion.div
            key={phase === 'dissolving' ? 'dissolving' : displayedPersonality}
            className="absolute inset-0 flex items-center justify-center"
            initial={
              phase === 'reforming'
                ? { opacity: 0, scale: 0.9 }
                : { opacity: 1, scale: 1 }
            }
            animate={
              phase === 'dissolving'
                ? { opacity: 0, scale: 0.8 }
                : { opacity: 1, scale: 1 }
            }
            exit={{ opacity: 0, scale: 0.8 }}
            transition={{
              duration:
                phase === 'dissolving' ? DISSOLVE_MS / 1000 : REFORM_MS / 1000,
              ease: 'easeInOut',
            }}
          >
            {children}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Shimmer — visible only during dark pause */}
      <AnimatePresence>
        {phase === 'paused' && (
          <motion.div
            key="shimmer"
            className="absolute pointer-events-none"
            style={{
              width: '60%',
              aspectRatio: '1',
              borderRadius: '50%',
              background:
                'radial-gradient(circle, var(--personality-accent) 0%, transparent 70%)',
            }}
            initial={{ opacity: 0, scale: 0.5 }}
            animate={{ opacity: [0, 0.15, 0], scale: [0.5, 1.5, 1.5] }}
            exit={{ opacity: 0 }}
            transition={{ duration: PAUSE_MS / 1000, ease: 'easeOut' }}
          />
        )}
      </AnimatePresence>
    </div>
  )
}
