/**
 * Stroke face data for AvatarCaricature (Chandler personality).
 *
 * A minimal line-art caricature of Chandler Bing — the MOST detailed of all
 * four avatar variants but still just strokes. Like a quick artist's sketch:
 * messy side-parted hair, expressive brows, sardonic narrow eyes, and THE
 * signature half-smirk with one corner up.
 *
 * ViewBox: 0 0 120 120
 */

import type { StrokeFeature, GlowFeature } from './lightFaces'

export interface ChandlerFaceState {
  features: Record<string, StrokeFeature>
  glows: Record<string, GlowFeature>
}

export interface ChandlerMoodOverlay {
  features?: Record<string, StrokeFeature>
  glows?: Record<string, GlowFeature>
}

// ─── State faces ────────────────────────────────────────────────────

export const chandlerFaces: Record<string, ChandlerFaceState> = {
  idle: {
    features: {
      // Hair — messy, side-parted (his left), 90s volume
      hair_top:     { type: 'path', d: 'M35 18 Q50 8, 68 14 Q78 17, 85 20', strokeWidth: 1.8, opacity: 0.35 },
      hair_part:    { type: 'path', d: 'M52 12 Q54 18, 53 24', strokeWidth: 1.2, opacity: 0.25 },
      hair_left:    { type: 'path', d: 'M35 18 Q30 22, 28 30', strokeWidth: 1.5, opacity: 0.30 },

      // Eyebrows — strong, expressive, primary emotion tool
      left_brow:    { type: 'path', d: 'M30 38 Q40 32, 50 36', strokeWidth: 1.8, opacity: 0.45 },
      right_brow:   { type: 'path', d: 'M70 35 Q80 31, 90 37', strokeWidth: 1.8, opacity: 0.45 },

      // Eyes — slightly narrow, sardonic squint
      left_eye:     { type: 'path', d: 'M34 48 Q40 44, 48 48', strokeWidth: 1.5, opacity: 0.40 },
      right_eye:    { type: 'path', d: 'M72 47 Q80 43, 88 47', strokeWidth: 1.5, opacity: 0.40 },

      // Nose — straight, two strokes (bridge + tip)
      nose_bridge:  { type: 'line', x1: 60, y1: 54, x2: 59, y2: 65, strokeWidth: 1.0, opacity: 0.20 },
      nose_tip:     { type: 'path', d: 'M56 65 Q59 68, 63 65', strokeWidth: 1.0, opacity: 0.22 },

      // Mouth — THE SMIRK: right corner curves up more than the left
      mouth:        { type: 'path', d: 'M42 80 Q52 83, 60 82 Q70 80, 78 76', strokeWidth: 1.6, opacity: 0.40 },

      // Jawline — angular, defined
      jaw_left:     { type: 'path', d: 'M26 42 Q24 60, 30 78 Q38 90, 50 94', strokeWidth: 1.2, opacity: 0.18 },
      jaw_right:    { type: 'path', d: 'M94 42 Q96 60, 90 78 Q82 90, 70 94', strokeWidth: 1.2, opacity: 0.18 },
    },
    glows: {
      left_eye_glow:  { cx: 41, cy: 47, r: 7, opacity: 0.04 },
      right_eye_glow: { cx: 80, cy: 46, r: 7, opacity: 0.04 },
      face_glow:      { cx: 60, cy: 60, r: 32, opacity: 0.04 },
    },
  },

  thinking: {
    features: {
      hair_top:     { type: 'path', d: 'M35 18 Q50 8, 68 14 Q78 17, 85 20', strokeWidth: 1.8, opacity: 0.35 },
      hair_part:    { type: 'path', d: 'M52 12 Q54 18, 53 24', strokeWidth: 1.2, opacity: 0.25 },
      hair_left:    { type: 'path', d: 'M35 18 Q30 22, 28 30', strokeWidth: 1.5, opacity: 0.30 },

      // Skeptical Chandler: left brow way UP, right drops slightly
      left_brow:    { type: 'path', d: 'M30 30 Q40 23, 50 28', strokeWidth: 2.0, opacity: 0.55 },
      right_brow:   { type: 'path', d: 'M70 37 Q80 34, 90 39', strokeWidth: 1.8, opacity: 0.45 },

      // Eyes slightly wider — the skeptical stare
      left_eye:     { type: 'path', d: 'M33 47 Q40 41, 49 47', strokeWidth: 1.5, opacity: 0.45 },
      right_eye:    { type: 'path', d: 'M71 46 Q80 41, 89 46', strokeWidth: 1.5, opacity: 0.45 },

      nose_bridge:  { type: 'line', x1: 60, y1: 54, x2: 59, y2: 65, strokeWidth: 1.0, opacity: 0.20 },
      nose_tip:     { type: 'path', d: 'M56 65 Q59 68, 63 65', strokeWidth: 1.0, opacity: 0.22 },

      // Slight pout — "hmm" expression
      mouth:        { type: 'path', d: 'M44 80 Q52 78, 60 80 Q68 82, 76 80', strokeWidth: 1.6, opacity: 0.35 },

      jaw_left:     { type: 'path', d: 'M26 42 Q24 60, 30 78 Q38 90, 50 94', strokeWidth: 1.2, opacity: 0.18 },
      jaw_right:    { type: 'path', d: 'M94 42 Q96 60, 90 78 Q82 90, 70 94', strokeWidth: 1.2, opacity: 0.18 },
    },
    glows: {
      left_eye_glow:  { cx: 41, cy: 46, r: 8, opacity: 0.05 },
      right_eye_glow: { cx: 80, cy: 45, r: 8, opacity: 0.05 },
      forehead_glow:  { cx: 55, cy: 22, r: 12, opacity: 0.06 },
      face_glow:      { cx: 60, cy: 60, r: 32, opacity: 0.04 },
    },
  },

  listening: {
    features: {
      hair_top:     { type: 'path', d: 'M35 18 Q50 8, 68 14 Q78 17, 85 20', strokeWidth: 1.8, opacity: 0.35 },
      hair_part:    { type: 'path', d: 'M52 12 Q54 18, 53 24', strokeWidth: 1.2, opacity: 0.25 },
      hair_left:    { type: 'path', d: 'M35 18 Q30 22, 28 30', strokeWidth: 1.5, opacity: 0.30 },

      // Both brows slightly up — interested/attentive
      left_brow:    { type: 'path', d: 'M30 34 Q40 28, 50 33', strokeWidth: 1.8, opacity: 0.50 },
      right_brow:   { type: 'path', d: 'M70 32 Q80 27, 90 34', strokeWidth: 1.8, opacity: 0.50 },

      // Eyes open wider
      left_eye:     { type: 'path', d: 'M33 47 Q40 42, 49 47', strokeWidth: 1.5, opacity: 0.45 },
      right_eye:    { type: 'path', d: 'M71 46 Q80 41, 89 46', strokeWidth: 1.5, opacity: 0.45 },

      nose_bridge:  { type: 'line', x1: 60, y1: 54, x2: 59, y2: 65, strokeWidth: 1.0, opacity: 0.20 },
      nose_tip:     { type: 'path', d: 'M56 65 Q59 68, 63 65', strokeWidth: 1.0, opacity: 0.22 },

      // Mouth neutral — slight line
      mouth:        { type: 'path', d: 'M44 80 Q60 83, 76 80', strokeWidth: 1.4, opacity: 0.30 },

      jaw_left:     { type: 'path', d: 'M26 42 Q24 60, 30 78 Q38 90, 50 94', strokeWidth: 1.2, opacity: 0.18 },
      jaw_right:    { type: 'path', d: 'M94 42 Q96 60, 90 78 Q82 90, 70 94', strokeWidth: 1.2, opacity: 0.18 },
    },
    glows: {
      left_eye_glow:  { cx: 41, cy: 46, r: 7, opacity: 0.04 },
      right_eye_glow: { cx: 80, cy: 45, r: 7, opacity: 0.04 },
      left_ear_glow:  { cx: 14, cy: 55, r: 7, opacity: 0.05 },
      right_ear_glow: { cx: 106, cy: 55, r: 7, opacity: 0.05 },
      face_glow:      { cx: 60, cy: 60, r: 32, opacity: 0.04 },
    },
  },

  speaking: {
    features: {
      hair_top:     { type: 'path', d: 'M35 18 Q50 8, 68 14 Q78 17, 85 20', strokeWidth: 1.8, opacity: 0.35 },
      hair_part:    { type: 'path', d: 'M52 12 Q54 18, 53 24', strokeWidth: 1.2, opacity: 0.25 },
      hair_left:    { type: 'path', d: 'M35 18 Q30 22, 28 30', strokeWidth: 1.5, opacity: 0.30 },

      // Brows in normal/animated position
      left_brow:    { type: 'path', d: 'M30 37 Q40 31, 50 35', strokeWidth: 1.8, opacity: 0.45 },
      right_brow:   { type: 'path', d: 'M70 34 Q80 30, 90 36', strokeWidth: 1.8, opacity: 0.45 },

      // Eyes normal
      left_eye:     { type: 'path', d: 'M34 48 Q40 44, 48 48', strokeWidth: 1.5, opacity: 0.40 },
      right_eye:    { type: 'path', d: 'M72 47 Q80 43, 88 47', strokeWidth: 1.5, opacity: 0.40 },

      nose_bridge:  { type: 'line', x1: 60, y1: 54, x2: 59, y2: 65, strokeWidth: 1.0, opacity: 0.20 },
      nose_tip:     { type: 'path', d: 'M56 65 Q59 68, 63 65', strokeWidth: 1.0, opacity: 0.22 },

      // Mouth opens wider — animated speaking
      mouth:        { type: 'path', d: 'M40 78 Q52 90, 60 88 Q70 86, 80 76', strokeWidth: 1.6, opacity: 0.42 },

      jaw_left:     { type: 'path', d: 'M26 42 Q24 60, 30 78 Q38 90, 50 94', strokeWidth: 1.2, opacity: 0.18 },
      jaw_right:    { type: 'path', d: 'M94 42 Q96 60, 90 78 Q82 90, 70 94', strokeWidth: 1.2, opacity: 0.18 },
    },
    glows: {
      left_eye_glow:  { cx: 41, cy: 47, r: 7, opacity: 0.04 },
      right_eye_glow: { cx: 80, cy: 46, r: 7, opacity: 0.04 },
      face_glow:      { cx: 60, cy: 60, r: 32, opacity: 0.05 },
    },
  },

  sleeping: {
    features: {
      // Hair stays but faded
      hair_top:     { type: 'path', d: 'M35 18 Q50 8, 68 14 Q78 17, 85 20', strokeWidth: 1.4, opacity: 0.10 },
      hair_part:    { type: 'path', d: 'M52 12 Q54 18, 53 24', strokeWidth: 0.8, opacity: 0.06 },
      hair_left:    { type: 'path', d: 'M35 18 Q30 22, 28 30', strokeWidth: 1.0, opacity: 0.08 },

      // Brows relaxed
      left_brow:    { type: 'path', d: 'M30 38 Q40 34, 50 37', strokeWidth: 1.4, opacity: 0.10 },
      right_brow:   { type: 'path', d: 'M70 36 Q80 33, 90 37', strokeWidth: 1.4, opacity: 0.10 },

      // Eyes closed — lines curve downward
      left_eye:     { type: 'path', d: 'M34 48 Q40 52, 48 48', strokeWidth: 1.2, opacity: 0.10 },
      right_eye:    { type: 'path', d: 'M72 47 Q80 51, 88 47', strokeWidth: 1.2, opacity: 0.10 },

      nose_bridge:  { type: 'line', x1: 60, y1: 54, x2: 59, y2: 65, strokeWidth: 0.8, opacity: 0.06 },
      nose_tip:     { type: 'path', d: 'M56 65 Q59 68, 63 65', strokeWidth: 0.8, opacity: 0.06 },

      // Mouth relaxed — straight line
      mouth:        { type: 'path', d: 'M44 80 Q60 82, 76 80', strokeWidth: 1.2, opacity: 0.08 },

      jaw_left:     { type: 'path', d: 'M26 42 Q24 60, 30 78 Q38 90, 50 94', strokeWidth: 1.0, opacity: 0.06 },
      jaw_right:    { type: 'path', d: 'M94 42 Q96 60, 90 78 Q82 90, 70 94', strokeWidth: 1.0, opacity: 0.06 },
    },
    glows: {
      face_glow: { cx: 60, cy: 60, r: 32, opacity: 0.01 },
    },
  },
}

