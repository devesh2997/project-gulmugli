/**
 * Pixel face data for AvatarPixel (Devesh personality).
 *
 * Each facial feature is an array of { x, y, opacity } on a 32x32 grid.
 * This file is the single source of truth for face geometry — the component
 * only handles rendering and animation.
 *
 * Design principle: states should be DRAMATICALLY different from each other.
 * Pixel positions should shift visibly, not just change opacity.
 */

export type PixelData = { x: number; y: number; opacity: number }[]

export type FaceFeature =
  | 'left_brow'
  | 'right_brow'
  | 'left_eye'
  | 'right_eye'
  | 'nose'
  | 'mouth'

export type FaceState = Record<FaceFeature, PixelData>

/**
 * Alternate mouth frame for speaking animation.
 */
export const speakingMouthClosed: PixelData = [
  { x: 13, y: 22, opacity: 0.7 }, { x: 14, y: 22, opacity: 0.7 },
  { x: 15, y: 22, opacity: 0.7 }, { x: 16, y: 22, opacity: 0.7 },
  { x: 17, y: 22, opacity: 0.7 }, { x: 18, y: 22, opacity: 0.7 },
]

// ─── State faces ────────────────────────────────────────────────────

export const pixelFaces: Record<string, FaceState> = {
  // ── IDLE: Calm, relaxed, neutral ──
  idle: {
    left_brow: [
      { x: 7, y: 10, opacity: 0.5 },
      { x: 8, y: 9, opacity: 0.6 },
      { x: 9, y: 9, opacity: 0.65 },
      { x: 10, y: 9, opacity: 0.65 },
      { x: 11, y: 9, opacity: 0.6 },
      { x: 12, y: 10, opacity: 0.5 },
    ],
    right_brow: [
      { x: 19, y: 10, opacity: 0.5 },
      { x: 20, y: 9, opacity: 0.6 },
      { x: 21, y: 9, opacity: 0.65 },
      { x: 22, y: 9, opacity: 0.65 },
      { x: 23, y: 9, opacity: 0.6 },
      { x: 24, y: 10, opacity: 0.5 },
    ],
    left_eye: [
      { x: 8, y: 13, opacity: 0.65 }, { x: 9, y: 13, opacity: 0.7 },
      { x: 10, y: 13, opacity: 0.7 }, { x: 11, y: 13, opacity: 0.65 },
      { x: 8, y: 14, opacity: 0.45 }, { x: 9, y: 14, opacity: 0.5 },
      { x: 10, y: 14, opacity: 0.5 }, { x: 11, y: 14, opacity: 0.45 },
    ],
    right_eye: [
      { x: 20, y: 13, opacity: 0.65 }, { x: 21, y: 13, opacity: 0.7 },
      { x: 22, y: 13, opacity: 0.7 }, { x: 23, y: 13, opacity: 0.65 },
      { x: 20, y: 14, opacity: 0.45 }, { x: 21, y: 14, opacity: 0.5 },
      { x: 22, y: 14, opacity: 0.5 }, { x: 23, y: 14, opacity: 0.45 },
    ],
    nose: [
      { x: 15, y: 17, opacity: 0.2 },
      { x: 16, y: 18, opacity: 0.2 },
    ],
    // Clear upward smile — corners UP, center flat
    mouth: [
      { x: 12, y: 21, opacity: 0.35 },
      { x: 13, y: 22, opacity: 0.5 }, { x: 14, y: 22, opacity: 0.55 },
      { x: 15, y: 22, opacity: 0.55 }, { x: 16, y: 22, opacity: 0.55 },
      { x: 17, y: 22, opacity: 0.55 }, { x: 18, y: 22, opacity: 0.5 },
      { x: 19, y: 21, opacity: 0.35 },
    ],
  },

  // ── LISTENING: Alert, attentive — eyes WIDE open, brows HIGH ──
  listening: {
    // Brows raised HIGH — y:6 vs idle y:9, very visible shift
    left_brow: [
      { x: 7, y: 7, opacity: 0.75 },
      { x: 8, y: 6, opacity: 0.85 },
      { x: 9, y: 6, opacity: 0.9 },
      { x: 10, y: 6, opacity: 0.9 },
      { x: 11, y: 6, opacity: 0.85 },
      { x: 12, y: 7, opacity: 0.75 },
    ],
    right_brow: [
      { x: 19, y: 7, opacity: 0.75 },
      { x: 20, y: 6, opacity: 0.85 },
      { x: 21, y: 6, opacity: 0.9 },
      { x: 22, y: 6, opacity: 0.9 },
      { x: 23, y: 6, opacity: 0.85 },
      { x: 24, y: 7, opacity: 0.75 },
    ],
    // Eyes 3 rows tall (vs 2 in idle) — WIDE open
    left_eye: [
      { x: 8, y: 11, opacity: 0.7 }, { x: 9, y: 11, opacity: 0.8 },
      { x: 10, y: 11, opacity: 0.8 }, { x: 11, y: 11, opacity: 0.7 },
      { x: 8, y: 12, opacity: 0.85 }, { x: 9, y: 12, opacity: 0.9 },
      { x: 10, y: 12, opacity: 0.9 }, { x: 11, y: 12, opacity: 0.85 },
      { x: 8, y: 13, opacity: 0.7 }, { x: 9, y: 13, opacity: 0.8 },
      { x: 10, y: 13, opacity: 0.8 }, { x: 11, y: 13, opacity: 0.7 },
    ],
    right_eye: [
      { x: 20, y: 11, opacity: 0.7 }, { x: 21, y: 11, opacity: 0.8 },
      { x: 22, y: 11, opacity: 0.8 }, { x: 23, y: 11, opacity: 0.7 },
      { x: 20, y: 12, opacity: 0.85 }, { x: 21, y: 12, opacity: 0.9 },
      { x: 22, y: 12, opacity: 0.9 }, { x: 23, y: 12, opacity: 0.85 },
      { x: 20, y: 13, opacity: 0.7 }, { x: 21, y: 13, opacity: 0.8 },
      { x: 22, y: 13, opacity: 0.8 }, { x: 23, y: 13, opacity: 0.7 },
    ],
    nose: [
      { x: 15, y: 17, opacity: 0.25 },
      { x: 16, y: 18, opacity: 0.25 },
    ],
    // Slightly parted — ready to respond
    mouth: [
      { x: 13, y: 22, opacity: 0.5 }, { x: 14, y: 22, opacity: 0.55 },
      { x: 15, y: 22, opacity: 0.55 }, { x: 16, y: 22, opacity: 0.55 },
      { x: 17, y: 22, opacity: 0.55 }, { x: 18, y: 22, opacity: 0.5 },
    ],
  },

  // ── THINKING: Concentrated — one brow up, eyes narrowed, pursed lips ──
  thinking: {
    // LEFT brow raised high (curious/skeptical), RIGHT stays low
    left_brow: [
      { x: 7, y: 7, opacity: 0.8 },
      { x: 8, y: 6, opacity: 0.85 },
      { x: 9, y: 5, opacity: 0.9 },
      { x: 10, y: 5, opacity: 0.9 },
      { x: 11, y: 6, opacity: 0.85 },
      { x: 12, y: 7, opacity: 0.8 },
    ],
    right_brow: [
      { x: 19, y: 10, opacity: 0.7 },
      { x: 20, y: 9, opacity: 0.75 },
      { x: 21, y: 9, opacity: 0.8 },
      { x: 22, y: 9, opacity: 0.8 },
      { x: 23, y: 9, opacity: 0.75 },
      { x: 24, y: 10, opacity: 0.7 },
    ],
    // Eyes slightly narrowed — squinting in thought
    left_eye: [
      { x: 8, y: 13, opacity: 0.75 }, { x: 9, y: 13, opacity: 0.85 },
      { x: 10, y: 13, opacity: 0.85 }, { x: 11, y: 13, opacity: 0.75 },
    ],
    right_eye: [
      { x: 20, y: 13, opacity: 0.75 }, { x: 21, y: 13, opacity: 0.85 },
      { x: 22, y: 13, opacity: 0.85 }, { x: 23, y: 13, opacity: 0.75 },
    ],
    nose: [
      { x: 15, y: 17, opacity: 0.25 },
      { x: 16, y: 18, opacity: 0.25 },
    ],
    // Pursed/flat — concentrated, NOT an "O" shape
    mouth: [
      { x: 14, y: 22, opacity: 0.55 }, { x: 15, y: 22, opacity: 0.6 },
      { x: 16, y: 22, opacity: 0.6 }, { x: 17, y: 22, opacity: 0.55 },
    ],
  },

  // ── SPEAKING: Animated — normal brows, open mouth ──
  speaking: {
    left_brow: [
      { x: 7, y: 9, opacity: 0.65 },
      { x: 8, y: 8, opacity: 0.7 },
      { x: 9, y: 8, opacity: 0.75 },
      { x: 10, y: 8, opacity: 0.75 },
      { x: 11, y: 8, opacity: 0.7 },
      { x: 12, y: 9, opacity: 0.65 },
    ],
    right_brow: [
      { x: 19, y: 9, opacity: 0.65 },
      { x: 20, y: 8, opacity: 0.7 },
      { x: 21, y: 8, opacity: 0.75 },
      { x: 22, y: 8, opacity: 0.75 },
      { x: 23, y: 8, opacity: 0.7 },
      { x: 24, y: 9, opacity: 0.65 },
    ],
    left_eye: [
      { x: 8, y: 12, opacity: 0.75 }, { x: 9, y: 12, opacity: 0.85 },
      { x: 10, y: 12, opacity: 0.85 }, { x: 11, y: 12, opacity: 0.75 },
      { x: 8, y: 13, opacity: 0.6 }, { x: 9, y: 13, opacity: 0.7 },
      { x: 10, y: 13, opacity: 0.7 }, { x: 11, y: 13, opacity: 0.6 },
    ],
    right_eye: [
      { x: 20, y: 12, opacity: 0.75 }, { x: 21, y: 12, opacity: 0.85 },
      { x: 22, y: 12, opacity: 0.85 }, { x: 23, y: 12, opacity: 0.75 },
      { x: 20, y: 13, opacity: 0.6 }, { x: 21, y: 13, opacity: 0.7 },
      { x: 22, y: 13, opacity: 0.7 }, { x: 23, y: 13, opacity: 0.6 },
    ],
    nose: [
      { x: 15, y: 17, opacity: 0.25 },
      { x: 16, y: 18, opacity: 0.25 },
    ],
    // Wide open mouth — 2 rows, wider than idle
    mouth: [
      { x: 12, y: 21, opacity: 0.65 }, { x: 13, y: 21, opacity: 0.7 },
      { x: 14, y: 21, opacity: 0.75 }, { x: 15, y: 21, opacity: 0.75 },
      { x: 16, y: 21, opacity: 0.75 }, { x: 17, y: 21, opacity: 0.75 },
      { x: 18, y: 21, opacity: 0.7 }, { x: 19, y: 21, opacity: 0.65 },
      { x: 12, y: 22, opacity: 0.55 }, { x: 13, y: 22, opacity: 0.6 },
      { x: 14, y: 22, opacity: 0.65 }, { x: 15, y: 22, opacity: 0.65 },
      { x: 16, y: 22, opacity: 0.65 }, { x: 17, y: 22, opacity: 0.65 },
      { x: 18, y: 22, opacity: 0.6 }, { x: 19, y: 22, opacity: 0.55 },
    ],
  },

  // ── SLEEPING: Minimal — just a few dim status pixels ──
  sleeping: {
    left_brow: [],
    right_brow: [],
    left_eye: [],
    right_eye: [],
    nose: [],
    mouth: [
      { x: 15, y: 15, opacity: 0.15 },
      { x: 16, y: 15, opacity: 0.15 },
      { x: 15, y: 16, opacity: 0.15 },
    ],
  },
}

