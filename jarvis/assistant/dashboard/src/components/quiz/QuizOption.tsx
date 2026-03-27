/**
 * QuizOption -- single answer button with personality-accent styling.
 *
 * States flow: default -> selected (pulsing) -> correct/wrong/revealed.
 * Each state has distinct spring animations so correct feels SATISFYING
 * and wrong feels gentle (red shake, not punishing).
 */

import { motion } from 'framer-motion'

export type OptionState = 'default' | 'selected' | 'correct' | 'wrong' | 'revealed'

interface QuizOptionProps {
  /** Full option text, e.g. "A) Paris" */
  text: string
  /** Letter prefix: A, B, C, D */
  letter: string
  state: OptionState
  disabled: boolean
  onTap: () => void
}

/** Shake keyframes for wrong answers -- gentle, not punishing */
const shakeVariants = {
  shake: {
    x: [0, -6, 6, -6, 6, -3, 3, 0],
    transition: { duration: 0.5, ease: 'easeInOut' as const },
  },
}

/** Extract just the answer text after "X) " prefix if present */
function stripPrefix(text: string): string {
  return text.replace(/^[A-D]\)\s*/, '')
}

export function QuizOption({ text, letter, state, disabled, onTap }: QuizOptionProps) {
  const isCorrect = state === 'correct'
  const isWrong = state === 'wrong'
  const isRevealed = state === 'revealed'
  const isSelected = state === 'selected'

  // Colors per state
  const borderColor =
    isCorrect || isRevealed
      ? 'rgba(74, 222, 128, 0.8)'   // green
      : isWrong
        ? 'rgba(248, 113, 113, 0.8)' // red
        : isSelected
          ? 'var(--personality-accent)'
          : 'rgba(255, 255, 255, 0.1)'

  const bgColor =
    isCorrect
      ? 'rgba(74, 222, 128, 0.12)'
      : isWrong
        ? 'rgba(248, 113, 113, 0.12)'
        : isRevealed
          ? 'rgba(74, 222, 128, 0.06)'
          : isSelected
            ? 'rgba(var(--personality-accent-rgb), 0.1)'
            : 'rgba(255, 255, 255, 0.03)'

  const letterBg =
    isCorrect
      ? 'rgba(74, 222, 128, 0.25)'
      : isWrong
        ? 'rgba(248, 113, 113, 0.25)'
        : isRevealed
          ? 'rgba(74, 222, 128, 0.15)'
          : 'rgba(var(--personality-accent-rgb), 0.12)'

  const letterBorder =
    isCorrect || isRevealed
      ? 'rgba(74, 222, 128, 0.5)'
      : isWrong
        ? 'rgba(248, 113, 113, 0.5)'
        : 'rgba(var(--personality-accent-rgb), 0.3)'

  // Icon in the letter circle
  const icon = isCorrect
    ? '\u2713'    // checkmark
    : isWrong
      ? '\u2717'  // X mark
      : letter

  const iconColor = isCorrect
    ? '#4ade80'
    : isWrong
      ? '#f87171'
      : isSelected
        ? 'var(--personality-accent)'
        : 'rgba(255, 255, 255, 0.7)'

  return (
    <motion.button
      onClick={disabled ? undefined : onTap}
      disabled={disabled}
      variants={isWrong ? shakeVariants : undefined}
      animate={isWrong ? 'shake' : isCorrect ? { scale: [1, 1.04, 1] } : undefined}
      whileHover={!disabled ? { scale: 1.02, borderColor: 'var(--personality-accent)' } : undefined}
      whileTap={!disabled ? { scale: 0.98 } : undefined}
      transition={{ type: 'spring', stiffness: 400, damping: 25 }}
      style={{
        width: '100%',
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: '12px 16px',
        borderRadius: 12,
        border: `1.5px solid ${borderColor}`,
        background: bgColor,
        cursor: disabled ? 'default' : 'pointer',
        outline: 'none',
        textAlign: 'left',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* Letter circle */}
      <motion.span
        animate={{
          scale: isSelected ? [1, 1.15, 1] : 1,
          borderColor: letterBorder,
        }}
        transition={isSelected ? { repeat: Infinity, duration: 1.2 } : { duration: 0.3 }}
        style={{
          width: 32,
          height: 32,
          borderRadius: '50%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: isCorrect || isWrong ? 16 : 14,
          fontWeight: 700,
          color: iconColor,
          background: letterBg,
          border: `1.5px solid ${letterBorder}`,
          flexShrink: 0,
          transition: 'background 0.3s, color 0.3s',
        }}
      >
        {icon}
      </motion.span>

      {/* Option text */}
      <span
        style={{
          fontSize: 15,
          fontWeight: 500,
          color: isCorrect || isRevealed
            ? '#4ade80'
            : isWrong
              ? '#f87171'
              : 'rgba(255, 255, 255, 0.9)',
          lineHeight: 1.35,
          transition: 'color 0.3s',
        }}
      >
        {stripPrefix(text)}
      </span>

      {/* Selected pulsing glow */}
      {isSelected && (
        <motion.div
          animate={{ opacity: [0.3, 0.6, 0.3] }}
          transition={{ repeat: Infinity, duration: 1.5, ease: 'easeInOut' }}
          style={{
            position: 'absolute',
            inset: 0,
            borderRadius: 12,
            background: 'rgba(var(--personality-accent-rgb), 0.05)',
            pointerEvents: 'none',
          }}
        />
      )}

      {/* Correct glow */}
      {isCorrect && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: [0, 0.5, 0] }}
          transition={{ duration: 0.8 }}
          style={{
            position: 'absolute',
            inset: -2,
            borderRadius: 14,
            boxShadow: '0 0 20px rgba(74, 222, 128, 0.4)',
            pointerEvents: 'none',
          }}
        />
      )}
    </motion.button>
  )
}
