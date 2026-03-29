/**
 * StoryOverlay — full-screen bedtime story experience.
 *
 * Shows when story mode is active. Displays story text paragraph by paragraph
 * with a typewriter-like fade-in, genre icon, and ambient dark overlay.
 * Auto-fades "The End" after story completes.
 */

import { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { StoryState, AssistantActions } from '../types/assistant'

// Genre icons — simple emoji-based, avoids external icon deps
const GENRE_ICONS: Record<string, string> = {
  bedtime: '\u{1F319}',    // crescent moon
  romantic: '\u{2764}',     // heart
  funny: '\u{1F602}',       // laughing face
  scary: '\u{1F47B}',       // ghost
  adventure: '\u{2694}',    // crossed swords
}

interface StoryOverlayProps {
  story: StoryState
  actions: AssistantActions
}

export function StoryOverlay({ story, actions }: StoryOverlayProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const [showEnd, setShowEnd] = useState(false)
  const [visibleCount, setVisibleCount] = useState(0)

  // Reveal paragraphs one at a time with a stagger
  useEffect(() => {
    if (!story.active) {
      setVisibleCount(0)
      setShowEnd(false)
      return
    }

    if (visibleCount < story.paragraphs.length) {
      const timer = setTimeout(() => {
        setVisibleCount(prev => prev + 1)
      }, visibleCount === 0 ? 300 : 1200)
      return () => clearTimeout(timer)
    }

    // All paragraphs visible — show "The End" after a pause
    if (story.paragraphs.length > 0 && visibleCount >= story.paragraphs.length && !story.finished) {
      const endTimer = setTimeout(() => setShowEnd(true), 2000)
      return () => clearTimeout(endTimer)
    }
  }, [story.active, story.paragraphs.length, visibleCount, story.finished])

  // Reset visible count when paragraphs change (continue)
  const prevLengthRef = useRef(story.paragraphs.length)
  useEffect(() => {
    if (story.paragraphs.length > prevLengthRef.current) {
      // New paragraphs added (continue) — keep existing visible, start revealing new ones
      setVisibleCount(prevLengthRef.current)
      setShowEnd(false)
    }
    prevLengthRef.current = story.paragraphs.length
  }, [story.paragraphs.length])

  // Auto-scroll to latest paragraph
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTo({
        top: scrollRef.current.scrollHeight,
        behavior: 'smooth',
      })
    }
  }, [visibleCount])

  const genreIcon = GENRE_ICONS[story.genre ?? ''] ?? GENRE_ICONS.bedtime
  const genreLabel = story.genre
    ? story.genre.charAt(0).toUpperCase() + story.genre.slice(1) + ' Story'
    : 'Story Time'

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 1.2 }}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 46,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'rgba(8, 8, 20, 0.88)',
        backdropFilter: 'blur(8px)',
      }}
    >
      {/* Close button */}
      <button
        onClick={() => actions.sendText('stop the story')}
        style={{
          position: 'absolute',
          top: 20,
          right: 24,
          background: 'none',
          border: 'none',
          color: 'rgba(255, 255, 255, 0.4)',
          fontSize: 28,
          cursor: 'pointer',
          zIndex: 2,
          lineHeight: 1,
          padding: 8,
        }}
        aria-label="Close story"
      >
        &times;
      </button>

      {/* Genre badge */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3, duration: 0.6 }}
        style={{
          fontSize: 42,
          marginBottom: 4,
          textAlign: 'center',
        }}
      >
        {genreIcon}
      </motion.div>

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 0.5 }}
        transition={{ delay: 0.5, duration: 0.6 }}
        style={{
          fontSize: 13,
          letterSpacing: '0.12em',
          textTransform: 'uppercase',
          color: 'rgba(255, 255, 255, 0.5)',
          marginBottom: 32,
          fontFamily: 'system-ui, sans-serif',
        }}
      >
        {genreLabel}
      </motion.div>

      {/* Story text area */}
      <div
        ref={scrollRef}
        style={{
          width: '100%',
          maxWidth: 640,
          maxHeight: '60vh',
          overflowY: 'auto',
          padding: '0 32px',
          scrollbarWidth: 'none',
        }}
      >
        <AnimatePresence>
          {story.paragraphs.slice(0, visibleCount).map((paragraph, i) => (
            <motion.p
              key={`p-${i}`}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, ease: 'easeOut' }}
              style={{
                fontFamily: "'Georgia', 'Times New Roman', 'Palatino', serif",
                fontSize: 18,
                lineHeight: 1.75,
                color: 'rgba(255, 255, 255, 0.88)',
                marginBottom: 24,
                textAlign: 'left',
              }}
            >
              {paragraph}
            </motion.p>
          ))}
        </AnimatePresence>

        {/* "The End" */}
        <AnimatePresence>
          {showEnd && (
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 1, ease: 'easeOut' }}
              style={{
                textAlign: 'center',
                marginTop: 40,
                marginBottom: 40,
              }}
            >
              <span
                style={{
                  fontFamily: "'Georgia', 'Times New Roman', serif",
                  fontStyle: 'italic',
                  fontSize: 22,
                  color: 'rgba(255, 255, 255, 0.6)',
                  letterSpacing: '0.05em',
                }}
              >
                The End
              </span>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Continue hint (shows after all paragraphs revealed but no "The End" yet) */}
      <AnimatePresence>
        {visibleCount >= story.paragraphs.length && story.paragraphs.length > 0 && !showEnd && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.4 }}
            exit={{ opacity: 0 }}
            transition={{ delay: 1, duration: 0.6 }}
            style={{
              position: 'absolute',
              bottom: 32,
              fontSize: 13,
              color: 'rgba(255, 255, 255, 0.4)',
              fontFamily: 'system-ui, sans-serif',
            }}
          >
            Say &ldquo;tell me more&rdquo; to continue
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}
