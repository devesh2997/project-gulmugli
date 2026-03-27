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
      // Hair — distinctive messy spiky 90s style, swept right, volumous on top
      // Based on reference: spiky peaks, side-parted, left side shorter
      hair_outline: { type: 'path', d: 'M30 28 Q32 18, 40 12 Q46 7, 52 10 Q56 5, 62 8 Q68 4, 74 10 Q82 14, 86 22 Q90 28, 88 34', strokeWidth: 2.0, opacity: 0.45 },
      hair_spike1:  { type: 'path', d: 'M44 12 Q47 4, 52 10', strokeWidth: 1.4, opacity: 0.30 },
      hair_spike2:  { type: 'path', d: 'M56 8 Q60 2, 62 8', strokeWidth: 1.4, opacity: 0.32 },
      hair_spike3:  { type: 'path', d: 'M66 6 Q72 3, 74 10', strokeWidth: 1.4, opacity: 0.28 },
      hair_part:    { type: 'path', d: 'M50 10 Q52 18, 50 26', strokeWidth: 1.0, opacity: 0.18 },
      hair_left:    { type: 'path', d: 'M30 28 Q26 32, 25 38', strokeWidth: 1.5, opacity: 0.25 },
      hair_right:   { type: 'path', d: 'M88 34 Q90 38, 92 42', strokeWidth: 1.2, opacity: 0.20 },

      // Face outline — wider cheeks, defined chin (based on reference)
      face_left:    { type: 'path', d: 'M25 38 Q22 52, 26 68 Q30 82, 40 90', strokeWidth: 1.3, opacity: 0.20 },
      face_right:   { type: 'path', d: 'M92 42 Q96 52, 94 68 Q88 82, 78 90', strokeWidth: 1.3, opacity: 0.20 },
      chin:         { type: 'path', d: 'M40 90 Q50 98, 60 98 Q70 98, 78 90', strokeWidth: 1.2, opacity: 0.18 },

      // Eyebrows — strong, expressive, slightly asymmetric (signature Chandler)
      left_brow:    { type: 'path', d: 'M30 38 Q38 32, 50 36', strokeWidth: 2.0, opacity: 0.50 },
      right_brow:   { type: 'path', d: 'M68 35 Q78 31, 88 37', strokeWidth: 2.0, opacity: 0.50 },

      // Eyes — almond shaped with slight sardonic narrowness
      left_eye:     { type: 'path', d: 'M33 48 Q38 43, 44 44 Q48 45, 50 48', strokeWidth: 1.5, opacity: 0.42 },
      right_eye:    { type: 'path', d: 'M68 47 Q74 42, 80 43 Q84 44, 86 47', strokeWidth: 1.5, opacity: 0.42 },
      // Pupils — small dots for that "looking at you" quality
      left_pupil:   { type: 'circle', cx: 41, cy: 46, r: 1.5, strokeWidth: 0, opacity: 0.35, fill: true },
      right_pupil:  { type: 'circle', cx: 77, cy: 45, r: 1.5, strokeWidth: 0, opacity: 0.35, fill: true },

      // Nose — slightly wider, two strokes
      nose_bridge:  { type: 'path', d: 'M59 52 Q58 58, 57 64', strokeWidth: 1.0, opacity: 0.18 },
      nose_tip:     { type: 'path', d: 'M54 64 Q57 68, 62 64', strokeWidth: 1.2, opacity: 0.22 },

      // Mouth — THE SMIRK: one corner up, slightly open
      mouth:        { type: 'path', d: 'M40 80 Q50 84, 58 82 Q66 80, 74 76 Q78 74, 80 72', strokeWidth: 1.8, opacity: 0.45 },
      // Lower lip hint
      mouth_lower:  { type: 'path', d: 'M44 84 Q54 88, 64 85', strokeWidth: 1.0, opacity: 0.15 },

      // Neck + collar hint (cardigan/V-neck from reference)
      neck_left:    { type: 'line', x1: 48, y1: 98, x2: 42, y2: 115, strokeWidth: 1.2, opacity: 0.15 },
      neck_right:   { type: 'line', x1: 72, y1: 98, x2: 78, y2: 115, strokeWidth: 1.2, opacity: 0.15 },
      collar_v:     { type: 'path', d: 'M34 110 Q44 105, 60 115 Q76 105, 86 110', strokeWidth: 1.3, opacity: 0.18 },
    },
    glows: {
      left_eye_glow:  { cx: 41, cy: 46, r: 8, opacity: 0.05 },
      right_eye_glow: { cx: 77, cy: 45, r: 8, opacity: 0.05 },
      face_glow:      { cx: 60, cy: 60, r: 35, opacity: 0.05 },
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