// ─── Mood overlays (additive on top of state) ───────────────────────

export type MoodFeature = FaceFeature | 'blush_left' | 'blush_right'

export const pixelMoodOverlays: Record<string, Partial<Record<MoodFeature, PixelData>>> = {
  shy: {
    blush_left: [
      { x: 5, y: 15, opacity: 0.4 }, { x: 6, y: 15, opacity: 0.5 },
      { x: 7, y: 15, opacity: 0.4 }, { x: 5, y: 16, opacity: 0.3 },
      { x: 6, y: 16, opacity: 0.4 }, { x: 7, y: 16, opacity: 0.3 },
    ],
    blush_right: [
      { x: 24, y: 15, opacity: 0.4 }, { x: 25, y: 15, opacity: 0.5 },
      { x: 26, y: 15, opacity: 0.4 }, { x: 24, y: 16, opacity: 0.3 },
      { x: 25, y: 16, opacity: 0.4 }, { x: 26, y: 16, opacity: 0.3 },
    ],
    // Happy squint eyes
    left_eye: [
      { x: 8, y: 13, opacity: 0.55 }, { x: 9, y: 12, opacity: 0.5 },
      { x: 10, y: 12, opacity: 0.5 }, { x: 11, y: 13, opacity: 0.55 },
    ],
    right_eye: [
      { x: 20, y: 13, opacity: 0.55 }, { x: 21, y: 12, opacity: 0.5 },
      { x: 22, y: 12, opacity: 0.5 }, { x: 23, y: 13, opacity: 0.55 },
    ],
  },
  happy: {
    // Upward arc eyes (happy squint)
    left_eye: [
      { x: 8, y: 14, opacity: 0.6 }, { x: 9, y: 13, opacity: 0.55 },
      { x: 10, y: 13, opacity: 0.55 }, { x: 11, y: 14, opacity: 0.6 },
    ],
    right_eye: [
      { x: 20, y: 14, opacity: 0.6 }, { x: 21, y: 13, opacity: 0.55 },
      { x: 22, y: 13, opacity: 0.55 }, { x: 23, y: 14, opacity: 0.6 },
    ],
    // Big wide smile
    mouth: [
      { x: 11, y: 22, opacity: 0.45 },
      { x: 12, y: 23, opacity: 0.55 }, { x: 13, y: 23, opacity: 0.6 },
      { x: 14, y: 23, opacity: 0.65 }, { x: 15, y: 24, opacity: 0.65 },
      { x: 16, y: 24, opacity: 0.65 }, { x: 17, y: 23, opacity: 0.65 },
      { x: 18, y: 23, opacity: 0.6 }, { x: 19, y: 23, opacity: 0.55 },
      { x: 20, y: 22, opacity: 0.45 },
    ],
  },
}
