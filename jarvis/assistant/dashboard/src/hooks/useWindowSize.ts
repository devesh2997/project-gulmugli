/**
 * Window size hook — provides responsive breakpoint info.
 *
 * Screen categories for the assistant:
 *   xs: 3.5" screen (~320-480px) — tiny embedded display
 *   sm: 5" screen (~480-640px) — small embedded or phone
 *   md: 7" screen (~640-900px) — tablet-size attached display
 *   lg: 10"+ / Mac / monitor (>900px) — full desktop
 */

import { useState, useEffect } from 'react'

export type Breakpoint = 'xs' | 'sm' | 'md' | 'lg'

export interface WindowSize {
  width: number
  height: number
  breakpoint: Breakpoint
  isCompact: boolean
  isMedium: boolean
}

export function useWindowSize(): WindowSize {
  const [size, setSize] = useState({
    width: window.innerWidth,
    height: window.innerHeight,
  })

  useEffect(() => {
    let rafId: number | null = null
    const onResize = () => {
      if (rafId) cancelAnimationFrame(rafId)
      rafId = requestAnimationFrame(() => {
        setSize({ width: window.innerWidth, height: window.innerHeight })
      })
    }
    window.addEventListener('resize', onResize)
    return () => {
      window.removeEventListener('resize', onResize)
      if (rafId) cancelAnimationFrame(rafId)
    }
  }, [])

  const breakpoint: Breakpoint =
    size.width < 480 ? 'xs' :
    size.width < 640 ? 'sm' :
    size.width < 900 ? 'md' : 'lg'

  const isCompact = breakpoint === 'xs' || breakpoint === 'sm'
  const isMedium = breakpoint === 'md'

  return { ...size, breakpoint, isCompact, isMedium }
}
