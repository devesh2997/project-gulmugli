/**
 * LightsPanel — visual light controls.
 *
 * Designed to feel like controlling ambient lighting in a smart room,
 * not a settings form. Contains: lamp silhouette toggle, horizontal
 * colour gradient strip, draggable brightness slider, scene preview cards.
 * The panel background subtly tints with the current light colour.
 */

import { useRef, useCallback } from 'react'
import { motion } from 'framer-motion'
import type { AssistantStore } from '../types/assistant'
import { LightOrb } from './lights/LightOrb'

interface Props {
  store: AssistantStore
}

/* ───── Colour strip with smooth gradient ───── */

const COLOR_STOPS = [
  { name: 'Warm White', color: '#ffd4a0', pos: 0 },
  { name: 'Cool White', color: '#e8f0ff', pos: 14 },
  { name: 'Red', color: '#ff4444', pos: 28 },
  { name: 'Orange', color: '#ff8844', pos: 42 },
  { name: 'Pink', color: '#ff44aa', pos: 56 },
  { name: 'Purple', color: '#aa44ff', pos: 70 },
  { name: 'Blue', color: '#4488ff', pos: 84 },
  { name: 'Green', color: '#44ff88', pos: 100 },
]

const GRADIENT = `linear-gradient(90deg, ${COLOR_STOPS.map(s => `${s.color} ${s.pos}%`).join(', ')})`

function ColorStrip({ currentColor, on, onColorChange }: {
  currentColor: string; on: boolean
  onColorChange: (color: string) => void
}) {
  const trackRef = useRef<HTMLDivElement>(null)
  const draggingRef = useRef(false)

  const pickColor = useCallback((clientX: number) => {
    if (!trackRef.current) return
    const r = trackRef.current.getBoundingClientRect()
    const ratio = Math.max(0, Math.min(1, (clientX - r.left) / r.width))
    // Find the two surrounding stops and interpolate
    const pos = ratio * 100
    let left = COLOR_STOPS[0], right = COLOR_STOPS[COLOR_STOPS.length - 1]
    for (let i = 0; i < COLOR_STOPS.length - 1; i++) {
      if (pos >= COLOR_STOPS[i].pos && pos <= COLOR_STOPS[i + 1].pos) {
        left = COLOR_STOPS[i]
        right = COLOR_STOPS[i + 1]
        break
      }
    }
    // Simple: use the nearest stop color
    const distLeft = Math.abs(pos - left.pos)
    const distRight = Math.abs(pos - right.pos)
    const nearest = distLeft <= distRight ? left : right
    onColorChange(nearest.color)
  }, [onColorChange])

  const handlePointerDown = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    draggingRef.current = true
    ;(e.target as HTMLElement).setPointerCapture(e.pointerId)
    pickColor(e.clientX)
  }, [pickColor])

  const handlePointerMove = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    if (!draggingRef.current) return
    pickColor(e.clientX)
  }, [pickColor])

  const handlePointerUp = useCallback(() => {
    draggingRef.current = false
  }, [])

  // Find position of current color on the strip
  const activeStop = COLOR_STOPS.find(s => s.color.toLowerCase() === currentColor.toLowerCase())
  const indicatorPos = activeStop ? activeStop.pos : 50

  return (
    <div
      ref={trackRef}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      style={{
        height: 28, borderRadius: 14,
        background: on ? GRADIENT : `linear-gradient(90deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0.1) 100%)`,
        cursor: 'pointer', position: 'relative',
        touchAction: 'none',
        boxShadow: on ? `inset 0 1px 3px rgba(0,0,0,0.2)` : 'none',
        border: '1px solid rgba(255,255,255,0.06)',
      }}
    >
      {/* Glowing indicator */}
      {on && (
        <motion.div
          animate={{ left: `${indicatorPos}%` }}
          transition={{ type: 'spring', stiffness: 300, damping: 28 }}
          style={{
            position: 'absolute', top: '50%', transform: 'translate(-50%, -50%)',
            width: 22, height: 22, borderRadius: 11,
            background: currentColor,
            border: '2.5px solid rgba(255,255,255,0.8)',
            boxShadow: `0 0 12px ${currentColor}88, 0 2px 6px rgba(0,0,0,0.3)`,
          }}
        />
      )}
    </div>
  )
}

/* ───── Brightness slider ───── */