// ─── Mood overlays ──────────────────────────────────────────────────

export const chandlerMoodOverlays: Record<string, ChandlerMoodOverlay> = {
  sarcastic: {
    features: {
      // Exaggerated eye roll — eyes shift up
      left_eye:   { type: 'path', d: 'M34 45 Q40 40, 48 45', strokeWidth: 1.5, opacity: 0.45 },
      right_eye:  { type: 'path', d: 'M72 44 Q80 39, 88 44', strokeWidth: 1.5, opacity: 0.45 },
      // One brow way up
      left_brow:  { type: 'path', d: 'M30 28 Q40 20, 50 26', strokeWidth: 2.0, opacity: 0.55 },
      right_brow: { type: 'path', d: 'M70 36 Q80 33, 90 38', strokeWidth: 1.8, opacity: 0.45 },
      // One-sided dramatic smirk
      mouth:      { type: 'path', d: 'M42 82 Q52 84, 60 82 Q72 78, 80 72', strokeWidth: 1.8, opacity: 0.48 },
    },
  },

  gotcha: {
    features: {
      // Both brows raised high
      left_brow:  { type: 'path', d: 'M30 30 Q40 22, 50 27', strokeWidth: 2.0, opacity: 0.55 },
      right_brow: { type: 'path', d: 'M70 27 Q80 21, 90 30', strokeWidth: 2.0, opacity: 0.55 },
      // Eyes bright and wide
      left_eye:   { type: 'path', d: 'M32 47 Q40 40, 50 47', strokeWidth: 1.6, opacity: 0.50 },
      right_eye:  { type: 'path', d: 'M70 46 Q80 39, 90 46', strokeWidth: 1.6, opacity: 0.50 },
      // Big wide grin
      mouth:      { type: 'path', d: 'M38 78 Q52 92, 60 90 Q70 88, 82 76', strokeWidth: 1.8, opacity: 0.48 },
    },
    glows: {
      face_glow: { cx: 60, cy: 60, r: 35, opacity: 0.07 },
    },
  },

  playful: {
    features: {
      // Mischievous asymmetric brows
      left_brow:  { type: 'path', d: 'M30 34 Q40 27, 50 32', strokeWidth: 1.8, opacity: 0.50 },
      right_brow: { type: 'path', d: 'M70 32 Q80 28, 90 35', strokeWidth: 1.8, opacity: 0.48 },
      // Slight head tilt suggested by asymmetric eye positions
      left_eye:   { type: 'path', d: 'M33 47 Q40 43, 49 48', strokeWidth: 1.5, opacity: 0.42 },
      right_eye:  { type: 'path', d: 'M72 46 Q80 42, 88 47', strokeWidth: 1.5, opacity: 0.42 },
      // Half-smile, mischievous
      mouth:      { type: 'path', d: 'M44 80 Q54 85, 62 82 Q72 78, 78 74', strokeWidth: 1.6, opacity: 0.42 },
    },
  },
}
