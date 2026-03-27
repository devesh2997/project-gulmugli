/**
 * LightsPanel — visual light controls.
 *
 * The panel itself takes on a subtle tint of the current light color.
 * Contains: LightOrb (toggle), color presets, brightness slider, scene tags.
 */

import { useRef, useCallback } from 'react'
import { motion } from 'framer-motion'
import type { AssistantStore } from '../types/assistant'
import { LightOrb } from './lights/LightOrb'

interface Props {
  store: AssistantStore
}

const COLOR_PRESETS = [
  { name: 'Warm', color: '#ffd4a0' },
  { name: 'Cool', color: '#e8f0ff' },
  { name: 'Red', color: '#ff4444' },
  { name: 'Blue', color: '#4488ff' },
  { name: 'Green', color: '#44ff88' },
  { name: 'Purple', color: '#aa44ff' },
  { name: 'Orange', color: '#ff8844' },
  { name: 'Pink', color: '#ff44aa' },
]

const SCENES = ['Reading', 'Movie', 'Relax', 'Party']

export function LightsPanel({ store }: Props) {
  const lights = store?.lights
  const actions = store?.actions
  const trackRef = useRef<HTMLDivElement>(null)

  const on = lights?.on ?? false
  const color = lights?.color ?? '#ffffff'
  const brightness = lights?.brightness ?? 100
  const scene = lights?.scene ?? null

  const handleBrightness = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (!trackRef.current) return
    const r = trackRef.current.getBoundingClientRect()
    const ratio = Math.max(0, Math.min(1, (e.clientX - r.left) / r.width))
    const val = Math.round(ratio * 100)
    actions.setLights({ action: 'brightness', value: val })
  }, [actions])

  return (
    <div style={{
      padding: '24px 20px', maxWidth: 400, margin: '0 auto',
      display: 'flex', flexDirection: 'column', gap: 28,
      position: 'relative',
    }}>
      {/* Subtle room tint overlay */}
      {on && (
        <motion.div
          animate={{ opacity: 0.04 }}
          initial={{ opacity: 0 }}
          style={{
            position: 'absolute', inset: 0,
            background: color, borderRadius: 16, pointerEvents: 'none',
          }}
        />
      )}

      {/* Light Orb */}
      <LightOrb
        on={on}
        color={color}
        brightness={brightness}
        onToggle={() => actions.setLights({ action: 'toggle' })}
      />

      {/* Status text */}
      <div style={{
        textAlign: 'center', fontSize: 12,
        color: on ? 'rgba(255,255,255,0.5)' : 'rgba(255,255,255,0.3)',
      }}>
        {on ? `On \u2014 ${brightness}%` : 'Off'}
      </div>

      {/* Color Presets */}
      <section>
        <div style={{
          fontSize: 10, fontWeight: 600, letterSpacing: 2,
          textTransform: 'uppercase' as const,
          color: 'rgba(255,255,255,0.35)', marginBottom: 12,
        }}>
          Color
        </div>
        <div style={{
          display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap',
        }}>
          {COLOR_PRESETS.map(p => {
            const isActive = on && color.toLowerCase() === p.color.toLowerCase()
            return (
              <motion.button
                key={p.color}
                onClick={() => actions.setLights({ action: 'color', color: p.color })}
                whileHover={{ scale: 1.15 }}
                whileTap={{ scale: 0.9 }}
                style={{
                  width: 24, height: 24, borderRadius: 12,
                  background: p.color, cursor: 'pointer', border: 'none',
                  outline: isActive ? `2px solid ${p.color}` : '2px solid transparent',
                  outlineOffset: 3,
                  boxShadow: isActive ? `0 0 12px ${p.color}66` : 'none',
                }}
                title={p.name}
              />
            )
          })}
        </div>
      </section>

      {/* Brightness Slider */}
      <section>
        <div style={{
          fontSize: 10, fontWeight: 600, letterSpacing: 2,
          textTransform: 'uppercase' as const,
          color: 'rgba(255,255,255,0.35)', marginBottom: 12,
        }}>
          Brightness
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div
            ref={trackRef}
            onClick={handleBrightness}
            style={{
              flex: 1, height: 8, borderRadius: 4,
              background: 'rgba(255,255,255,0.08)', cursor: 'pointer',
              position: 'relative',
            }}
          >
            <motion.div
              animate={{ width: `${brightness}%` }}
              transition={{ type: 'spring', stiffness: 300, damping: 30 }}
              style={{
                height: '100%', borderRadius: 4,
                background: on ? color : 'rgba(255,255,255,0.2)',
              }}
            />
            <motion.div
              animate={{ left: `${brightness}%` }}
              transition={{ type: 'spring', stiffness: 300, damping: 30 }}
              style={{
                position: 'absolute', top: '50%', transform: 'translate(-50%, -50%)',
                width: 18, height: 18, borderRadius: 9,
                background: on ? color : 'rgba(255,255,255,0.3)',
                boxShadow: on ? `0 0 10px ${color}66` : 'none',
                border: '2px solid rgba(255,255,255,0.3)',
              }}
            />
          </div>
          <span style={{
            fontSize: 12, color: 'rgba(255,255,255,0.5)',
            fontFamily: 'monospace', minWidth: 32, textAlign: 'right',
          }}>
            {brightness}%
          </span>
        </div>
      </section>

      {/* Scene Presets */}
      <section>
        <div style={{
          fontSize: 10, fontWeight: 600, letterSpacing: 2,
          textTransform: 'uppercase' as const,
          color: 'rgba(255,255,255,0.35)', marginBottom: 12,
        }}>
          Scenes
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {SCENES.map(s => {
            const isActive = scene?.toLowerCase() === s.toLowerCase()
            return (
              <motion.button
                key={s}
                onClick={() => actions.setLights({ action: 'scene', scene: s.toLowerCase() })}
                whileTap={{ scale: 0.95 }}
                style={{
                  padding: '6px 14px', borderRadius: 16,
                  fontSize: 12, fontWeight: 500, cursor: 'pointer',
                  border: `1px solid ${isActive ? (on ? color : 'rgba(255,255,255,0.3)') : 'rgba(255,255,255,0.1)'}`,
                  background: isActive ? (on ? `${color}22` : 'rgba(255,255,255,0.08)') : 'transparent',
                  color: isActive ? (on ? color : 'rgba(255,255,255,0.6)') : 'rgba(255,255,255,0.4)',
                }}
              >
                {s}
              </motion.button>
            )
          })}
        </div>
      </section>
    </div>
  )
}
