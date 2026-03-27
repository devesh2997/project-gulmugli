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
      // Hair — same as idle
      hair_outline: { type: 'path', d: 'M30 28 Q32 18, 40 12 Q46 7, 52 10 Q56 5, 62 8 Q68 4, 74 10 Q82 14, 86 22 Q90 28, 88 34', strokeWidth: 2.0, opacity: 0.45 },
      hair_spike1:  { type: 'path', d: 'M44 12 Q47 4, 52 10', strokeWidth: 1.4, opacity: 0.30 },
      hair_spike2:  { type: 'path', d: 'M56 8 Q60 2, 62 8', strokeWidth: 1.4, opacity: 0.32 },
      hair_spike3:  { type: 'path', d: 'M66 6 Q72 3, 74 10', strokeWidth: 1.4, opacity: 0.28 },
      hair_part:    { type: 'path', d: 'M50 10 Q52 18, 50 26', strokeWidth: 1.0, opacity: 0.18 },
      hair_left:    { type: 'path', d: 'M30 28 Q26 32, 25 38', strokeWidth: 1.5, opacity: 0.25 },
      hair_right:   { type: 'path', d: 'M88 34 Q90 38, 92 42', strokeWidth: 1.2, opacity: 0.20 },

      // Face outline — same as idle
      face_left:    { type: 'path', d: 'M25 38 Q22 52, 26 68 Q30 82, 40 90', strokeWidth: 1.3, opacity: 0.20 },
      face_right:   { type: 'path', d: 'M92 42 Q96 52, 94 68 Q88 82, 78 90', strokeWidth: 1.3, opacity: 0.20 },
      chin:         { type: 'path', d: 'M40 90 Q50 98, 60 98 Q70 98, 78 90', strokeWidth: 1.2, opacity: 0.18 },

      // Skeptical Chandler: left brow raised HIGH, right stays lower
      left_brow:    { type: 'path', d: 'M30 30 Q38 22, 50 28', strokeWidth: 2.0, opacity: 0.55 },
      right_brow:   { type: 'path', d: 'M68 37 Q78 34, 88 39', strokeWidth: 1.8, opacity: 0.45 },

      // Eyes slightly wider — the skeptical stare
      left_eye:     { type: 'path', d: 'M33 47 Q38 41, 44 42 Q48 43, 50 47', strokeWidth: 1.5, opacity: 0.45 },
      right_eye:    { type: 'path', d: 'M68 46 Q74 41, 80 42 Q84 43, 86 46', strokeWidth: 1.5, opacity: 0.45 },
      // Pupils look up-left (thinking)
      left_pupil:   { type: 'circle', cx: 39, cy: 44, r: 1.5, strokeWidth: 0, opacity: 0.38, fill: true },
      right_pupil:  { type: 'circle', cx: 75, cy: 43, r: 1.5, strokeWidth: 0, opacity: 0.38, fill: true },

      // Nose — same as idle
      nose_bridge:  { type: 'path', d: 'M59 52 Q58 58, 57 64', strokeWidth: 1.0, opacity: 0.18 },
      nose_tip:     { type: 'path', d: 'M54 64 Q57 68, 62 64', strokeWidth: 1.2, opacity: 0.22 },

      // Slight pout — flat "hmm" expression
      mouth:        { type: 'path', d: 'M42 80 Q52 78, 60 80 Q68 82, 76 80', strokeWidth: 1.6, opacity: 0.35 },
      mouth_lower:  { type: 'path', d: 'M46 83 Q56 86, 72 83', strokeWidth: 1.0, opacity: 0.12 },

      // Neck + collar — same as idle
      neck_left:    { type: 'line', x1: 48, y1: 98, x2: 42, y2: 115, strokeWidth: 1.2, opacity: 0.15 },
      neck_right:   { type: 'line', x1: 72, y1: 98, x2: 78, y2: 115, strokeWidth: 1.2, opacity: 0.15 },
      collar_v:     { type: 'path', d: 'M34 110 Q44 105, 60 115 Q76 105, 86 110', strokeWidth: 1.3, opacity: 0.18 },
    },
    glows: {
      left_eye_glow:  { cx: 41, cy: 46, r: 8, opacity: 0.05 },
      right_eye_glow: { cx: 77, cy: 45, r: 8, opacity: 0.05 },
      forehead_glow:  { cx: 55, cy: 22, r: 12, opacity: 0.06 },
      face_glow:      { cx: 60, cy: 60, r: 32, opacity: 0.04 },
    },
  },

  listening: {
    features: {
      // Hair — same as idle
      hair_outline: { type: 'path', d: 'M30 28 Q32 18, 40 12 Q46 7, 52 10 Q56 5, 62 8 Q68 4, 74 10 Q82 14, 86 22 Q90 28, 88 34', strokeWidth: 2.0, opacity: 0.45 },
      hair_spike1:  { type: 'path', d: 'M44 12 Q47 4, 52 10', strokeWidth: 1.4, opacity: 0.30 },
      hair_spike2:  { type: 'path', d: 'M56 8 Q60 2, 62 8', strokeWidth: 1.4, opacity: 0.32 },
      hair_spike3:  { type: 'path', d: 'M66 6 Q72 3, 74 10', strokeWidth: 1.4, opacity: 0.28 },
      hair_part:    { type: 'path', d: 'M50 10 Q52 18, 50 26', strokeWidth: 1.0, opacity: 0.18 },
      hair_left:    { type: 'path', d: 'M30 28 Q26 32, 25 38', strokeWidth: 1.5, opacity: 0.25 },
      hair_right:   { type: 'path', d: 'M88 34 Q90 38, 92 42', strokeWidth: 1.2, opacity: 0.20 },

      // Face outline — same as idle
      face_left:    { type: 'path', d: 'M25 38 Q22 52, 26 68 Q30 82, 40 90', strokeWidth: 1.3, opacity: 0.20 },
      face_right:   { type: 'path', d: 'M92 42 Q96 52, 94 68 Q88 82, 78 90', strokeWidth: 1.3, opacity: 0.20 },
      chin:         { type: 'path', d: 'M40 90 Q50 98, 60 98 Q70 98, 78 90', strokeWidth: 1.2, opacity: 0.18 },

      // Both brows slightly raised — attentive
      left_brow:    { type: 'path', d: 'M30 34 Q38 28, 50 33', strokeWidth: 2.0, opacity: 0.50 },
      right_brow:   { type: 'path', d: 'M68 32 Q78 27, 88 34', strokeWidth: 2.0, opacity: 0.50 },

      // Eyes wide open — wider arcs than idle
      left_eye:     { type: 'path', d: 'M33 48 Q38 41, 44 42 Q48 43, 50 48', strokeWidth: 1.5, opacity: 0.45 },
      right_eye:    { type: 'path', d: 'M68 47 Q74 40, 80 41 Q84 42, 86 47', strokeWidth: 1.5, opacity: 0.45 },
      // Pupils centered/focused
      left_pupil:   { type: 'circle', cx: 41, cy: 45, r: 1.6, strokeWidth: 0, opacity: 0.38, fill: true },
      right_pupil:  { type: 'circle', cx: 77, cy: 44, r: 1.6, strokeWidth: 0, opacity: 0.38, fill: true },

      // Nose — same as idle
      nose_bridge:  { type: 'path', d: 'M59 52 Q58 58, 57 64', strokeWidth: 1.0, opacity: 0.18 },
      nose_tip:     { type: 'path', d: 'M54 64 Q57 68, 62 64', strokeWidth: 1.2, opacity: 0.22 },

      // Mouth neutral, slightly parted
      mouth:        { type: 'path', d: 'M42 80 Q50 83, 60 82 Q68 81, 76 80', strokeWidth: 1.5, opacity: 0.35 },
      mouth_lower:  { type: 'path', d: 'M46 84 Q54 86, 72 84', strokeWidth: 1.0, opacity: 0.12 },

      // Neck + collar — same as idle
      neck_left:    { type: 'line', x1: 48, y1: 98, x2: 42, y2: 115, strokeWidth: 1.2, opacity: 0.15 },
      neck_right:   { type: 'line', x1: 72, y1: 98, x2: 78, y2: 115, strokeWidth: 1.2, opacity: 0.15 },
      collar_v:     { type: 'path', d: 'M34 110 Q44 105, 60 115 Q76 105, 86 110', strokeWidth: 1.3, opacity: 0.18 },
    },
    glows: {
      left_eye_glow:  { cx: 41, cy: 46, r: 7, opacity: 0.04 },
      right_eye_glow: { cx: 77, cy: 45, r: 7, opacity: 0.04 },
      left_ear_glow:  { cx: 14, cy: 55, r: 7, opacity: 0.05 },
      right_ear_glow: { cx: 106, cy: 55, r: 7, opacity: 0.05 },
      face_glow:      { cx: 60, cy: 60, r: 32, opacity: 0.04 },
    },
  },

  speaking: {
    features: {
      // Hair — same as idle
      hair_outline: { type: 'path', d: 'M30 28 Q32 18, 40 12 Q46 7, 52 10 Q56 5, 62 8 Q68 4, 74 10 Q82 14, 86 22 Q90 28, 88 34', strokeWidth: 2.0, opacity: 0.45 },
      hair_spike1:  { type: 'path', d: 'M44 12 Q47 4, 52 10', strokeWidth: 1.4, opacity: 0.30 },
      hair_spike2:  { type: 'path', d: 'M56 8 Q60 2, 62 8', strokeWidth: 1.4, opacity: 0.32 },
      hair_spike3:  { type: 'path', d: 'M66 6 Q72 3, 74 10', strokeWidth: 1.4, opacity: 0.28 },
      hair_part:    { type: 'path', d: 'M50 10 Q52 18, 50 26', strokeWidth: 1.0, opacity: 0.18 },
      hair_left:    { type: 'path', d: 'M30 28 Q26 32, 25 38', strokeWidth: 1.5, opacity: 0.25 },
      hair_right:   { type: 'path', d: 'M88 34 Q90 38, 92 42', strokeWidth: 1.2, opacity: 0.20 },

      // Face outline — same as idle
      face_left:    { type: 'path', d: 'M25 38 Q22 52, 26 68 Q30 82, 40 90', strokeWidth: 1.3, opacity: 0.20 },
      face_right:   { type: 'path', d: 'M92 42 Q96 52, 94 68 Q88 82, 78 90', strokeWidth: 1.3, opacity: 0.20 },
      chin:         { type: 'path', d: 'M40 90 Q50 98, 60 98 Q70 98, 78 90', strokeWidth: 1.2, opacity: 0.18 },

      // Brows slightly up — expressive/animated
      left_brow:    { type: 'path', d: 'M30 36 Q38 30, 50 34', strokeWidth: 2.0, opacity: 0.48 },
      right_brow:   { type: 'path', d: 'M68 34 Q78 29, 88 35', strokeWidth: 2.0, opacity: 0.48 },

      // Eyes normal
      left_eye:     { type: 'path', d: 'M33 48 Q38 43, 44 44 Q48 45, 50 48', strokeWidth: 1.5, opacity: 0.42 },
      right_eye:    { type: 'path', d: 'M68 47 Q74 42, 80 43 Q84 44, 86 47', strokeWidth: 1.5, opacity: 0.42 },
      // Pupils centered
      left_pupil:   { type: 'circle', cx: 41, cy: 46, r: 1.5, strokeWidth: 0, opacity: 0.35, fill: true },
      right_pupil:  { type: 'circle', cx: 77, cy: 45, r: 1.5, strokeWidth: 0, opacity: 0.35, fill: true },

      // Nose — same as idle
      nose_bridge:  { type: 'path', d: 'M59 52 Q58 58, 57 64', strokeWidth: 1.0, opacity: 0.18 },
      nose_tip:     { type: 'path', d: 'M54 64 Q57 68, 62 64', strokeWidth: 1.2, opacity: 0.22 },

      // Mouth WIDE open — upper lip arc up, lower lip arc down
      mouth:        { type: 'path', d: 'M40 78 Q50 74, 60 75 Q70 74, 80 78', strokeWidth: 1.8, opacity: 0.45 },
      mouth_lower:  { type: 'path', d: 'M42 82 Q52 90, 60 91 Q68 90, 78 82', strokeWidth: 1.6, opacity: 0.40 },

      // Neck + collar — same as idle
      neck_left:    { type: 'line', x1: 48, y1: 98, x2: 42, y2: 115, strokeWidth: 1.2, opacity: 0.15 },
      neck_right:   { type: 'line', x1: 72, y1: 98, x2: 78, y2: 115, strokeWidth: 1.2, opacity: 0.15 },
      collar_v:     { type: 'path', d: 'M34 110 Q44 105, 60 115 Q76 105, 86 110', strokeWidth: 1.3, opacity: 0.18 },
    },
    glows: {
      left_eye_glow:  { cx: 41, cy: 46, r: 7, opacity: 0.04 },
      right_eye_glow: { cx: 77, cy: 45, r: 7, opacity: 0.04 },
      face_glow:      { cx: 60, cy: 60, r: 32, opacity: 0.05 },
    },
  },

  sleeping: {
    features: {
      // Hair — simplified, very dim
      hair_outline: { type: 'path', d: 'M30 28 Q32 18, 40 12 Q46 7, 52 10 Q56 5, 62 8 Q68 4, 74 10 Q82 14, 86 22 Q90 28, 88 34', strokeWidth: 1.6, opacity: 0.10 },
      hair_spike1:  { type: 'path', d: 'M44 12 Q47 4, 52 10', strokeWidth: 1.0, opacity: 0.06 },
      hair_spike2:  { type: 'path', d: 'M56 8 Q60 2, 62 8', strokeWidth: 1.0, opacity: 0.07 },
      hair_spike3:  { type: 'path', d: 'M66 6 Q72 3, 74 10', strokeWidth: 1.0, opacity: 0.06 },
      hair_part:    { type: 'path', d: 'M50 10 Q52 18, 50 26', strokeWidth: 0.8, opacity: 0.06 },
      hair_left:    { type: 'path', d: 'M30 28 Q26 32, 25 38', strokeWidth: 1.0, opacity: 0.08 },
      hair_right:   { type: 'path', d: 'M88 34 Q90 38, 92 42', strokeWidth: 0.8, opacity: 0.06 },

      // Face outline — dim
      face_left:    { type: 'path', d: 'M25 38 Q22 52, 26 68 Q30 82, 40 90', strokeWidth: 1.0, opacity: 0.08 },
      face_right:   { type: 'path', d: 'M92 42 Q96 52, 94 68 Q88 82, 78 90', strokeWidth: 1.0, opacity: 0.08 },
      chin:         { type: 'path', d: 'M40 90 Q50 98, 60 98 Q70 98, 78 90', strokeWidth: 0.8, opacity: 0.06 },

      // Brows relaxed, very dim
      left_brow:    { type: 'path', d: 'M30 40 Q38 36, 50 39', strokeWidth: 1.4, opacity: 0.10 },
      right_brow:   { type: 'path', d: 'M68 38 Q78 35, 88 39', strokeWidth: 1.4, opacity: 0.10 },

      // Eyes closed — curves downward
      left_eye:     { type: 'path', d: 'M33 48 Q38 52, 44 52 Q48 52, 50 48', strokeWidth: 1.2, opacity: 0.10 },
      right_eye:    { type: 'path', d: 'M68 47 Q74 51, 80 51 Q84 51, 86 47', strokeWidth: 1.2, opacity: 0.10 },
      // No pupils visible (sleeping) — zero opacity
      left_pupil:   { type: 'circle', cx: 41, cy: 46, r: 1.5, strokeWidth: 0, opacity: 0, fill: true },
      right_pupil:  { type: 'circle', cx: 77, cy: 45, r: 1.5, strokeWidth: 0, opacity: 0, fill: true },

      // Nose — dim
      nose_bridge:  { type: 'path', d: 'M59 52 Q58 58, 57 64', strokeWidth: 0.8, opacity: 0.06 },
      nose_tip:     { type: 'path', d: 'M54 64 Q57 68, 62 64', strokeWidth: 0.8, opacity: 0.06 },

      // Mouth relaxed — flat line
      mouth:        { type: 'path', d: 'M44 80 Q54 82, 60 82 Q66 82, 76 80', strokeWidth: 1.2, opacity: 0.08 },
      mouth_lower:  { type: 'path', d: 'M46 84 Q56 85, 72 84', strokeWidth: 0.8, opacity: 0.06 },

      // Neck + collar hidden (under the "covers")
      neck_left:    { type: 'line', x1: 48, y1: 98, x2: 42, y2: 115, strokeWidth: 1.2, opacity: 0 },
      neck_right:   { type: 'line', x1: 72, y1: 98, x2: 78, y2: 115, strokeWidth: 1.2, opacity: 0 },
      collar_v:     { type: 'path', d: 'M34 110 Q44 105, 60 115 Q76 105, 86 110', strokeWidth: 1.3, opacity: 0 },
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
      left_eye:   { type: 'path', d: 'M33 46 Q38 40, 44 41 Q48 42, 50 46', strokeWidth: 1.5, opacity: 0.45 },
      right_eye:  { type: 'path', d: 'M68 45 Q74 39, 80 40 Q84 41, 86 45', strokeWidth: 1.5, opacity: 0.45 },
      // Pupils rolled up
      left_pupil:  { type: 'circle', cx: 41, cy: 43, r: 1.5, strokeWidth: 0, opacity: 0.40, fill: true },
      right_pupil: { type: 'circle', cx: 77, cy: 42, r: 1.5, strokeWidth: 0, opacity: 0.40, fill: true },
      // One brow way up
      left_brow:  { type: 'path', d: 'M30 28 Q38 20, 50 26', strokeWidth: 2.0, opacity: 0.55 },
      right_brow: { type: 'path', d: 'M68 36 Q78 33, 88 38', strokeWidth: 1.8, opacity: 0.45 },
      // One-sided dramatic smirk
      mouth:      { type: 'path', d: 'M42 82 Q52 84, 60 82 Q72 78, 80 72', strokeWidth: 1.8, opacity: 0.48 },
    },
  },

  gotcha: {
    features: {
      // Both brows raised high
      left_brow:  { type: 'path', d: 'M30 30 Q38 22, 50 27', strokeWidth: 2.0, opacity: 0.55 },
      right_brow: { type: 'path', d: 'M68 27 Q78 21, 88 30', strokeWidth: 2.0, opacity: 0.55 },
      // Eyes bright and wide
      left_eye:   { type: 'path', d: 'M33 48 Q38 40, 44 41 Q48 42, 50 48', strokeWidth: 1.6, opacity: 0.50 },
      right_eye:  { type: 'path', d: 'M68 47 Q74 39, 80 40 Q84 41, 86 47', strokeWidth: 1.6, opacity: 0.50 },
      // Pupils bright and focused
      left_pupil:  { type: 'circle', cx: 41, cy: 45, r: 1.8, strokeWidth: 0, opacity: 0.42, fill: true },
      right_pupil: { type: 'circle', cx: 77, cy: 44, r: 1.8, strokeWidth: 0, opacity: 0.42, fill: true },
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
      left_brow:  { type: 'path', d: 'M30 34 Q38 27, 50 32', strokeWidth: 1.8, opacity: 0.50 },
      right_brow: { type: 'path', d: 'M68 32 Q78 28, 88 35', strokeWidth: 1.8, opacity: 0.48 },
      // Slight head tilt suggested by asymmetric eye positions
      left_eye:   { type: 'path', d: 'M33 48 Q38 43, 44 44 Q48 46, 50 48', strokeWidth: 1.5, opacity: 0.42 },
      right_eye:  { type: 'path', d: 'M68 47 Q74 42, 80 43 Q84 45, 86 47', strokeWidth: 1.5, opacity: 0.42 },
      // Pupils slightly off-center (mischievous glance)
      left_pupil:  { type: 'circle', cx: 43, cy: 46, r: 1.5, strokeWidth: 0, opacity: 0.38, fill: true },
      right_pupil: { type: 'circle', cx: 79, cy: 45, r: 1.5, strokeWidth: 0, opacity: 0.38, fill: true },
      // Half-smile, mischievous
      mouth:      { type: 'path', d: 'M44 80 Q54 85, 62 82 Q72 78, 78 74', strokeWidth: 1.6, opacity: 0.42 },
    },
  },
}
