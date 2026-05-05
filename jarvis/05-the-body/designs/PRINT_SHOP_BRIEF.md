# Print Shop Brief — Vesper Enclosure v4

A small desktop appliance enclosure, **200 × 145 × 70 mm**
(W × H × D), shaped like a tablet on its side. This brief covers
two bundles; only one will be sent for any given order.

---

## Bundle reference

| Bundle | Side panels | Vendor flow |
|---|---|---|
| **v4-solid** | PETG, 3D-printed | Single print shop |
| **v4 (windowed)** | 3 mm clear cast acrylic, laser-cut | Print shop + laser-cut shop |

The two bundles share the same frame, back panel, and LED diffuser
STL files. They differ only in how the side panels are produced.
Side-panel exterior dimensions are identical across both bundles,
so a future swap from PETG to acrylic (or vice-versa) requires no
frame changes.

---

## What's being made

A single enclosure that houses:

- A 7" HDMI LCD (front face, screen visible)
- A small computer (NVIDIA Jetson, mounted to the back panel)
- A speaker (fires downward through the bottom)
- A microphone (top face)
- A WS2812B LED bar (across the bottom front)
- Two side panels (PETG or acrylic, depending on bundle)

---

## v4-solid bundle

All in `stl-v4-solid/`:

| File | Material | Quantity | Approx. weight |
|---|---|---|---|
| `jarvis-frame-v4.stl` | PETG, matte black | 1× | ~340 g |
| `jarvis-back-panel-v4.stl` | PETG, matte black | 1× | ~80 g |
| `jarvis-side-panel-v4.stl` | PETG, matte black | **2×** | ~25 g each |
| `jarvis-led-diffuser-v4.stl` | Clear / natural PLA | 1× | ~3 g |
| `jarvis-side-panel-v4.dxf` | (not used by this bundle — ignore) | — | — |

Total filament: ~470 g.

---

## v4 (windowed acrylic) bundle

All in `stl-v4/`:

| File | Material | Quantity |
|---|---|---|
| `jarvis-frame-v4.stl` | PETG, matte black | 1× |
| `jarvis-back-panel-v4.stl` | PETG, matte black | 1× |
| `jarvis-led-diffuser-v4.stl` | Clear / natural PLA | 1× |
| `jarvis-side-panel-v4.dxf` | 3 mm clear cast acrylic, laser-cut | **2×** |

This bundle requires a laser-cut step in addition to FDM printing.

---

## Material specifications

| Part | Material | Notes |
|---|---|---|
| Frame, back panel, side panels (v4-solid) | PETG, matte black, ±0.05 mm tolerance | PETG holds tolerances better than PLA in warm ambient temperatures. Matte black hides the LCD bezel cleanly. |
| LED diffuser | Clear or natural PLA, 100 % infill | Natural PLA gives the desired translucency for an LED diffuser. PETG would be milky-cloudy at 100 % infill. |
| Side panels (v4 windowed only) | 3 mm clear cast acrylic (NOT extruded) | Cast acrylic laser-cuts with cleaner edges and better optical clarity. |

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
| Side panels (×2, v4-solid only) | 1.5 hours each = 3 hours |
| LED diffuser | 45–60 min |
| **Total v4-solid** | **~21–24 hours** sequential |
| **Total v4 (windowed)** | **~18–21 hours** sequential |

Two printers in parallel cuts the wall-clock to ~14–16 h either way.

---

## Laser-cut acrylic settings (v4 windowed only)

```
Material:      3 mm clear cast acrylic, 1 sheet ~30 × 30 cm
Quantity:      Cut 2× (left and right are identical)
Cutter power:  Whatever the shop uses for 3 mm acrylic
                 (typical 80 W CO₂ at ~20 mm/s, 100 % power)
Edge finish:   Standard polished cast-acrylic edge is sufficient
```

The DXF defines a single rounded-rectangle outline plus 4 corner
etch marks (washer mounting positions for assembly).

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

- [ ] All STLs load as **manifold meshes** (no holes / inverted
      normals) in the slicer.
- [ ] Frame fits within the printer's build volume
      (200 × 145 × 70 mm — fits any modern desktop FDM).
- [ ] PETG filament in stock (or quote for an equivalent
      alternate).
- [ ] (v4 windowed bundle only) 3 mm clear cast acrylic
      available at the laser-cut partner shop.

If any of these fail, please contact the requester before
printing.

---

## File bundle reference

```
stl-v4-solid/
├── jarvis-frame-v4.stl          ← print 1× in PETG
├── jarvis-back-panel-v4.stl     ← print 1× in PETG
├── jarvis-side-panel-v4.stl     ← print 2× in PETG
├── jarvis-led-diffuser-v4.stl   ← print 1× in clear/natural PLA
├── jarvis-side-panel-v4.dxf     ← not used by this bundle
└── MANIFEST.txt

stl-v4/
├── jarvis-frame-v4.stl          ← print 1× in PETG
├── jarvis-back-panel-v4.stl     ← print 1× in PETG
├── jarvis-led-diffuser-v4.stl   ← print 1× in clear/natural PLA
├── jarvis-side-panel-v4.dxf     ← laser-cut 2× in 3 mm clear acrylic
└── MANIFEST.txt
```

---

## Questions

For tolerance, material, or orientation questions, please reply
to the order or contact the requester directly. Designs are
parametric; minor adjustments regenerate quickly.
