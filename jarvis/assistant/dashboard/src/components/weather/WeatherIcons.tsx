/**
 * Animated SVG weather icons.
 *
 * Each icon animates smoothly: sun rays rotate, rain drops fall,
 * lightning flashes, snowflakes drift. Uses framer-motion for
 * spring-based animations.
 *
 * Props:
 *   condition: WeatherCondition key matching backend values
 *   size: pixel size (square)
 *   color: optional accent color override
 */

import { motion } from 'framer-motion'
import type { WeatherCondition } from '../../types/assistant'

interface WeatherIconProps {
  condition: WeatherCondition
  size?: number
  color?: string
}

// ── Sun (sunny) ─────────────────────────────────────────────────
function SunnyIcon({ size = 64, color = '#FFB800' }: { size?: number; color?: string }) {
  const r = size * 0.2
  const rayLen = size * 0.15
  const rayDist = size * 0.32
  const cx = size / 2
  const cy = size / 2

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <motion.g
        animate={{ rotate: 360 }}
        transition={{ duration: 20, repeat: Infinity, ease: 'linear' }}
        style={{ originX: `${cx}px`, originY: `${cy}px` }}
      >
        {/* Rays */}
        {Array.from({ length: 8 }).map((_, i) => {
          const angle = (i * 45 * Math.PI) / 180
          const x1 = cx + Math.cos(angle) * (r + 4)
          const y1 = cy + Math.sin(angle) * (r + 4)
          const x2 = cx + Math.cos(angle) * rayDist
          const y2 = cy + Math.sin(angle) * rayDist
          return (
            <motion.line
              key={i}
              x1={x1} y1={y1} x2={x2} y2={y2}
              stroke={color}
              strokeWidth={size * 0.04}
              strokeLinecap="round"
              initial={{ opacity: 0.6 }}
              animate={{ opacity: [0.6, 1, 0.6] }}
              transition={{ duration: 2, repeat: Infinity, delay: i * 0.25 }}
            />
          )
        })}
      </motion.g>
      {/* Sun body */}
      <motion.circle
        cx={cx} cy={cy} r={r}
        fill={color}
        animate={{ scale: [1, 1.05, 1] }}
        transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
        style={{ originX: `${cx}px`, originY: `${cy}px` }}
      />
    </svg>
  )
}

// ── Partly Cloudy ───────────────────────────────────────────────
function PartlyCloudyIcon({ size = 64, color = '#FFB800' }: { size?: number; color?: string }) {
  const s = size
  return (
    <svg width={s} height={s} viewBox="0 0 64 64">
      {/* Small sun behind */}
      <motion.g
        animate={{ rotate: 360 }}
        transition={{ duration: 20, repeat: Infinity, ease: 'linear' }}
        style={{ originX: '20px', originY: '22px' }}
      >
        {Array.from({ length: 6 }).map((_, i) => {
          const angle = (i * 60 * Math.PI) / 180
          return (
            <line
              key={i}
              x1={20 + Math.cos(angle) * 8}
              y1={22 + Math.sin(angle) * 8}
              x2={20 + Math.cos(angle) * 12}
              y2={22 + Math.sin(angle) * 12}
              stroke={color}
              strokeWidth={2}
              strokeLinecap="round"
            />
          )
        })}
      </motion.g>
      <circle cx={20} cy={22} r={7} fill={color} />
      {/* Cloud in front */}
      <motion.g
        animate={{ x: [0, 2, 0] }}
        transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut' }}
      >
        <ellipse cx={36} cy={38} rx={16} ry={10} fill="#D0D8E8" />
        <ellipse cx={30} cy={32} rx={10} ry={8} fill="#E0E6F0" />
        <ellipse cx={42} cy={33} rx={9} ry={7} fill="#D8DFEd" />
      </motion.g>
    </svg>
  )
}

