/**
 * Canvas — full-screen background layer.
 *
 * Layer 1: linear gradient from --time-current-canvas_gradient_start to
 *           --time-current-canvas_gradient_end (interpolated by useTimeOfDay).
 * Layer 2: radial gradient using --personality-glow_color at ~5% opacity,
 *           centred — provides the per-personality tint on top of the time base.
 *
 * Sits at z-index 0 so every other UI element renders above it.
 * No props — reads everything from CSS vars set by TokenProvider.
 */

export function Canvas() {
  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 0,
        background: `linear-gradient(160deg, var(--time-current-canvas_gradient_start), var(--time-current-canvas_gradient_end))`,
      }}
    >
      {/* Personality tint overlay */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background: `radial-gradient(ellipse at 50% 50%, rgba(var(--personality-accent-rgb), 0.08) 0%, transparent 70%)`,
        }}
      />
    </div>
  )
}
