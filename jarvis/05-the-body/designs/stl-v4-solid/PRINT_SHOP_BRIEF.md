# Print Shop Brief — Vesper Enclosure v4

A small desktop appliance enclosure, **200 × 145 × 70 mm**
(W × H × D), shaped like a tablet on its side.

---

## What's being made

A single enclosure that houses:

- A 7" HDMI LCD (front face, screen visible)
- A small computer (NVIDIA Jetson, mounted to the back panel)
- A speaker (fires downward through the bottom)
- A microphone (top face)
- A WS2812B LED bar (across the bottom front)
- Two side panels

---

## Bundle contents

All files in this folder:

| File | Material | Quantity | Approx. weight |
|---|---|---|---|
| `jarvis-frame-v4.stl` | PETG, matte black | 1× | ~340 g |
| `jarvis-back-panel-v4.stl` | PETG, matte black | 1× | ~80 g |
| `jarvis-side-panel-v4.stl` | PETG, matte black | **2×** | ~25 g each |
| `jarvis-led-diffuser-v4.stl` | Clear / natural PLA | 1× | ~3 g |

Total filament: ~470 g.

The two side panels are identical — print the same STL twice.

---

## Material specifications

| Part | Material | Notes |
|---|---|---|
| Frame, back panel, side panels | PETG, matte black, ±0.05 mm tolerance | PETG holds tolerances better than PLA in warm ambient temperatures. Matte black hides the LCD bezel cleanly. |
| LED diffuser | Clear or natural PLA, 100 % infill | Natural PLA gives the desired translucency for an LED diffuser. PETG would be milky-cloudy at 100 % infill. |

If matte black PETG is not stocked, glossy black is acceptable.
Avoid TPU, ABS, or any flexible material.

---

## Print settings (FDM)

```
Printer:       Any 0.4 mm nozzle FDM
                 (Prusa MK3/4, Bambu A1/X1, Ender 3+, Creality K1)
Layer height:  0.2 mm  (frame, back panel, side panels)
               0.15 mm (LED diffuser — finer for light transmission)
Walls:         4 perimeters (1.6 mm wall thickness)
Infill:        20 % honeycomb / gyroid (frame, back panel, side panels)
               100 %                   (LED diffuser only)
Supports:      Tree / organic, ONLY on bottoms of internal screen
               standoffs and Jetson standoffs in back panel.
               Side panels need NO supports.
Bed temp:      70 °C (PETG), 60 °C (PLA)
Print speed:   50 mm/s outer perimeters, 80 mm/s infill
Brim:          5 mm (PETG specifically — first-layer adhesion)

Print orientation:
  jarvis-frame-v4.stl        — FRONT face DOWN (cleanest screen-side finish)
  jarvis-back-panel-v4.stl   — flat side DOWN, port-cluster face UP
  jarvis-led-diffuser-v4.stl — flat (any orientation, no supports)
  jarvis-side-panel-v4.stl   — inside face UP (dimple bumps facing up;
                               gives a clean outer surface)
```

Approximate print times on a typical FDM:

| Part | Time |
|---|---|
| Frame | 14–16 hours |
| Back panel | 3–4 hours |
| Side panels (×2) | 1.5 hours each = 3 hours |
| LED diffuser | 45–60 min |
| **Total sequential** | **~21–24 hours** |

Two printers in parallel cuts the wall-clock to ~14–16 h.

---

## Tolerance notes

Dimensions where mis-tolerance causes assembly issues:

- **Screen cutout** (front face): rectangular hole exposing the
  LCD active area. Designed at 154 × 86 mm with 1.5 mm overhang
  hiding the bezel. Print accurate to ±0.3 mm.
- **Screen mounting standoffs** (interior, behind front face):
  four M3 brass-insert pockets. Marker dimples must be visible
  and approximately on design coordinates after print.
- **Side opening rabbet**: panel should slide in flush with
  ~0.5 mm play. Tight tolerance shop (<±0.1 mm) might need a
  0.5 mm shim; loose: panel gets sanded to fit.
- **Snap-fit corners (back panel ↔ frame)**: tolerance ±0.2 mm
  is required for the snap-fit to engage cleanly.

If any dimension comes out > 0.5 mm off design, please print a
quick test of just the affected face and confirm before
committing to the full frame.

---

## Sanity checks before quoting

- [ ] All four STLs load as **manifold meshes** (no holes /
      inverted normals) in the slicer.
- [ ] Frame fits within the printer's build volume
      (200 × 145 × 70 mm — fits any modern desktop FDM).
- [ ] PETG filament in stock (or quote for an equivalent
      alternate).

If any of these fail, please contact the requester before
printing.

---

## Questions

For tolerance, material, or orientation questions, please reply
to the order or contact the requester directly. Designs are
parametric; minor adjustments regenerate quickly.