// ── Cloudy ──────────────────────────────────────────────────────
function CloudyIcon({ size = 64 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64">
      <motion.g
        animate={{ x: [0, 3, 0, -3, 0] }}
        transition={{ duration: 8, repeat: Infinity, ease: 'easeInOut' }}
      >
        <ellipse cx={22} cy={34} rx={14} ry={9} fill="#C0C8D8" />
        <ellipse cx={34} cy={28} rx={12} ry={9} fill="#D0D8E8" />
        <ellipse cx={40} cy={36} rx={16} ry={10} fill="#B8C0D0" />
        <ellipse cx={30} cy={38} rx={18} ry={10} fill="#CDD4E4" />
      </motion.g>
    </svg>
  )
}

// ── Rain ────────────────────────────────────────────────────────
function RainIcon({ size = 64, color = '#5B9BD5' }: { size?: number; color?: string }) {
  const drops = [
    { x: 20, delay: 0 },
    { x: 30, delay: 0.3 },
    { x: 40, delay: 0.6 },
    { x: 25, delay: 0.15 },
    { x: 35, delay: 0.45 },
  ]
  return (
    <svg width={size} height={size} viewBox="0 0 64 64">
      {/* Cloud */}
      <ellipse cx={32} cy={24} rx={18} ry={10} fill="#8E99A8" />
      <ellipse cx={24} cy={22} rx={10} ry={8} fill="#9AA4B4" />
      <ellipse cx={40} cy={22} rx={10} ry={8} fill="#9AA4B4" />
      {/* Rain drops */}
      {drops.map((drop, i) => (
        <motion.line
          key={i}
          x1={drop.x} y1={36}
          x2={drop.x - 2} y2={44}
          stroke={color}
          strokeWidth={2}
          strokeLinecap="round"
          initial={{ y: 0, opacity: 1 }}
          animate={{ y: [0, 14, 0], opacity: [1, 0.3, 1] }}
          transition={{ duration: 1, repeat: Infinity, delay: drop.delay, ease: 'easeIn' }}
        />
      ))}
    </svg>
  )
}

// ── Thunderstorm ────────────────────────────────────────────────
function ThunderstormIcon({ size = 64 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64">
      {/* Dark cloud */}
      <ellipse cx={32} cy={22} rx={18} ry={10} fill="#6B7280" />
      <ellipse cx={24} cy={20} rx={10} ry={8} fill="#7B8290" />
      <ellipse cx={40} cy={20} rx={10} ry={8} fill="#7B8290" />
      {/* Lightning bolt */}
      <motion.polygon
        points="30,30 34,30 31,40 36,40 28,54 32,42 27,42"
        fill="#FFD700"
        animate={{ opacity: [1, 0.2, 1, 0.2, 1, 1] }}
        transition={{ duration: 2, repeat: Infinity, times: [0, 0.1, 0.2, 0.3, 0.4, 1] }}
      />
      {/* Rain drops */}
      {[18, 42, 46].map((x, i) => (
        <motion.line
          key={i}
          x1={x} y1={34}
          x2={x - 2} y2={42}
          stroke="#5B9BD5"
          strokeWidth={2}
          strokeLinecap="round"
          animate={{ y: [0, 12, 0], opacity: [1, 0.3, 1] }}
          transition={{ duration: 0.8, repeat: Infinity, delay: i * 0.2 }}
        />
      ))}
    </svg>
  )
}

// ── Snow ────────────────────────────────────────────────────────
function SnowIcon({ size = 64 }: { size?: number }) {
  const flakes = [
    { x: 20, delay: 0 },
    { x: 30, delay: 0.4 },
    { x: 40, delay: 0.8 },
    { x: 25, delay: 0.2 },
    { x: 35, delay: 0.6 },
  ]
  return (
    <svg width={size} height={size} viewBox="0 0 64 64">
      {/* Cloud */}
      <ellipse cx={32} cy={22} rx={18} ry={10} fill="#B0B8C8" />
      <ellipse cx={24} cy={20} rx={10} ry={8} fill="#C0C8D8" />
      <ellipse cx={40} cy={20} rx={10} ry={8} fill="#C0C8D8" />
      {/* Snowflakes */}
      {flakes.map((flake, i) => (
        <motion.g
          key={i}
          animate={{
            y: [0, 18, 0],
            x: [0, (i % 2 === 0 ? 3 : -3), 0],
            rotate: [0, 180, 360],
            opacity: [1, 0.4, 1],
          }}
          transition={{ duration: 2.5, repeat: Infinity, delay: flake.delay, ease: 'easeInOut' }}
        >
          <circle cx={flake.x} cy={36} r={2.5} fill="white" opacity={0.9} />
        </motion.g>
      ))}
    </svg>
  )
}

