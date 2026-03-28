/**
 * Weather Widget -- contextual mini-widget that appears when weather is queried.
 *
 * Shows animated weather icon, temperature, condition, feels-like.
 * Personality-colored accent on temperature. Spring animation entry.
 * Auto-fades after 15 seconds. Tap to expand with 3-day forecast + hourly.
 * Weather condition affects ambient background glow color.
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { WeatherIcon, conditionToGlow } from './weather/WeatherIcons'
import type { WeatherData, WeatherCondition } from '../types/assistant'
import { useTokens } from '../context/TokenProvider'

// Personality accent colors — matches the token system defaults
const PERSONALITY_ACCENTS: Record<string, string> = {
  jarvis: '#60A5FA',
  devesh: '#34D399',
  chandler: '#F59E0B',
  girlfriend: '#F472B6',
}

interface WeatherWidgetProps {
  data: WeatherData
  onDismiss: () => void
}

const DAY_NAMES = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

function formatDate(dateStr: string): string {
  try {
    const d = new Date(dateStr + 'T00:00:00')
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    const tomorrow = new Date(today)
    tomorrow.setDate(tomorrow.getDate() + 1)
    if (d.getTime() === today.getTime()) return 'Today'
    if (d.getTime() === tomorrow.getTime()) return 'Tomorrow'
    return DAY_NAMES[d.getDay()]
  } catch {
    return dateStr
  }
}

function formatHour(timeStr: string): string {
  try {
    const [h] = timeStr.split(':')
    const hour = parseInt(h, 10)
    if (hour === 0) return '12am'
    if (hour === 12) return '12pm'
    return hour > 12 ? `${hour - 12}pm` : `${hour}am`
  } catch {
    return timeStr
  }
}

export function WeatherWidget({ data, onDismiss }: WeatherWidgetProps) {
  const [expanded, setExpanded] = useState(false)
  const [showHourly, setShowHourly] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const { currentPersonality } = useTokens()

  const accentColor = PERSONALITY_ACCENTS[currentPersonality] || '#60A5FA'
  const condition = (data.condition || data.icon || 'cloudy') as WeatherCondition
  const glowColor = conditionToGlow(condition)

  // Auto-dismiss after 15 seconds (only when not expanded)
  const resetTimer = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => {
      if (!expanded) onDismiss()
    }, 15000)
  }, [expanded, onDismiss])

  useEffect(() => {
    resetTimer()
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [resetTimer])

  // Pause auto-dismiss while expanded
  useEffect(() => {
    if (expanded && timerRef.current) {
      clearTimeout(timerRef.current)
    } else if (!expanded) {
      resetTimer()
    }
  }, [expanded, resetTimer])

  const handleClick = () => {
    setExpanded(prev => !prev)
  }

  const unit = data.unit || 'C'
  const hasTemperature = data.temperature !== undefined && data.temperature !== null

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: 30, scale: 0.9 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: -20, scale: 0.95 }}
        transition={{ type: 'spring', damping: 20, stiffness: 300 }}
        onClick={handleClick}
        style={{
          position: 'fixed',
          bottom: 24,
          left: '50%',
          transform: 'translateX(-50%)',
          zIndex: 40,
          cursor: 'pointer',
          maxWidth: expanded ? 420 : 320,
          width: '90vw',
        }}
      >
        {/* Ambient glow */}
        <div
          style={{
            position: 'absolute',
            inset: -20,
            borderRadius: 32,
            background: `radial-gradient(ellipse at center, ${glowColor} 0%, transparent 70%)`,
            pointerEvents: 'none',
          }}
        />

        <motion.div
          layout
          style={{
            position: 'relative',
            borderRadius: 20,
            background: 'rgba(15, 23, 42, 0.85)',
            backdropFilter: 'blur(20px)',
            WebkitBackdropFilter: 'blur(20px)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            padding: expanded ? 20 : 16,
            overflow: 'hidden',
          }}
        >
          {/* Compact view: icon + temp + condition */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <WeatherIcon condition={condition} size={expanded ? 56 : 48} />

            <div style={{ flex: 1 }}>
              {hasTemperature && (
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
                  <span style={{
                    fontSize: expanded ? 36 : 32,
                    fontWeight: 700,
                    color: accentColor,
                    lineHeight: 1,
                    fontVariantNumeric: 'tabular-nums',
                  }}>
                    {Math.round(data.temperature!)}
                  </span>
                  <span style={{
                    fontSize: 16,
                    fontWeight: 500,
                    color: 'rgba(255,255,255,0.5)',
                  }}>
                    {'\u00B0'}{unit}
                  </span>
                </div>
              )}
              <div style={{
                fontSize: 13,
                color: 'rgba(255,255,255,0.7)',
                marginTop: 2,
              }}>
                {data.description || condition.replace('_', ' ')}
              </div>
            </div>

            <div style={{ textAlign: 'right' }}>
              {data.feels_like !== undefined && (
                <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.45)' }}>
                  Feels {Math.round(data.feels_like)}{'\u00B0'}
                </div>
              )}
              {data.humidity !== undefined && (
                <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.45)' }}>
                  {data.humidity}% humidity
                </div>
              )}
              <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.35)', marginTop: 2 }}>
                {data.location}
              </div>
            </div>
          </div>

          {/* Expanded view: forecast + hourly */}
          <AnimatePresence>
            {expanded && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.3, ease: 'easeInOut' }}
              >
                {/* Tab switcher */}
                {data.forecast && data.hourly && (
                  <div style={{
                    display: 'flex',
                    gap: 8,
                    marginTop: 14,
                    marginBottom: 10,
                    borderBottom: '1px solid rgba(255,255,255,0.06)',
                    paddingBottom: 8,
                  }}>
                    <button
                      onClick={(e) => { e.stopPropagation(); setShowHourly(false) }}
                      style={{
                        background: 'none',
                        border: 'none',
                        color: !showHourly ? accentColor : 'rgba(255,255,255,0.4)',
                        fontSize: 12,
                        fontWeight: 600,
                        cursor: 'pointer',
                        padding: '2px 8px',
                        borderRadius: 6,
                        ...((!showHourly) ? { background: 'rgba(255,255,255,0.05)' } : {}),
                      }}
                    >
                      Forecast
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); setShowHourly(true) }}
                      style={{
                        background: 'none',
                        border: 'none',
                        color: showHourly ? accentColor : 'rgba(255,255,255,0.4)',
                        fontSize: 12,
                        fontWeight: 600,
                        cursor: 'pointer',
                        padding: '2px 8px',
                        borderRadius: 6,
                        ...(showHourly ? { background: 'rgba(255,255,255,0.05)' } : {}),
                      }}
                    >
                      Hourly
                    </button>
                  </div>
                )}

                {/* Forecast days */}
                {!showHourly && data.forecast && (
                  <div style={{ display: 'flex', gap: 6, marginTop: data.hourly ? 0 : 14 }}>
                    {data.forecast.slice(0, 4).map((day, i) => (
                      <motion.div
                        key={day.date}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: i * 0.08 }}
                        style={{
                          flex: 1,
                          textAlign: 'center',
                          padding: '8px 4px',
                          borderRadius: 12,
                          background: 'rgba(255,255,255,0.03)',
                        }}
                      >
                        <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.5)', marginBottom: 6 }}>
                          {formatDate(day.date)}
                        </div>
                        <WeatherIcon condition={day.icon as WeatherCondition} size={28} />
                        <div style={{ fontSize: 12, fontWeight: 600, color: 'rgba(255,255,255,0.9)', marginTop: 4 }}>
                          {Math.round(day.temp_max)}{'\u00B0'}
                        </div>
                        <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)' }}>
                          {Math.round(day.temp_min)}{'\u00B0'}
                        </div>
                        {day.precipitation_chance > 0 && (
                          <div style={{ fontSize: 10, color: '#5B9BD5', marginTop: 2 }}>
                            {day.precipitation_chance}%
                          </div>
                        )}
                      </motion.div>
                    ))}
                  </div>
                )}

                {/* Hourly breakdown */}
                {showHourly && data.hourly && (
                  <div style={{
                    display: 'flex',
                    gap: 4,
                    overflowX: 'auto',
                    paddingBottom: 4,
                    scrollbarWidth: 'none',
                  }}>
                    {data.hourly.slice(0, 12).map((hour, i) => (
                      <motion.div
                        key={hour.time}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: i * 0.04 }}
                        style={{
                          minWidth: 48,
                          textAlign: 'center',
                          padding: '6px 4px',
                          borderRadius: 10,
                          background: 'rgba(255,255,255,0.03)',
                          flexShrink: 0,
                        }}
                      >
                        <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.45)', marginBottom: 4 }}>
                          {formatHour(hour.time)}
                        </div>
                        <WeatherIcon condition={hour.icon as WeatherCondition} size={22} />
                        <div style={{ fontSize: 12, fontWeight: 600, color: 'rgba(255,255,255,0.85)', marginTop: 3 }}>
                          {Math.round(hour.temperature)}{'\u00B0'}
                        </div>
                        {hour.precipitation_chance > 0 && (
                          <div style={{ fontSize: 9, color: '#5B9BD5', marginTop: 1 }}>
                            {hour.precipitation_chance}%
                          </div>
                        )}
                      </motion.div>
                    ))}
                  </div>
                )}

                {/* Sunrise/sunset bar */}
                {data.sunrise && data.sunset && (
                  <div style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    marginTop: 10,
                    padding: '6px 8px',
                    borderRadius: 8,
                    background: 'rgba(255,255,255,0.02)',
                    fontSize: 11,
                    color: 'rgba(255,255,255,0.4)',
                  }}>
                    <span>{'\u2600'} {data.sunrise}</span>
                    <span>{data.wind_speed !== undefined ? `${data.wind_speed} km/h` : ''}</span>
                    <span>{'\u263D'} {data.sunset}</span>
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  )
}
