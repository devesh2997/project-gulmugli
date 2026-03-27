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
      // Asymmetric brows — left raised HIGH (curious), right stays low and flat
      left_brow:  { type: 'path', d: 'M28 28 Q38 20, 48 26', strokeWidth: 1.4, opacity: 0.50 },
      right_brow: { type: 'path', d: 'M72 37 Q82 34, 92 38', strokeWidth: 1.2, opacity: 0.38 },
      // Eyes narrowed — half-closed arcs instead of open lines
      left_eye:   { type: 'path', d: 'M34 50 Q40 46, 46 50', strokeWidth: 1.4, opacity: 0.42 },
      right_eye:  { type: 'path', d: 'M74 50 Q80 47, 86 50', strokeWidth: 1.3, opacity: 0.40 },
      nose:       { type: 'line', x1: 60, y1: 60, x2: 58, y2: 67, strokeWidth: 0.8, opacity: 0.15 },
      // Pursed lips — small "hmm" shape, shifted right
      mouth:      { type: 'path', d: 'M50 80 Q58 77, 68 80', strokeWidth: 1.2, opacity: 0.30 },
    },
    glows: {
      left_eye_glow:  { cx: 40, cy: 48, r: 8, opacity: 0.04 },
      right_eye_glow: { cx: 80, cy: 48, r: 8, opacity: 0.04 },
      forehead_glow:  { cx: 55, cy: 18, r: 14, opacity: 0.06 },
      face_glow:      { cx: 60, cy: 62, r: 30, opacity: 0.03 },
    },
  },

  listening: {
    features: {
      // Brows raised HIGH — visible 10px shift from idle (y:38 → y:28)
      left_brow:  { type: 'path', d: 'M28 28 Q38 22, 48 27', strokeWidth: 1.4, opacity: 0.50 },
      right_brow: { type: 'path', d: 'M72 27 Q82 22, 92 28', strokeWidth: 1.4, opacity: 0.50 },
      // Eyes WIDE — tall arcs (open ovals) instead of flat lines
      left_eye:   { type: 'path', d: 'M33 53 Q36 44, 40 42 Q44 44, 47 53', strokeWidth: 1.4, opacity: 0.48 },
      right_eye:  { type: 'path', d: 'M73 53 Q76 44, 80 42 Q84 44, 87 53', strokeWidth: 1.4, opacity: 0.48 },
      // Pupil highlights — visible spark of attention
      left_eye_highlight:  { type: 'circle', cx: 40, cy: 47, r: 1.5, strokeWidth: 0, opacity: 0.15, fill: true },
      right_eye_highlight: { type: 'circle', cx: 80, cy: 47, r: 1.5, strokeWidth: 0, opacity: 0.15, fill: true },
      nose:       { type: 'line', x1: 60, y1: 60, x2: 58, y2: 67, strokeWidth: 0.8, opacity: 0.15 },
      // Mouth slightly open — welcoming parted lips
      mouth:      { type: 'path', d: 'M44 78 Q60 84, 76 78', strokeWidth: 1.2, opacity: 0.30 },
    },
    glows: {
      left_eye_glow:  { cx: 40, cy: 48, r: 8, opacity: 0.05 },
      right_eye_glow: { cx: 80, cy: 48, r: 8, opacity: 0.05 },
      left_ear_glow:  { cx: 10, cy: 55, r: 8, opacity: 0.06 },
      right_ear_glow: { cx: 110, cy: 55, r: 8, opacity: 0.06 },
      face_glow:      { cx: 60, cy: 60, r: 32, opacity: 0.04 },
    },
  },

  speaking: {
    features: {
      // Brows slightly animated — expressive during speech
      left_brow:  { type: 'path', d: 'M28 34 Q38 28, 48 33', strokeWidth: 1.3, opacity: 0.40 },
      right_brow: { type: 'path', d: 'M72 33 Q82 28, 92 34', strokeWidth: 1.3, opacity: 0.40 },
      // Eyes normal — gentle curves
      left_eye:   { type: 'path', d: 'M34 52 Q40 46, 46 52', strokeWidth: 1.3, opacity: 0.38 },
      right_eye:  { type: 'path', d: 'M74 52 Q80 46, 86 52', strokeWidth: 1.3, opacity: 0.38 },
      nose:       { type: 'line', x1: 60, y1: 60, x2: 58, y2: 67, strokeWidth: 0.8, opacity: 0.15 },
      // Mouth WIDE open — dramatic curve for speaking
      mouth:      { type: 'path', d: 'M40 77 Q60 94, 80 77', strokeWidth: 1.3, opacity: 0.35 },
    },
    glows: {
      left_eye_glow:  { cx: 40, cy: 50, r: 6, opacity: 0.03 },
      right_eye_glow: { cx: 80, cy: 50, r: 6, opacity: 0.03 },
      mouth_glow:     { cx: 60, cy: 84, r: 10, opacity: 0.04 },
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