// ── Fog ─────────────────────────────────────────────────────────
function FogIcon({ size = 64 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64">
      {[24, 32, 40].map((y, i) => (
        <motion.line
          key={i}
          x1={12} y1={y} x2={52} y2={y}
          stroke="#B0B8C8"
          strokeWidth={4}
          strokeLinecap="round"
          animate={{ x: [0, (i % 2 === 0 ? 4 : -4), 0], opacity: [0.5, 0.8, 0.5] }}
          transition={{ duration: 3, repeat: Infinity, delay: i * 0.5, ease: 'easeInOut' }}
        />
      ))}
    </svg>
  )
}

// ── Clear Night ─────────────────────────────────────────────────
function ClearNightIcon({ size = 64, color = '#C4B5FD' }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64">
      {/* Moon (crescent via two overlapping circles) */}
      <motion.g
        animate={{ rotate: [0, 5, 0, -5, 0] }}
        transition={{ duration: 6, repeat: Infinity, ease: 'easeInOut' }}
        style={{ originX: '30px', originY: '30px' }}
      >
        <circle cx={30} cy={30} r={14} fill={color} />
        <circle cx={36} cy={26} r={12} fill="#0F172A" />
      </motion.g>
      {/* Stars */}
      {[
        { x: 48, y: 16, r: 1.5, delay: 0 },
        { x: 50, y: 28, r: 1, delay: 0.5 },
        { x: 44, y: 42, r: 1.2, delay: 1 },
        { x: 16, y: 18, r: 1, delay: 0.3 },
        { x: 12, y: 38, r: 1.3, delay: 0.8 },
      ].map((star, i) => (
        <motion.circle
          key={i}
          cx={star.x} cy={star.y} r={star.r}
          fill="white"
          animate={{ opacity: [0.4, 1, 0.4], scale: [0.8, 1.2, 0.8] }}
          transition={{ duration: 2, repeat: Infinity, delay: star.delay }}
          style={{ originX: `${star.x}px`, originY: `${star.y}px` }}
        />
      ))}
    </svg>
  )
}

// ── Main export ─────────────────────────────────────────────────
const iconMap: Record<WeatherCondition, React.FC<{ size?: number; color?: string }>> = {
  sunny: SunnyIcon,
  partly_cloudy: PartlyCloudyIcon,
  cloudy: CloudyIcon,
  rain: RainIcon,
  thunderstorm: ThunderstormIcon,
  snow: SnowIcon,
  fog: FogIcon,
  clear_night: ClearNightIcon,
}

export function WeatherIcon({ condition, size = 64, color }: WeatherIconProps) {
  const Icon = iconMap[condition] || iconMap.cloudy
  return <Icon size={size} color={color} />
}

/** Map weather condition to ambient glow color for background effects. */
export function conditionToGlow(condition: WeatherCondition): string {
  const glowMap: Record<WeatherCondition, string> = {
    sunny: 'rgba(255, 184, 0, 0.15)',
    partly_cloudy: 'rgba(255, 210, 100, 0.10)',
    cloudy: 'rgba(160, 170, 190, 0.10)',
    rain: 'rgba(80, 130, 190, 0.12)',
    thunderstorm: 'rgba(100, 80, 160, 0.15)',
    snow: 'rgba(200, 210, 240, 0.12)',
    fog: 'rgba(160, 170, 180, 0.10)',
    clear_night: 'rgba(100, 80, 180, 0.10)',
  }
  return glowMap[condition] || 'rgba(100, 100, 100, 0.08)'
}
