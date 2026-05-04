/**
 * PartyHat — generic SVG party hat overlay for any avatar.
 *
 * Activated when the active event pack's `theme/avatar.json` lists
 * `party_hat` in `accessories`. Brand-agnostic: this file has no idea
 * which event triggers it; the hook decides.
 *
 * Coordinate system:
 * - Wrapper is absolutely positioned at the avatar's top-right rim,
 *   rotated ~15° clockwise so the hat looks "perched", not pasted.
 * - The SVG itself is built in a 100x140 viewBox and scaled down via
 *   `size` so it tracks the avatar at sidebar (small) and kiosk (large).
 * - The hat's tip extends outside the avatar bounds — the AvatarOrb
 *   wrapper already uses `overflow: visible`, which is the contract.
 *
 * Light vs dark backgrounds: palette swaps via `useLightMode`. Dark
 * backgrounds get a vivid magenta cone with cyan stripes; light
 * backgrounds get a richer crimson with deeper navy stripes so it
 * stays readable. The pom-pom is always a warm gold.
 *
 * Animation: framer-motion drop-in from above the avatar with a small
 * wiggle settle. Animation runs once on mount; if the accessory is
 * later removed, the hat unmounts cleanly via AnimatePresence in the
 * parent.
 */

import { motion } from 'framer-motion'
import { useLightMode } from '../../hooks/useLightMode'

export interface PartyHatProps {
  /**
   * The avatar's "core" radius (same `size` prop AvatarOrb consumes).
   * The hat scales relative to this — width is ~55% of the orb's
   * diameter, which lands "small enough to perch, large enough to see".
   */
  size: number
}

interface Palette {
  cone: string
  coneShadow: string
  stripe: string
  pom: string
  pomHighlight: string
  outline: string
}

function getPalette(isLight: boolean): Palette {
  if (isLight) {
    return {
      cone: '#d63a5f', // crimson, reads on light bg
      coneShadow: '#a51b3f',
      stripe: '#1d2c5b', // deep navy
      pom: '#ffc94a',
      pomHighlight: '#fff3b0',
      outline: 'rgba(20, 10, 30, 0.55)',
    }
  }
  return {
    cone: '#ff4fa3', // vivid magenta, pops on dark bg
    coneShadow: '#c91f73',
    stripe: '#3ddcff', // electric cyan
    pom: '#ffd96b',
    pomHighlight: '#fff5c4',
    outline: 'rgba(255, 255, 255, 0.35)',
  }
}

export function PartyHat({ size }: PartyHatProps) {
  const isLight = useLightMode()
  const palette = getPalette(isLight)

  // Hat width ~ 55% of the orb diameter (size is the orb radius, so the
  // diameter is `size`-as-width in the AvatarOrb idiom — see how AvatarOrb
  // uses `width: size, height: size` for its core; here we treat `size`
  // the same way and pick a fraction of that).
  const hatWidth = size * 0.55
  const hatHeight = hatWidth * 1.4 // viewBox is 100x140, preserve ratio

  // Position: top-right rim of the avatar core. AvatarOrb's container is
  // `size * 2` square with the core centered, so coordinates are relative
  // to that container. We want the hat's bottom-center (the brim) to sit
  // on the orb's upper-right rim.
  //
  // Orb center sits at (size, size) in the container.
  // Upper-right rim (at ~30° above horizontal) ≈ (size + size*0.43, size - size*0.25).
  // We anchor the hat brim's CENTER there, then rotate the hat 15°
  // clockwise so it reads as "perched, slightly askew".
  const anchorX = size + size * 0.43
  const anchorY = size - size * 0.25

  return (
    <motion.div
      style={{
        position: 'absolute',
        // Place the hat so its bottom-center aligns with the anchor.
        left: anchorX - hatWidth / 2,
        top: anchorY - hatHeight,
        width: hatWidth,
        height: hatHeight,
        // Pivot for rotation = bottom-center of the hat (the brim).
        // That way the wiggle animation rotates around the perch point,
        // not the SVG's top-left.
        transformOrigin: '50% 100%',
        pointerEvents: 'none',
        // Don't intercept clicks meant for the avatar (App.tsx wires
        // onClick on the avatar wrapper for tap-to-wake).
      }}
      initial={{ y: -size * 0.8, opacity: 0, rotate: 15 }}
      animate={{
        y: 0,
        opacity: 1,
        // Drop-in then wiggle settle: overshoot one way, back the other,
        // land at the perched 15°.
        rotate: [15, 8, 22, 12, 15],
      }}
      transition={{
        y: { type: 'spring', stiffness: 220, damping: 14, delay: 0.05 },
        opacity: { duration: 0.25, delay: 0.05 },
        rotate: {
          duration: 0.9,
          delay: 0.35, // start the wiggle after the drop lands
          times: [0, 0.25, 0.55, 0.8, 1],
          ease: 'easeInOut',
        },
      }}
    >
      <svg
        width="100%"
        height="100%"
        viewBox="0 0 100 140"
        // role/aria — purely decorative, hidden from screen readers.
        aria-hidden="true"
        style={{ display: 'block', overflow: 'visible' }}
      >
        {/* Soft drop-shadow under the brim so the hat looks like it sits
            on the orb instead of floating above it. */}
        <ellipse
          cx="50"
          cy="128"
          rx="34"
          ry="4"
          fill="rgba(0, 0, 0, 0.18)"
        />

        {/* Cone body. Path: brim-left -> tip -> brim-right -> brim-curve.
            The slight curve on the brim line gives it 3D depth. */}
        <path
          d="M 14 124 Q 50 132 86 124 L 50 8 Z"
          fill={palette.cone}
          stroke={palette.outline}
          strokeWidth="1.2"
          strokeLinejoin="round"
        />

        {/* Cone inner shadow on the right side — gives volume. */}
        <path
          d="M 50 8 L 86 124 Q 68 128 50 128 Z"
          fill={palette.coneShadow}
          opacity="0.45"
        />

        {/* Diagonal stripes — wrap around the cone via curved paths so
            they feel like they hug a 3D shape, not a flat triangle.
            Three stripes spaced down the cone. */}
        <path
          d="M 28 90 Q 50 95 72 90"
          stroke={palette.stripe}
          strokeWidth="5"
          fill="none"
          strokeLinecap="round"
        />
        <path
          d="M 35 64 Q 50 68 65 64"
          stroke={palette.stripe}
          strokeWidth="4"
          fill="none"
          strokeLinecap="round"
        />
        <path
          d="M 42 38 Q 50 41 58 38"
          stroke={palette.stripe}
          strokeWidth="3"
          fill="none"
          strokeLinecap="round"
        />

        {/* Pom-pom on top. Two circles for highlight depth. */}
        <circle
          cx="50"
          cy="6"
          r="11"
          fill={palette.pom}
          stroke={palette.outline}
          strokeWidth="1"
        />
        <circle
          cx="46"
          cy="3"
          r="4"
          fill={palette.pomHighlight}
          opacity="0.8"
        />
      </svg>
    </motion.div>
  )
}
