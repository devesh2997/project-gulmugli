/**
 * Gesture detection hook.
 *
 * Detects touch swipes, keyboard arrow keys, and mouse drags.
 * Fires a callback with the detected direction.
 */

import { useEffect } from 'react'

type GestureDirection = 'up' | 'down' | 'left' | 'right'
type GestureCallback = (direction: GestureDirection) => void

export function useGesture(onGesture: GestureCallback): void {
  useEffect(() => {
    const THRESHOLD = 50

    // Touch tracking
    let touchStartX = 0
    let touchStartY = 0

    const onTouchStart = (e: TouchEvent) => {
      touchStartX = e.touches[0].clientX
      touchStartY = e.touches[0].clientY
    }

    const onTouchEnd = (e: TouchEvent) => {
      const dx = e.changedTouches[0].clientX - touchStartX
      const dy = e.changedTouches[0].clientY - touchStartY
      if (Math.abs(dx) < THRESHOLD && Math.abs(dy) < THRESHOLD) return
      if (Math.abs(dx) > Math.abs(dy)) {
        onGesture(dx > 0 ? 'right' : 'left')
      } else {
        onGesture(dy > 0 ? 'down' : 'up')
      }
    }

    // Keyboard
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'ArrowUp') { e.preventDefault(); onGesture('up') }
      else if (e.key === 'ArrowDown') { e.preventDefault(); onGesture('down') }
      else if (e.key === 'ArrowLeft') { e.preventDefault(); onGesture('left') }
      else if (e.key === 'ArrowRight') { e.preventDefault(); onGesture('right') }
      else if (e.key === 'Escape') { e.preventDefault(); onGesture('down') }
    }

    // Mouse drag tracking
    let mouseStartX = 0
    let mouseStartY = 0
    let isDragging = false

    const onMouseDown = (e: MouseEvent) => {
      mouseStartX = e.clientX
      mouseStartY = e.clientY
      isDragging = true
    }

    const onMouseUp = (e: MouseEvent) => {
      if (!isDragging) return
      isDragging = false
      const dx = e.clientX - mouseStartX
      const dy = e.clientY - mouseStartY
      if (Math.abs(dx) < THRESHOLD && Math.abs(dy) < THRESHOLD) return
      if (Math.abs(dx) > Math.abs(dy)) {
        onGesture(dx > 0 ? 'right' : 'left')
      } else {
        onGesture(dy > 0 ? 'down' : 'up')
      }
    }

    window.addEventListener('touchstart', onTouchStart)
    window.addEventListener('touchend', onTouchEnd)
    window.addEventListener('keydown', onKeyDown)
    window.addEventListener('mousedown', onMouseDown)
    window.addEventListener('mouseup', onMouseUp)

    return () => {
      window.removeEventListener('touchstart', onTouchStart)
      window.removeEventListener('touchend', onTouchEnd)
      window.removeEventListener('keydown', onKeyDown)
      window.removeEventListener('mousedown', onMouseDown)
      window.removeEventListener('mouseup', onMouseUp)
    }
  }, [onGesture])
}
