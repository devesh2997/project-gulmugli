/**
 * Pixel face data for AvatarPixel (Devesh personality).
 *
 * Each facial feature is an array of { x, y, opacity } on a 32x32 grid.
 * This file is the single source of truth for face geometry — the component
 * only handles rendering and animation.
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

// ─── State faces ────────────────────────────────────────────────────

export const pixelFaces: Record<string, FaceState> = {
  idle: {
    left_brow: [
      { x: 7, y: 10, opacity: 0.5 },
      { x: 8, y: 9, opacity: 0.55 },
      { x: 9, y: 9, opacity: 0.6 },
      { x: 10, y: 9, opacity: 0.6 },
      { x: 11, y: 9, opacity: 0.55 },
      { x: 12, y: 10, opacity: 0.5 },
    ],
    right_brow: [
      { x: 19, y: 10, opacity: 0.5 },
      { x: 20, y: 9, opacity: 0.55 },
      { x: 21, y: 9, opacity: 0.6 },
      { x: 22, y: 9, opacity: 0.6 },
      { x: 23, y: 9, opacity: 0.55 },
      { x: 24, y: 10, opacity: 0.5 },
    ],
    left_eye: [
      { x: 8, y: 13, opacity: 0.65 }, { x: 9, y: 13, opacity: 0.65 },
      { x: 10, y: 13, opacity: 0.65 }, { x: 11, y: 13, opacity: 0.65 },
      { x: 8, y: 14, opacity: 0.5 }, { x: 9, y: 14, opacity: 0.5 },
      { x: 10, y: 14, opacity: 0.5 }, { x: 11, y: 14, opacity: 0.5 },
    ],
    right_eye: [
      { x: 20, y: 13, opacity: 0.65 }, { x: 21, y: 13, opacity: 0.65 },
      { x: 22, y: 13, opacity: 0.65 }, { x: 23, y: 13, opacity: 0.65 },
      { x: 20, y: 14, opacity: 0.5 }, { x: 21, y: 14, opacity: 0.5 },
      { x: 22, y: 14, opacity: 0.5 }, { x: 23, y: 14, opacity: 0.5 },
    ],
    nose: [
      { x: 15, y: 17, opacity: 0.2 },
      { x: 16, y: 18, opacity: 0.2 },
    ],
    mouth: [
      { x: 12, y: 22, opacity: 0.5 },
      { x: 13, y: 23, opacity: 0.55 }, { x: 14, y: 23, opacity: 0.55 },
      { x: 15, y: 23, opacity: 0.55 }, { x: 16, y: 23, opacity: 0.55 },
      { x: 17, y: 23, opacity: 0.55 }, { x: 18, y: 23, opacity: 0.55 },
      { x: 19, y: 22, opacity: 0.5 },
    ],
  },

  thinking: {
    left_brow: [
      { x: 7, y: 8, opacity: 0.65 },
      { x: 8, y: 7, opacity: 0.65 },
      { x: 9, y: 7, opacity: 0.65 },
      { x: 10, y: 7, opacity: 0.65 },
      { x: 11, y: 7, opacity: 0.65 },
      { x: 12, y: 8, opacity: 0.65 },
    ],
    right_brow: [
      { x: 19, y: 8, opacity: 0.65 },
      { x: 20, y: 7, opacity: 0.65 },
      { x: 21, y: 7, opacity: 0.65 },
      { x: 22, y: 7, opacity: 0.65 },
      { x: 23, y: 7, opacity: 0.65 },
      { x: 24, y: 8, opacity: 0.65 },
    ],
    left_eye: [
      { x: 8, y: 12, opacity: 0.7 }, { x: 9, y: 12, opacity: 0.7 },
      { x: 10, y: 12, opacity: 0.7 }, { x: 11, y: 12, opacity: 0.7 },
      { x: 8, y: 13, opacity: 0.6 }, { x: 9, y: 13, opacity: 0.6 },
      { x: 10, y: 13, opacity: 0.6 }, { x: 11, y: 13, opacity: 0.6 },
      { x: 8, y: 14, opacity: 0.5 }, { x: 9, y: 14, opacity: 0.5 },
      { x: 10, y: 14, opacity: 0.5 }, { x: 11, y: 14, opacity: 0.5 },
    ],
    right_eye: [
      { x: 20, y: 12, opacity: 0.7 }, { x: 21, y: 12, opacity: 0.7 },
      { x: 22, y: 12, opacity: 0.7 }, { x: 23, y: 12, opacity: 0.7 },
      { x: 20, y: 13, opacity: 0.6 }, { x: 21, y: 13, opacity: 0.6 },
      { x: 22, y: 13, opacity: 0.6 }, { x: 23, y: 13, opacity: 0.6 },
      { x: 20, y: 14, opacity: 0.5 }, { x: 21, y: 14, opacity: 0.5 },
      { x: 22, y: 14, opacity: 0.5 }, { x: 23, y: 14, opacity: 0.5 },
    ],
    nose: [
      { x: 15, y: 17, opacity: 0.2 },
      { x: 16, y: 18, opacity: 0.2 },
    ],
    mouth: [
      { x: 14, y: 22, opacity: 0.5 },
      { x: 15, y: 21, opacity: 0.55 }, { x: 16, y: 21, opacity: 0.55 },
      { x: 17, y: 22, opacity: 0.5 },
      { x: 15, y: 23, opacity: 0.5 }, { x: 16, y: 23, opacity: 0.5 },
    ],
  },

  listening: {
    left_brow: [
      { x: 8, y: 8, opacity: 0.55 },
      { x: 9, y: 8, opacity: 0.6 },
      { x: 10, y: 8, opacity: 0.6 },
      { x: 11, y: 8, opacity: 0.55 },
    ],
    right_brow: [
      { x: 20, y: 8, opacity: 0.55 },
      { x: 21, y: 8, opacity: 0.6 },
      { x: 22, y: 8, opacity: 0.6 },
      { x: 23, y: 8, opacity: 0.55 },
    ],
    left_eye: [
      { x: 8, y: 13, opacity: 0.65 }, { x: 9, y: 13, opacity: 0.65 },
      { x: 10, y: 13, opacity: 0.65 }, { x: 11, y: 13, opacity: 0.65 },
      { x: 8, y: 14, opacity: 0.6 }, { x: 9, y: 14, opacity: 0.6 },
      { x: 10, y: 14, opacity: 0.6 }, { x: 11, y: 14, opacity: 0.6 },
    ],
    right_eye: [
      { x: 20, y: 13, opacity: 0.65 }, { x: 21, y: 13, opacity: 0.65 },
      { x: 22, y: 13, opacity: 0.65 }, { x: 23, y: 13, opacity: 0.65 },
      { x: 20, y: 14, opacity: 0.6 }, { x: 21, y: 14, opacity: 0.6 },
      { x: 22, y: 14, opacity: 0.6 }, { x: 23, y: 14, opacity: 0.6 },
    ],
    nose: [
      { x: 15, y: 17, opacity: 0.2 },
      { x: 16, y: 18, opacity: 0.2 },
    ],
    mouth: [
      { x: 13, y: 22, opacity: 0.5 }, { x: 14, y: 22, opacity: 0.5 },
      { x: 15, y: 22, opacity: 0.5 }, { x: 16, y: 22, opacity: 0.5 },
      { x: 17, y: 22, opacity: 0.5 }, { x: 18, y: 22, opacity: 0.5 },
    ],
  },

  speaking: {
    left_brow: [
      { x: 7, y: 10, opacity: 0.5 },
      { x: 8, y: 9, opacity: 0.55 },
      { x: 9, y: 9, opacity: 0.6 },
      { x: 10, y: 9, opacity: 0.6 },
      { x: 11, y: 9, opacity: 0.55 },
      { x: 12, y: 10, opacity: 0.5 },
    ],
    right_brow: [
      { x: 19, y: 10, opacity: 0.5 },
      { x: 20, y: 9, opacity: 0.55 },
      { x: 21, y: 9, opacity: 0.6 },
      { x: 22, y: 9, opacity: 0.6 },
      { x: 23, y: 9, opacity: 0.55 },
      { x: 24, y: 10, opacity: 0.5 },
    ],
    left_eye: [
      { x: 8, y: 13, opacity: 0.65 }, { x: 9, y: 13, opacity: 0.65 },
      { x: 10, y: 13, opacity: 0.65 }, { x: 11, y: 13, opacity: 0.65 },
      { x: 8, y: 14, opacity: 0.5 }, { x: 9, y: 14, opacity: 0.5 },
      { x: 10, y: 14, opacity: 0.5 }, { x: 11, y: 14, opacity: 0.5 },
    ],
    right_eye: [
      { x: 20, y: 13, opacity: 0.65 }, { x: 21, y: 13, opacity: 0.65 },
      { x: 22, y: 13, opacity: 0.65 }, { x: 23, y: 13, opacity: 0.65 },
      { x: 20, y: 14, opacity: 0.5 }, { x: 21, y: 14, opacity: 0.5 },
      { x: 22, y: 14, opacity: 0.5 }, { x: 23, y: 14, opacity: 0.5 },
    ],
    nose: [
      { x: 15, y: 17, opacity: 0.2 },
      { x: 16, y: 18, opacity: 0.2 },
    ],
    mouth: [
      { x: 11, y: 22, opacity: 0.5 }, { x: 12, y: 22, opacity: 0.55 },
      { x: 13, y: 22, opacity: 0.55 }, { x: 14, y: 22, opacity: 0.55 },
      { x: 15, y: 22, opacity: 0.55 }, { x: 16, y: 22, opacity: 0.55 },
      { x: 17, y: 22, opacity: 0.55 }, { x: 18, y: 22, opacity: 0.55 },
      { x: 19, y: 22, opacity: 0.55 }, { x: 20, y: 22, opacity: 0.5 },
      { x: 12, y: 23, opacity: 0.45 }, { x: 13, y: 23, opacity: 0.45 },
      { x: 14, y: 23, opacity: 0.45 }, { x: 15, y: 23, opacity: 0.45 },
      { x: 16, y: 23, opacity: 0.45 }, { x: 17, y: 23, opacity: 0.45 },
      { x: 18, y: 23, opacity: 0.45 }, { x: 19, y: 23, opacity: 0.45 },
    ],
  },

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
    left_eye: [
      { x: 8, y: 13, opacity: 0.55 }, { x: 9, y: 13, opacity: 0.6 },
      { x: 10, y: 13, opacity: 0.6 }, { x: 11, y: 13, opacity: 0.55 },
    ],
    right_eye: [
      { x: 20, y: 13, opacity: 0.55 }, { x: 21, y: 13, opacity: 0.6 },
      { x: 22, y: 13, opacity: 0.6 }, { x: 23, y: 13, opacity: 0.55 },
    ],
  },
  happy: {
    left_eye: [
      { x: 8, y: 13, opacity: 0.6 }, { x: 9, y: 12, opacity: 0.55 },
      { x: 10, y: 12, opacity: 0.55 }, { x: 11, y: 13, opacity: 0.6 },
    ],
    right_eye: [
      { x: 20, y: 13, opacity: 0.6 }, { x: 21, y: 12, opacity: 0.55 },
      { x: 22, y: 12, opacity: 0.55 }, { x: 23, y: 13, opacity: 0.6 },
    ],
    mouth: [
      { x: 11, y: 22, opacity: 0.5 },
      { x: 12, y: 23, opacity: 0.55 }, { x: 13, y: 23, opacity: 0.55 },
      { x: 14, y: 23, opacity: 0.55 }, { x: 15, y: 23, opacity: 0.55 },
      { x: 16, y: 23, opacity: 0.55 }, { x: 17, y: 23, opacity: 0.55 },
      { x: 18, y: 23, opacity: 0.55 }, { x: 19, y: 23, opacity: 0.55 },
      { x: 20, y: 22, opacity: 0.5 },
    ],
  },
}
