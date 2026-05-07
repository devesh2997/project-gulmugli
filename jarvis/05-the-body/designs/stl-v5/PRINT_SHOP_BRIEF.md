# Print Shop Brief — Vesper Enclosure v5

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
- Two side panels (left = solid, right = with port aperture)

---

## Bundle contents

All files in this folder:

| File | Material | Quantity | Approx. weight |
|---|---|---|---|
| `jarvis-frame-v5.stl` | PETG, matte black | 1× | ~340 g |
| `jarvis-back-panel-v5.stl` | PETG, matte black | 1× | ~75 g |
| `jarvis-side-panel-left-v5.stl` | PETG, matte black | 1× | ~22 g |
| `jarvis-side-panel-right-v5.stl` | PETG, matte black | 1× | ~17 g |
| `jarvis-led-diffuser-v5.stl` | Clear / natural PLA | 1× | ~3 g |

The two side panels are **different** STLs — the right side has an
aperture for cable access. Print each one once.

Total filament: ~460 g.

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
               and Jetson standoffs. Side panels and LED diffuser
               need NO supports.
Bed temp:      70 °C (PETG), 60 °C (PLA)
Print speed:   50 mm/s outer perimeters, 80 mm/s infill
Brim:          5 mm (PETG specifically — first-layer adhesion)

Print orientation:
  jarvis-frame-v5.stl              — FRONT face DOWN.
                                     Cleanest screen-aperture finish.
                                     The 4 feet on the bottom face
                                     point UP during print and need
                                     no supports.
  jarvis-back-panel-v5.stl         — flat side DOWN.
                                     Standoffs print as small upward
                                     bosses.
  jarvis-led-diffuser-v5.stl       — flat (any orientation).
  jarvis-side-panel-left-v5.stl    — INSIDE FACE DOWN.
                                     Magnet washer pockets print
                                     against the build plate, giving
                                     clean flat-bottom holes.
  jarvis-side-panel-right-v5.stl   — INSIDE FACE DOWN.
                                     Same as left. The port aperture
                                     is a clean through-hole; no
                                     overhangs.
```

Approximate print times on a typical FDM:

| Part | Time |
|---|---|
| Frame | 14–16 hours |
| Back panel | 3–4 hours |
| Side panel × 2 | 1.5 hours each = 3 hours |
| LED diffuser | 45–60 min |
| **Total sequential** | **~21–24 hours** |

Two printers in parallel cuts the wall-clock to ~14–16 h.

---

## Tolerance notes

Dimensions where mis-tolerance causes assembly issues:

- **Screen aperture** (front face): rectangular hole exposing the
  LCD active area at 154 × 86 mm with 1.5 mm overhang hiding the
  bezel. Print accurate to ±0.3 mm.
- **Screen mounting standoffs** (interior, behind front face):
  four M3 brass-insert pockets. Marker dimples must be visible
  and approximately on design coordinates after print.
- **Side panel ↔ side opening fit**: the side panels are sized
  0.3 mm smaller than the opening on each axis to allow insertion
  on FDM tolerances. If your printer is tight (≤ ±0.1 mm), the
  panels may need very light sanding to slide in cleanly.
- **Magnet pockets** (interior, in the 4 corner bosses around
  each side opening): 6 mm dia × 3 mm deep, designed for press-fit
  N42 disc magnets. Pockets print with a clean flat bottom.
- **LED diffuser ↔ slot fit**: diffuser is 0.3 mm smaller than the
  slot; should drop in cleanly.

If any dimension comes out > 0.5 mm off design, please print a
quick test of just the affected face and confirm before
committing to the full frame.

---

## Sanity checks before quoting

- [ ] All five STLs load as **manifold meshes** (no holes /
      inverted normals) in the slicer.
- [ ] All five STLs report as **single body** (1 connected
      component) in the slicer — NOT multiple disconnected pieces.
- [ ] Frame fits within the printer's build volume
      (200 × 155 × 70 mm including the 10 mm feet that drop below
      the device base — fits any modern desktop FDM).
- [ ] PETG filament in stock (or quote for an equivalent
      alternate).

If any of these fail, please contact the requester before
printing.

---

## Questions

For tolerance, material, or orientation questions, please reply
to the order or contact the requester directly. Designs are
parametric; minor adjustments regenerate quickly.
