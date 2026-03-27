/**
 * QuizStats -- end-of-game summary with animated score reveal.
 *
 * Shows: big animated score count-up, accuracy ring, personality reaction,
 * and action buttons. Replaces the question area inside QuizCard.
 */

import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'

interface QuizStatsProps {
  score: { correct: number; total: number }
  reaction?: string
  onPlayAgain: () => void
  onQuit: () => void
}

/** Circular progress ring that draws itself clockwise */
function AccuracyRing({ percentage }: { percentage: number }) {
  const size = 100
  const strokeWidth = 6
  const radius = (size - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (percentage / 100) * circumference

  return (
    <div style={{ position: 'relative', width: size, height: size }}>
      {/* Background ring */}
      <svg width={size} height={size} style={{ position: 'absolute', transform: 'rotate(-90deg)' }}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="rgba(255, 255, 255, 0.06)"
          strokeWidth={strokeWidth}
        />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--personality-accent)"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 1.2, ease: 'easeOut', delay: 0.3 }}
          style={{ filter: 'drop-shadow(0 0 6px rgba(var(--personality-accent-rgb), 0.4))' }}
        />
      </svg>

      {/* Center text */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <motion.span
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.8 }}
          style={{
            fontSize: 22,
            fontWeight: 700,
            color: 'var(--personality-accent)',
            lineHeight: 1,
          }}
        >
          {percentage}%
        </motion.span>
        <motion.span
          initial={{ opacity: 0 }}
          animate={{ opacity: 0.5 }}
          transition={{ delay: 1 }}
          style={{ fontSize: 10, color: 'rgba(255, 255, 255, 0.5)', marginTop: 2 }}
        >
          accuracy
        </motion.span>
      </div>
    </div>
  )
}

/** Animated score number that rolls up from 0 */
function AnimatedScore({ target, total }: { target: number; total: number }) {
  const [display, setDisplay] = useState(0)

  useEffect(() => {
    if (target === 0) { setDisplay(0); return }
    const duration = 1000
    const steps = Math.min(target, 20)
    const interval = duration / steps
    let current = 0
    const timer = setInterval(() => {
      current++
      setDisplay(current)
      if (current >= target) clearInterval(timer)
    }, interval)
    return () => clearInterval(timer)
  }, [target])

  return (
    <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
      <motion.span
        key={display}
        initial={{ y: -10, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        style={{
          fontSize: 48,
          fontWeight: 800,
          color: 'var(--personality-accent)',
          fontVariantNumeric: 'tabular-nums',
          lineHeight: 1,
        }}
      >
        {display}
      </motion.span>
      <span style={{ fontSize: 20, fontWeight: 500, color: 'rgba(255, 255, 255, 0.3)' }}>
        / {total}
      </span>
    </div>
  )
}

export function QuizStats({ score, reaction, onPlayAgain, onQuit }: QuizStatsProps) {
  const percentage = score.total > 0 ? Math.round((score.correct / score.total) * 100) : 0

  // Pick an emoji based on score
  const emoji =
    percentage >= 90 ? '\uD83C\uDF89'    // party popper
    : percentage >= 70 ? '\uD83D\uDE0E'   // cool sunglasses
    : percentage >= 50 ? '\uD83D\uDE0A'   // slightly smiling
    : percentage >= 30 ? '\uD83E\uDD14'   // thinking
    : '\uD83D\uDE2C'                       // grimacing

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: 'spring', stiffness: 300, damping: 30 }}
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 20,
        padding: '8px 0',
      }}
    >
      {/* Emoji */}
      <motion.div
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        transition={{ type: 'spring', stiffness: 500, damping: 20, delay: 0.1 }}
        style={{ fontSize: 40 }}
      >
        {emoji}
      </motion.div>

      {/* Score + Ring side by side */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
        <AnimatedScore target={score.correct} total={score.total} />
        <AccuracyRing percentage={percentage} />
      </div>

      {/* Personality reaction */}
      {reaction && (
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1.2 }}
          style={{
            fontSize: 14,
            fontStyle: 'italic',
            color: 'rgba(255, 255, 255, 0.6)',
            textAlign: 'center',
            lineHeight: 1.5,
            maxWidth: 300,
            padding: '0 8px',
          }}
        >
          &ldquo;{reaction}&rdquo;
        </motion.p>
      )}

      {/* Action buttons */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 1.4, type: 'spring', stiffness: 300, damping: 25 }}
        style={{ display: 'flex', gap: 12, marginTop: 4 }}
      >
        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={onPlayAgain}
          style={{
            padding: '10px 24px',
            borderRadius: 12,
            border: 'none',
            background: 'var(--personality-accent)',
            color: '#0a0a0c',
            fontSize: 14,
            fontWeight: 600,
            cursor: 'pointer',
            boxShadow: '0 2px 12px rgba(var(--personality-accent-rgb), 0.3)',
          }}
        >
          Play Again
        </motion.button>
        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={onQuit}
          style={{
            padding: '10px 24px',
            borderRadius: 12,
            border: '1px solid rgba(255, 255, 255, 0.1)',
            background: 'rgba(255, 255, 255, 0.04)',
            color: 'rgba(255, 255, 255, 0.6)',
            fontSize: 14,
            fontWeight: 500,
            cursor: 'pointer',
          }}
        >
          Done
        </motion.button>
      </motion.div>
    </motion.div>
  )
}