function BrightnessSlider({ brightness, on, color, onChange }: {
  brightness: number; on: boolean; color: string
  onChange: (val: number) => void
}) {
  const trackRef = useRef<HTMLDivElement>(null)
  const draggingRef = useRef(false)

  const computeValue = useCallback((clientX: number) => {
    if (!trackRef.current) return brightness
    const r = trackRef.current.getBoundingClientRect()
    const ratio = Math.max(0, Math.min(1, (clientX - r.left) / r.width))
    return Math.round(ratio * 100)
  }, [brightness])

  const handlePointerDown = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    draggingRef.current = true
    ;(e.target as HTMLElement).setPointerCapture(e.pointerId)
    onChange(computeValue(e.clientX))
  }, [computeValue, onChange])

  const handlePointerMove = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    if (!draggingRef.current) return
    onChange(computeValue(e.clientX))
  }, [computeValue, onChange])

  const handlePointerUp = useCallback(() => {
    draggingRef.current = false
  }, [])

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
      {/* Dim sun icon */}
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
        stroke="rgba(255,255,255,0.3)" strokeWidth="2" strokeLinecap="round">
        <circle cx="12" cy="12" r="4" />
        <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
      </svg>

      <div
        ref={trackRef}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        style={{
          flex: 1, height: 12, borderRadius: 6,
          background: 'rgba(255,255,255,0.06)', cursor: 'pointer',
          position: 'relative', touchAction: 'none',
          border: '1px solid rgba(255,255,255,0.04)',
        }}
      >
        {/* Filled portion */}
        <motion.div
          animate={{ width: `${brightness}%` }}
          transition={{ type: 'spring', stiffness: 300, damping: 30 }}
          style={{
            height: '100%', borderRadius: 6,
            background: on
              ? `linear-gradient(90deg, rgba(255,255,255,0.08), ${color})`
              : 'rgba(255,255,255,0.1)',
          }}
        />
        {/* Thumb */}
        <motion.div
          animate={{ left: `${brightness}%` }}
          transition={{ type: 'spring', stiffness: 300, damping: 30 }}
          style={{
            position: 'absolute', top: '50%', transform: 'translate(-50%, -50%)',
            width: 22, height: 22, borderRadius: 11,
            background: '#1a1820',
            border: `2.5px solid ${on ? color : 'rgba(255,255,255,0.25)'}`,
            boxShadow: on ? `0 0 10px ${color}44, 0 2px 6px rgba(0,0,0,0.4)` : '0 2px 6px rgba(0,0,0,0.3)',
          }}
        />
      </div>

      {/* Bright sun icon */}
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
        stroke="rgba(255,255,255,0.5)" strokeWidth="2" strokeLinecap="round">
        <circle cx="12" cy="12" r="5" />
        <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
      </svg>

      {/* Value */}
      <span style={{
        fontSize: 12, color: 'rgba(255,255,255,0.5)',
        fontFamily: 'monospace', minWidth: 32, textAlign: 'right',
      }}>
        {brightness}%
      </span>
    </div>
  )
}

/* ───── Scene preview cards ───── */

const SCENE_VISUALS: Record<string, { gradient: string; icon: string }> = {
  reading: {
    gradient: 'linear-gradient(135deg, #ffd4a0 0%, #e8a060 100%)',
    icon: 'M4 19.5A2.5 2.5 0 0 1 6.5 17H20M4 19.5V4.5A2.5 2.5 0 0 1 6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5z',
  },
  movie: {
    gradient: 'linear-gradient(135deg, #2244aa 0%, #1a1a40 100%)',
    icon: 'M7 4v16M17 4v16M3 8h4M17 8h4M3 12h18M3 16h4M17 16h4M4 20h16a1 1 0 0 0 1-1V5a1 1 0 0 0-1-1H4a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1z',
  },
  relax: {
    gradient: 'linear-gradient(135deg, #8844cc 0%, #553399 100%)',
    icon: 'M18 8h1a4 4 0 0 1 0 8h-1M2 8h16v9a4 4 0 0 1-4 4H6a4 4 0 0 1-4-4V8zM6 1v3M10 1v3M14 1v3',
  },
  party: {
    gradient: 'linear-gradient(135deg, #ff4444, #ff8844, #ffd444, #44ff88, #4488ff, #aa44ff)',
    icon: 'M12 2L9.2 8.6 2 9.2l5.5 4.3L5.8 22 12 17.8 18.2 22l-1.7-8.5L22 9.2l-7.2-.6L12 2z',
  },
}

