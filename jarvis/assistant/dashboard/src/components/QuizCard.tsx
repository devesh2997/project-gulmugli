/**
 * QuizCard -- premium floating quiz overlay with personality theming.
 *
 * This is the star UI for the trivia game. NOT generic -- it's a cinematic,
 * game-show style card with spring animations, personality-accent glow,
 * score dots, timer bar, and confetti bursts on correct answers.
 *
 * Features:
 *   - Floating card with personality-accent glow and blur
 *   - Score dots that fill with pop animation as you answer
 *   - Question transitions slide left/right
 *   - Timer bar shrinks over time in personality accent
 *   - Confetti particles burst on correct answers
 *   - Minimizable to a floating badge (swipe down)
 *   - Stats overlay at end of game
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion, PanInfo } from 'framer-motion'
import { QuizOption, type OptionState } from './quiz/QuizOption'
import { QuizStats } from './quiz/QuizStats'
import type { QuizState, AssistantActions } from '../types/assistant'

interface QuizCardProps {
  quiz: QuizState
  actions: AssistantActions
}

// ─── Category icons ──────────────────────────────────────────────
const CATEGORY_ICONS: Record<string, string> = {
  general: '\uD83C\uDF10',     // globe
  bollywood: '\uD83C\uDFAC',   // clapper
  music: '\uD83C\uDFB5',       // music note
  geography: '\uD83D\uDDFA\uFE0F', // world map
  tech: '\uD83D\uDCBB',        // laptop
  movies: '\uD83C\uDF7F',      // popcorn
  food: '\uD83C\uDF55',        // pizza
  cricket: '\uD83C\uDFCF',     // cricket bat
  science: '\uD83E\uDD2F',     // exploding head
  history: '\uD83C\uDFDB\uFE0F', // classical building
  sports: '\u26BD',             // soccer ball
}

function getCategoryIcon(category: string): string {
  return CATEGORY_ICONS[category.toLowerCase()] ?? '\uD83E\uDDE0' // brain default
}

// ─── Difficulty badge color ──────────────────────────────────────
function getDifficultyColor(difficulty: string): string {
  switch (difficulty.toLowerCase()) {
    case 'easy': return 'rgba(74, 222, 128, 0.7)'
    case 'medium': return 'rgba(250, 204, 21, 0.7)'
    case 'hard': return 'rgba(248, 113, 113, 0.7)'
    default: return 'rgba(255, 255, 255, 0.4)'
  }
}

// ─── Extract letter from option ──────────────────────────────────
function extractLetter(option: string, index: number): string {
  const match = option.match(/^([A-D])\)/)
  return match ? match[1] : String.fromCharCode(65 + index)
}

// ─── Confetti burst ──────────────────────────────────────────────
function ConfettiBurst() {
  const particles = useMemo(() =>
    Array.from({ length: 16 }, (_, i) => ({
      id: i,
      angle: (i / 16) * 360 + (Math.random() - 0.5) * 20,
      distance: 40 + Math.random() * 60,
      size: 4 + Math.random() * 4,
      color: [
        '#4ade80', '#facc15', '#60a5fa', '#f472b6',
        '#a78bfa', '#34d399', '#fb923c', '#22d3ee',
      ][i % 8],
      delay: Math.random() * 0.1,
    })),
  [])

  return (
    <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 20, overflow: 'hidden' }}>
      {particles.map(p => {
        const rad = (p.angle * Math.PI) / 180
        const tx = Math.cos(rad) * p.distance
        const ty = Math.sin(rad) * p.distance
        return (
          <motion.div
            key={p.id}
            initial={{ x: '50%', y: '30%', scale: 0, opacity: 1 }}
            animate={{
              x: `calc(50% + ${tx}px)`,
              y: `calc(30% + ${ty}px)`,
              scale: [0, 1.2, 0.6],
              opacity: [1, 1, 0],
              rotate: Math.random() * 360,
            }}
            transition={{ duration: 0.8, delay: p.delay, ease: 'easeOut' }}
            style={{
              position: 'absolute',
              width: p.size,
              height: p.size,
              borderRadius: Math.random() > 0.5 ? '50%' : 2,
              background: p.color,
            }}
          />
        )
      })}
    </div>
  )
}

// ─── Score dots ──────────────────────────────────────────────────
function ScoreDots({ outcomes, total, currentIndex }: {
  outcomes: ('correct' | 'wrong')[]
  total: number
  currentIndex: number
}) {
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'center',
        gap: 6,
        padding: '4px 0',
        flexWrap: 'wrap',
      }}
    >
      {Array.from({ length: total }, (_, i) => {
        const outcome = outcomes[i]
        const isCurrent = i === currentIndex && !outcome

        let bg: string
        let border: string
        let shadow: string | undefined

        if (outcome === 'correct') {
          bg = 'rgba(74, 222, 128, 0.8)'
          border = 'rgba(74, 222, 128, 0.3)'
          shadow = '0 0 6px rgba(74, 222, 128, 0.4)'
        } else if (outcome === 'wrong') {
          bg = 'rgba(248, 113, 113, 0.6)'
          border = 'rgba(248, 113, 113, 0.3)'
        } else if (isCurrent) {
          bg = 'rgba(var(--personality-accent-rgb), 0.5)'
          border = 'rgba(var(--personality-accent-rgb), 0.3)'
        } else {
          bg = 'rgba(255, 255, 255, 0.06)'
          border = 'rgba(255, 255, 255, 0.06)'
        }

        return (
          <motion.div
            key={i}
            initial={outcome ? { scale: 0 } : false}
            animate={
              isCurrent
                ? { scale: [1, 1.3, 1], opacity: [0.5, 1, 0.5] }
                : outcome
                  ? { scale: [0, 1.4, 1] }
                  : { scale: 1 }
            }
            transition={
              isCurrent
                ? { repeat: Infinity, duration: 1.5, ease: 'easeInOut' }
                : outcome
                  ? { type: 'spring', stiffness: 500, damping: 15 }
                  : undefined
            }
            style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              background: bg,
              border: `1px solid ${border}`,
              boxShadow: shadow,
            }}
          />
        )
      })}
    </div>
  )
}

// ─── Timer bar ───────────────────────────────────────────────────
function TimerBar({ timeLimit, running }: { timeLimit: number; running: boolean }) {
  return (
    <div
      style={{
        width: '100%',
        height: 3,
        background: 'rgba(255, 255, 255, 0.06)',
        borderRadius: 2,
        overflow: 'hidden',
        marginTop: 8,
      }}
    >
      <motion.div
        initial={{ width: '100%' }}
        animate={running ? { width: '0%' } : { width: '100%' }}
        transition={running ? { duration: timeLimit, ease: 'linear' } : { duration: 0.3 }}
        style={{
          height: '100%',
          background: 'var(--personality-accent)',
          borderRadius: 2,
          boxShadow: '0 0 8px rgba(var(--personality-accent-rgb), 0.4)',
        }}
      />
    </div>
  )
}

// ─── Minimized badge ─────────────────────────────────────────────
function MiniBadge({
  questionNumber,
  totalQuestions,
  onExpand,
}: {
  questionNumber: number
  totalQuestions: number
  onExpand: () => void
}) {
  return (
    <motion.button
      initial={{ scale: 0.5, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      exit={{ scale: 0.5, opacity: 0 }}
      whileHover={{ scale: 1.05 }}
      whileTap={{ scale: 0.95 }}
      onClick={onExpand}
      style={{
        position: 'fixed',
        bottom: 24,
        right: 24,
        zIndex: 45,
        padding: '8px 16px',
        borderRadius: 20,
        border: '1px solid rgba(var(--personality-accent-rgb), 0.3)',
        background: 'rgba(10, 10, 12, 0.85)',
        backdropFilter: 'blur(16px)',
        color: 'var(--personality-accent)',
        fontSize: 13,
        fontWeight: 600,
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        boxShadow: '0 4px 20px rgba(0, 0, 0, 0.4), 0 0 12px rgba(var(--personality-accent-rgb), 0.15)',
      }}
    >
      <span style={{ fontSize: 14 }}>{'\uD83E\uDDE0'}</span>
      Quiz Q{questionNumber}/{totalQuestions}
    </motion.button>
  )
}

// ─── Main QuizCard ───────────────────────────────────────────────
export function QuizCard({ quiz, actions }: QuizCardProps) {
  const { question, lastResult, score, outcomes, showStats } = quiz
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null)
  const [minimized, setMinimized] = useState(false)
  const [showConfetti, setShowConfetti] = useState(false)
  const [timerRunning, setTimerRunning] = useState(false)
  // Track question number to detect transitions
  const prevQuestionNum = useRef<number>(0)
  // Slide direction for question transitions
  const [slideDir, setSlideDir] = useState<1 | -1>(1)

  // Reset selection when question changes
  useEffect(() => {
    if (question && question.questionNumber !== prevQuestionNum.current) {
      setSelectedIndex(null)
      setShowConfetti(false)
      setTimerRunning(true)
      setSlideDir(1)
      prevQuestionNum.current = question.questionNumber
    }
  }, [question?.questionNumber])

  // Confetti on correct answer
  useEffect(() => {
    if (lastResult?.correct) {
      setShowConfetti(true)
      setTimerRunning(false)
      const t = setTimeout(() => setShowConfetti(false), 1000)
      return () => clearTimeout(t)
    }
    if (lastResult && !lastResult.correct) {
      setTimerRunning(false)
    }
  }, [lastResult])

  const handleOptionTap = useCallback((index: number) => {
    if (selectedIndex !== null || lastResult) return
    setSelectedIndex(index)
    setTimerRunning(false)
    // Send the full option text to the backend
    if (question?.options[index]) {
      actions.quizAnswer(question.options[index])
    }
  }, [selectedIndex, lastResult, question, actions])

  const handleSwipeDown = useCallback((_e: MouseEvent | TouchEvent | PointerEvent, info: PanInfo) => {
    if (info.offset.y > 60) {
      setMinimized(true)
    }
  }, [])

  const handlePlayAgain = useCallback(() => {
    actions.sendText('play again')
  }, [actions])

  const handleQuit = useCallback(() => {
    actions.quizQuit()
  }, [actions])

  // Determine option states
  const getOptionState = useCallback((index: number): OptionState => {
    if (!lastResult) {
      return index === selectedIndex ? 'selected' : 'default'
    }
    // After result
    const optText = question?.options[index] ?? ''
    const isCorrectOption = optText === lastResult.correctAnswer ||
      optText.replace(/^[A-D]\)\s*/, '') === lastResult.correctAnswer.replace(/^[A-D]\)\s*/, '')
    if (index === selectedIndex && lastResult.correct) return 'correct'
    if (index === selectedIndex && !lastResult.correct) return 'wrong'
    if (isCorrectOption) return 'revealed'
    return 'default'
  }, [lastResult, selectedIndex, question])

  // Show minimized badge
  if (minimized) {
    return (
      <AnimatePresence>
        <MiniBadge
          questionNumber={question?.questionNumber ?? 1}
          totalQuestions={question?.totalQuestions ?? 10}
          onExpand={() => setMinimized(false)}
        />
      </AnimatePresence>
    )
  }

  if (!question && !showStats) return null

  return (
    <motion.div
      initial={{ scale: 0.85, opacity: 0, rotate: -1 }}
      animate={{ scale: 1, opacity: 1, rotate: 0 }}
      exit={{ scale: 0.85, opacity: 0, rotate: 1 }}
      transition={{ type: 'spring', stiffness: 300, damping: 25 }}
      drag="y"
      dragConstraints={{ top: 0, bottom: 0 }}
      dragElastic={0.3}
      onDragEnd={handleSwipeDown}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 45,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 16,
        // Allow seeing avatar behind
        pointerEvents: 'none',
      }}
    >
      {/* Backdrop dim */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        style={{
          position: 'absolute',
          inset: 0,
          background: 'rgba(0, 0, 0, 0.4)',
          backdropFilter: 'blur(4px)',
          pointerEvents: 'auto',
        }}
        onClick={() => setMinimized(true)}
      />

      {/* Card */}
      <motion.div
        layout
        style={{
          position: 'relative',
          width: '85%',
          maxWidth: 420,
          maxHeight: '85vh',
          borderRadius: 20,
          background: 'rgba(12, 12, 16, 0.92)',
          backdropFilter: 'blur(24px)',
          border: '1px solid rgba(var(--personality-accent-rgb), 0.15)',
          boxShadow: `
            0 8px 40px rgba(0, 0, 0, 0.5),
            0 0 30px rgba(var(--personality-accent-rgb), 0.08),
            inset 0 1px 0 rgba(255, 255, 255, 0.04)
          `,
          overflow: 'hidden',
          pointerEvents: 'auto',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {/* Confetti */}
        <AnimatePresence>
          {showConfetti && <ConfettiBurst />}
        </AnimatePresence>

        {/* Header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '14px 16px 8px',
          }}
        >
          {/* Category pill + difficulty */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {question && (
              <>
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 4,
                    padding: '3px 10px',
                    borderRadius: 12,
                    background: 'rgba(var(--personality-accent-rgb), 0.1)',
                    border: '1px solid rgba(var(--personality-accent-rgb), 0.15)',
                    fontSize: 12,
                    fontWeight: 500,
                    color: 'rgba(255, 255, 255, 0.7)',
                  }}
                >
                  <span style={{ fontSize: 13 }}>{getCategoryIcon(question.category)}</span>
                  {question.category}
                </span>
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: 600,
                    textTransform: 'uppercase',
                    letterSpacing: 0.5,
                    color: getDifficultyColor(question.difficulty),
                  }}
                >
                  {question.difficulty}
                </span>
              </>
            )}
          </div>

          {/* Right side: question counter + close */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {question && !showStats && (
              <span
                style={{
                  fontSize: 13,
                  fontWeight: 600,
                  color: 'rgba(var(--personality-accent-rgb), 0.7)',
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                Q{question.questionNumber}/{question.totalQuestions}
              </span>
            )}
            <motion.button
              whileHover={{ scale: 1.15, opacity: 1 }}
              whileTap={{ scale: 0.9 }}
              onClick={() => actions.quizQuit()}
              style={{
                width: 28,
                height: 28,
                borderRadius: '50%',
                border: 'none',
                background: 'rgba(255, 255, 255, 0.06)',
                color: 'rgba(255, 255, 255, 0.4)',
                fontSize: 14,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              {'\u2715'}
            </motion.button>
          </div>
        </div>

        {/* Score dots */}
        {question && !showStats && (
          <div style={{ padding: '0 16px' }}>
            <ScoreDots
              outcomes={outcomes}
              total={question.totalQuestions}
              currentIndex={question.questionNumber - 1}
            />
          </div>
        )}

        {/* Content area */}
        <div style={{ flex: 1, overflow: 'auto', padding: '0 16px 16px' }}>
          <AnimatePresence mode="wait">
            {showStats ? (
              <motion.div
                key="stats"
                initial={{ opacity: 0, x: 40 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -40 }}
                transition={{ type: 'spring', stiffness: 300, damping: 30 }}
              >
                <QuizStats
                  score={score}
                  reaction={lastResult?.reaction}
                  onPlayAgain={handlePlayAgain}
                  onQuit={handleQuit}
                />
              </motion.div>
            ) : question ? (
              <motion.div
                key={`q-${question.questionNumber}`}
                initial={{ opacity: 0, x: slideDir * 60 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: slideDir * -60 }}
                transition={{ type: 'spring', stiffness: 300, damping: 30 }}
              >
                {/* Question text */}
                <p
                  style={{
                    fontSize: 17,
                    fontWeight: 600,
                    lineHeight: 1.5,
                    color: 'rgba(255, 255, 255, 0.92)',
                    margin: '12px 0 4px',
                  }}
                >
                  {question.question}
                </p>

                {/* Timer bar */}
                {question.timeLimit && question.timeLimit > 0 && (
                  <TimerBar
                    timeLimit={question.timeLimit}
                    running={timerRunning && !lastResult}
                  />
                )}

                {/* Options */}
                <div
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 8,
                    marginTop: 16,
                  }}
                >
                  {question.options.map((opt, i) => (
                    <QuizOption
                      key={`${question.questionNumber}-${i}`}
                      text={opt}
                      letter={extractLetter(opt, i)}
                      state={getOptionState(i)}
                      disabled={selectedIndex !== null || !!lastResult}
                      onTap={() => handleOptionTap(i)}
                    />
                  ))}
                </div>

                {/* Reaction text after answer */}
                <AnimatePresence>
                  {lastResult && lastResult.reaction && !showStats && (
                    <motion.p
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0 }}
                      transition={{ delay: 0.3 }}
                      style={{
                        fontSize: 13,
                        fontStyle: 'italic',
                        color: 'rgba(255, 255, 255, 0.5)',
                        textAlign: 'center',
                        marginTop: 12,
                        lineHeight: 1.4,
                      }}
                    >
                      &ldquo;{lastResult.reaction}&rdquo;
                    </motion.p>
                  )}
                </AnimatePresence>

                {/* Explanation after answer */}
                <AnimatePresence>
                  {lastResult && lastResult.explanation && !showStats && (
                    <motion.p
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0 }}
                      transition={{ delay: 0.5 }}
                      style={{
                        fontSize: 12,
                        color: 'rgba(255, 255, 255, 0.35)',
                        textAlign: 'center',
                        marginTop: 6,
                        lineHeight: 1.4,
                      }}
                    >
                      {lastResult.explanation}
                    </motion.p>
                  )}
                </AnimatePresence>
              </motion.div>
            ) : null}
          </AnimatePresence>
        </div>

        {/* Bottom accent line */}
        <div
          style={{
            height: 2,
            background: `linear-gradient(90deg, transparent, var(--personality-accent), transparent)`,
            opacity: 0.3,
          }}
        />
      </motion.div>
    </motion.div>
  )
}
