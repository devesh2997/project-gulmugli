/**
 * useLightMode — reads the --ui-is-light-mode CSS var set by useTimeOfDay.
 *
 * Returns `true` when the background brightness is high enough that
 * dark-mode-designed elements need to adapt (darker text, higher opacity,
 * inverted glass effects, etc.).
 *
 * Polls every 500ms and also listens for the 'time-sim-change' custom event
 * so simulated-time scrubbing updates components immediately.
 */

import { useEffect, useState } from 'react'

export function useLightMode(): boolean {
  const [isLight, setIsLight] = useState(false)

  useEffect(() => {
    const check = () => {
      const val = getComputedStyle(document.documentElement)
        .getPropertyValue('--ui-is-light-mode').trim()
      setIsLight(val === '1')
    }
    check()
    const id = setInterval(check, 500)
    const onSimChange = () => setTimeout(check, 100)
    window.addEventListener('time-sim-change', onSimChange)
    return () => {
      clearInterval(id)
      window.removeEventListener('time-sim-change', onSimChange)
    }
  }, [])

  return isLight
}