function SceneCard({ name, isActive, on, color, onSelect }: {
  name: string; isActive: boolean; on: boolean; color: string
  onSelect: () => void
}) {
  const visual = SCENE_VISUALS[name.toLowerCase()] || SCENE_VISUALS.relax
  const displayName = name.charAt(0).toUpperCase() + name.slice(1)

  return (
    <motion.button
      onClick={onSelect}
      whileHover={{ scale: 1.03 }}
      whileTap={{ scale: 0.97 }}
      animate={{
        borderColor: isActive && on
          ? `${color}88`
          : 'rgba(255,255,255,0.06)',
        boxShadow: isActive && on
          ? `0 0 16px ${color}30`
          : '0 2px 8px rgba(0,0,0,0.2)',
      }}
      transition={{ type: 'spring', stiffness: 400, damping: 28 }}
      style={{
        flex: '1 1 0',
        minWidth: 72,
        display: 'flex', flexDirection: 'column',
        alignItems: 'center', gap: 8,
        padding: '12px 8px 10px',
        borderRadius: 14,
        background: 'rgba(255,255,255,0.02)',
        border: '1.5px solid rgba(255,255,255,0.06)',
        cursor: 'pointer',
      }}
    >
      {/* Colour swatch */}
      <div style={{
        width: 36, height: 36, borderRadius: 10,
        background: visual.gradient,
        opacity: on ? (isActive ? 1 : 0.5) : 0.2,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        transition: 'opacity 0.25s ease',
      }}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
          stroke="rgba(255,255,255,0.7)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <path d={visual.icon} />
        </svg>
      </div>

      {/* Label */}
      <span style={{
        fontSize: 10, fontWeight: 600,
        letterSpacing: 0.3,
        color: isActive && on ? color : 'rgba(255,255,255,0.4)',
        transition: 'color 0.25s ease',
      }}>
        {displayName}
      </span>
    </motion.button>
  )
}

/* ───── Scenes list ───── */

const SCENES = ['Reading', 'Movie', 'Relax', 'Party']

/* ───── Main panel ───── */

export function LightsPanel({ store }: Props) {
  const lights = store?.lights
  const actions = store?.actions

  const on = lights?.on ?? false
  const color = lights?.color ?? '#ffffff'
  const brightness = lights?.brightness ?? 100
  const scene = lights?.scene ?? null

  return (
    <div style={{
      padding: '24px 20px', maxWidth: 400, margin: '0 auto',
      display: 'flex', flexDirection: 'column', gap: 28,
      position: 'relative',
    }}>
      {/* Subtle room tint overlay */}
      {on && (
        <motion.div
          animate={{ opacity: 0.06 }}
          initial={{ opacity: 0 }}
          transition={{ duration: 0.5 }}
          style={{
            position: 'absolute', inset: 0,
            background: `radial-gradient(ellipse at 50% 30%, ${color}25, transparent 70%)`,
            borderRadius: 16, pointerEvents: 'none',
          }}
        />
      )}

      {/* Lamp silhouette toggle */}
      <LightOrb
        on={on}
        color={color}
        brightness={brightness}
        onToggle={() => actions.setLights({ action: 'toggle' })}
      />

      {/* Status text */}
      <div style={{
        textAlign: 'center', fontSize: 12,
        color: on ? 'rgba(255,255,255,0.5)' : 'rgba(255,255,255,0.25)',
        marginTop: -12,
      }}>
        {on ? `On \u2014 ${brightness}%` : 'Off'}
      </div>

      {/* Colour Gradient Strip */}
      <section>
        <div style={{
          fontSize: 10, fontWeight: 600, letterSpacing: 2,
          textTransform: 'uppercase' as const,
          color: 'rgba(255,255,255,0.3)', marginBottom: 12,
        }}>
          Colour
        </div>
        <ColorStrip
          currentColor={color}
          on={on}
          onColorChange={(c) => actions.setLights({ action: 'color', color: c })}
        />
      </section>

      {/* Brightness Slider */}
      <section>
        <div style={{
          fontSize: 10, fontWeight: 600, letterSpacing: 2,
          textTransform: 'uppercase' as const,
          color: 'rgba(255,255,255,0.3)', marginBottom: 12,
        }}>
          Brightness
        </div>
        <BrightnessSlider
          brightness={brightness}
          on={on}
          color={color}
          onChange={(val) => actions.setLights({ action: 'brightness', value: val })}
        />
      </section>

      {/* Scene Preview Cards */}
      <section>
        <div style={{
          fontSize: 10, fontWeight: 600, letterSpacing: 2,
          textTransform: 'uppercase' as const,
          color: 'rgba(255,255,255,0.3)', marginBottom: 12,
        }}>
          Scenes
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          {SCENES.map(s => (
            <SceneCard
              key={s}
              name={s}
              isActive={scene?.toLowerCase() === s.toLowerCase()}
              on={on}
              color={color}
              onSelect={() => actions.setLights({ action: 'scene', scene: s.toLowerCase() })}
            />
          ))}
        </div>
      </section>
    </div>
  )
}
