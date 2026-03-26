/**
 * Stroke face data for AvatarLight (Girlfriend personality).
 *
 * Each facial feature is an SVG stroke element (path, line, circle, ellipse).
 * Glow halos add warmth and emotion via soft radial light. This file is the
 * single source of truth for face geometry — the component only handles
 * rendering and animation.
 *
 * ViewBox: 0 0 120 120
 */

export interface StrokeFeature {
  type: 'path' | 'line' | 'circle' | 'ellipse'
  d?: string
  x1?: number; y1?: number; x2?: number; y2?: number
  cx?: number; cy?: number; r?: number
  rx?: number; ry?: number
  strokeWidth: number
  opacity: number
  fill?: boolean
}

export interface GlowFeature {
  cx: number; cy: number; r: number
  opacity: number
  color?: string
}

export interface LightFaceState {
  features: Record<string, StrokeFeature>
  glows: Record<string, GlowFeature>
}

// ─── State faces ────────────────────────────────────────────────────

export const lightFaces: Record<string, LightFaceState> = {
  idle: {
    features: {
      left_brow:  { type: 'path', d: 'M28 38 Q38 32, 48 36', strokeWidth: 1.3, opacity: 0.35 },
      right_brow: { type: 'path', d: 'M72 36 Q82 32, 92 38', strokeWidth: 1.3, opacity: 0.35 },
      left_eye:   { type: 'line', x1: 35, y1: 50, x2: 45, y2: 50, strokeWidth: 1.3, opacity: 0.35 },
      right_eye:  { type: 'line', x1: 75, y1: 50, x2: 85, y2: 50, strokeWidth: 1.3, opacity: 0.35 },
      nose:       { type: 'line', x1: 60, y1: 60, x2: 58, y2: 67, strokeWidth: 0.8, opacity: 0.15 },
      mouth:      { type: 'path', d: 'M46 80 Q60 86, 74 80', strokeWidth: 1.1, opacity: 0.25 },
    },
    glows: {
      left_eye_glow:  { cx: 40, cy: 50, r: 6, opacity: 0.03 },
      right_eye_glow: { cx: 80, cy: 50, r: 6, opacity: 0.03 },
      face_glow:      { cx: 60, cy: 62, r: 30, opacity: 0.03 },
    },
  },

  thinking: {
    features: {
      left_brow:  { type: 'path', d: 'M28 33 Q38 27, 48 31', strokeWidth: 1.3, opacity: 0.45 },
      right_brow: { type: 'path', d: 'M72 31 Q82 27, 92 33', strokeWidth: 1.3, opacity: 0.45 },
      left_eye:   { type: 'line', x1: 34, y1: 48, x2: 46, y2: 48, strokeWidth: 1.3, opacity: 0.45 },
      right_eye:  { type: 'line', x1: 74, y1: 48, x2: 86, y2: 48, strokeWidth: 1.3, opacity: 0.45 },
      nose:       { type: 'line', x1: 60, y1: 60, x2: 58, y2: 67, strokeWidth: 0.8, opacity: 0.15 },
      mouth:      { type: 'ellipse', cx: 60, cy: 80, rx: 6, ry: 5, strokeWidth: 1.1, opacity: 0.22 },
    },
    glows: {
      left_eye_glow:  { cx: 40, cy: 48, r: 8, opacity: 0.04 },
      right_eye_glow: { cx: 80, cy: 48, r: 8, opacity: 0.04 },
      forehead_glow:  { cx: 60, cy: 22, r: 10, opacity: 0.05 },
      face_glow:      { cx: 60, cy: 62, r: 30, opacity: 0.03 },
    },
  },

  listening: {
    features: {
      left_brow:  { type: 'path', d: 'M28 35 Q38 30, 48 34', strokeWidth: 1.3, opacity: 0.40 },
      right_brow: { type: 'path', d: 'M72 34 Q82 30, 92 35', strokeWidth: 1.3, opacity: 0.40 },
      left_eye:   { type: 'line', x1: 35, y1: 50, x2: 45, y2: 50, strokeWidth: 1.3, opacity: 0.40 },
      right_eye:  { type: 'line', x1: 75, y1: 50, x2: 85, y2: 50, strokeWidth: 1.3, opacity: 0.40 },
      left_eye_highlight:  { type: 'circle', cx: 41, cy: 49, r: 0.8, strokeWidth: 0, opacity: 0.08, fill: true },
      right_eye_highlight: { type: 'circle', cx: 81, cy: 49, r: 0.8, strokeWidth: 0, opacity: 0.08, fill: true },
      nose:       { type: 'line', x1: 60, y1: 60, x2: 58, y2: 67, strokeWidth: 0.8, opacity: 0.15 },
      mouth:      { type: 'path', d: 'M46 80 Q60 83, 74 80', strokeWidth: 1.1, opacity: 0.22 },
    },
    glows: {
      left_eye_glow:  { cx: 40, cy: 50, r: 6, opacity: 0.03 },
      right_eye_glow: { cx: 80, cy: 50, r: 6, opacity: 0.03 },
      left_ear_glow:  { cx: 12, cy: 55, r: 6, opacity: 0.04 },
      right_ear_glow: { cx: 108, cy: 55, r: 6, opacity: 0.04 },
      face_glow:      { cx: 60, cy: 62, r: 30, opacity: 0.03 },
    },
  },

  speaking: {
    features: {
      left_brow:  { type: 'path', d: 'M28 38 Q38 32, 48 36', strokeWidth: 1.3, opacity: 0.35 },
      right_brow: { type: 'path', d: 'M72 36 Q82 32, 92 38', strokeWidth: 1.3, opacity: 0.35 },
      left_eye:   { type: 'line', x1: 35, y1: 50, x2: 45, y2: 50, strokeWidth: 1.3, opacity: 0.35 },
      right_eye:  { type: 'line', x1: 75, y1: 50, x2: 85, y2: 50, strokeWidth: 1.3, opacity: 0.35 },
      nose:       { type: 'line', x1: 60, y1: 60, x2: 58, y2: 67, strokeWidth: 0.8, opacity: 0.15 },
      mouth:      { type: 'path', d: 'M42 79 Q60 90, 78 79', strokeWidth: 1.1, opacity: 0.30 },
    },
    glows: {
      left_eye_glow:  { cx: 40, cy: 50, r: 6, opacity: 0.03 },
      right_eye_glow: { cx: 80, cy: 50, r: 6, opacity: 0.03 },
      face_glow:      { cx: 60, cy: 62, r: 30, opacity: 0.04 },
    },
  },

  sleeping: {
    features: {
      left_brow:  { type: 'path', d: 'M28 38 Q38 32, 48 36', strokeWidth: 1.3, opacity: 0.08 },
      right_brow: { type: 'path', d: 'M72 36 Q82 32, 92 38', strokeWidth: 1.3, opacity: 0.08 },
      left_eye:   { type: 'line', x1: 35, y1: 50, x2: 45, y2: 50, strokeWidth: 1.3, opacity: 0.10 },
      right_eye:  { type: 'line', x1: 75, y1: 50, x2: 85, y2: 50, strokeWidth: 1.3, opacity: 0.10 },
      nose:       { type: 'line', x1: 60, y1: 60, x2: 58, y2: 67, strokeWidth: 0.8, opacity: 0.06 },
      mouth:      { type: 'path', d: 'M46 80 Q60 86, 74 80', strokeWidth: 1.1, opacity: 0.08 },
    },
    glows: {
      face_glow: { cx: 60, cy: 62, r: 30, opacity: 0.01 },
    },
  },
}

