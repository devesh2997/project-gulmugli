/**
 * Gesture detection hook.
 *
 * Detects touch swipes, keyboard arrow keys, and mouse drags.
 * Fires a callback with the detected direction.
 */

import { useEffect } from 'react'

type GestureDirection = 'up' | 'down' | 'left' | 'right'
type GestureCallback = (direction: GestureDirection) => void

/**
 * Check if an event target is inside a draggable widget, slider, or other
 * interactive element that should NOT trigger panel swipe gestures.
 */
function isInsideInteractive(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  // Walk up the DOM tree looking for elements that handle their own drag
  let el: HTMLElement | null = target
  while (el) {
    // Framer-motion draggable elements get this attribute
    if (el.getAttribute('data-framer-drag') !== null) return true
    // Our explicit marker for interactive areas (sliders, widgets, etc.)
    if (el.dataset.gestureIgnore === 'true') return true
    // Elements inside slide panels shouldn't trigger new panel gestures
    if (el.getAttribute('data-panel') === 'true') return true
    // Any button, input, or interactive control
    const tag = el.tagName
    if (tag === 'BUTTON' || tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') return true
    el = el.parentElement
  }
  return false
}

export function useGesture(onGesture: GestureCallback): void {
  useEffect(() => {
    const THRESHOLD = 50

    // Touch tracking
    let touchStartX = 0
    let touchStartY = 0
    let touchBlocked = false

    const onTouchStart = (e: TouchEvent) => {
      touchBlocked = isInsideInteractive(e.target)
      touchStartX = e.touches[0].clientX
      touchStartY = e.touches[0].clientY
    }

    const onTouchEnd = (e: TouchEvent) => {
      if (touchBlocked) return
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
    let mouseBlocked = false

    const onMouseDown = (e: MouseEvent) => {
      mouseBlocked = isInsideInteractive(e.target)
      mouseStartX = e.clientX
      mouseStartY = e.clientY
      isDragging = true
    }

    const onMouseUp = (e: MouseEvent) => {
      if (!isDragging) return
      isDragging = false
      if (mouseBlocked) return
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