// ─── Mood overlays ──────────────────────────────────────────────────

export interface LightMoodOverlay {
  features?: Record<string, StrokeFeature>
  glows?: Record<string, GlowFeature>
}

export const lightMoodOverlays: Record<string, LightMoodOverlay> = {
  shy: {
    features: {
      left_eye:  { type: 'path', d: 'M33 52 Q40 45, 47 52', strokeWidth: 1.3, opacity: 0.35 },
      right_eye: { type: 'path', d: 'M73 52 Q80 45, 87 52', strokeWidth: 1.3, opacity: 0.35 },
    },
    glows: {
      blush_left:  { cx: 26, cy: 62, r: 12, opacity: 0.06, color: '#ff6b8a' },
      blush_right: { cx: 94, cy: 62, r: 12, opacity: 0.06, color: '#ff6b8a' },
    },
  },
  happy: {
    features: {
      left_eye:  { type: 'path', d: 'M33 52 Q40 45, 47 52', strokeWidth: 1.3, opacity: 0.40 },
      right_eye: { type: 'path', d: 'M73 52 Q80 45, 87 52', strokeWidth: 1.3, opacity: 0.40 },
      mouth:     { type: 'path', d: 'M42 78 Q60 92, 78 78', strokeWidth: 1.2, opacity: 0.30 },
    },
  },
}
