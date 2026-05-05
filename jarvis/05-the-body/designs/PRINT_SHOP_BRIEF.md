# Print Shop Brief — Vesper Enclosure v4

**One-page handout for a 3D-print shop / laser-cut shop.**
Send this PDF + the four files in `stl-v4/` and the print shop has
everything they need to quote and produce.

---

## What's being made

A small desktop appliance enclosure, **roughly 200 × 145 × 70 mm**
(W × H × D), shaped like a tablet on its side. It houses:

- A 7" HDMI LCD (front face, screen visible)
- A small computer (NVIDIA Jetson, mounted to the back panel)
- A speaker (fires downward through the bottom)
- A microphone (top face)
- A WS2812B LED bar (across the bottom front)
- Two clear acrylic side windows

Three FDM-printed parts + one laser-cut acrylic panel (cut twice —
left and right sides).

---

## Files

All in `stl-v4/`:

| File | Type | Material | Quantity | Approx. weight |
|---|---|---|---|---|
| `jarvis-frame-v4.stl` | FDM print | **PETG, matte black** | 1 | ~340 g |
| `jarvis-back-panel-v4.stl` | FDM print | **PETG, matte black** | 1 | ~80 g |
| `jarvis-led-diffuser-v4.stl` | FDM print | **Clear / natural PLA** | 1 | ~3 g |
| `jarvis-side-panel-v4.dxf` | Laser cut | **3 mm clear cast acrylic** | **2** | (≈30×30 cm sheet covers both with offcuts) |

Total FDM filament budget: ~450 g. Standard 1 kg spool covers it
twice over.

---

## Material recommendation

| Part | Material | Why |
|---|---|---|
| Frame, back panel | **PETG, matte black, ±0.05 mm tolerance** | PETG holds tolerances better than PLA in Indian summer (no warping at 40 °C+ ambient); matte black hides the LCD bezel cleanly. |
| LED diffuser | **Clear or natural PLA, 100% infill** | Natural PLA is pleasantly translucent — exactly what an LED diffuser wants. PETG would also work but tends to come out more milky-cloudy and is harder to print at 100% infill cleanly. |
| Side windows | **3 mm clear cast acrylic** (NOT extruded) | Cast acrylic laser-cuts with cleaner edges and better optical clarity. Extruded acrylic is OK if cast isn't available, but flag if so. |

If matte black PETG isn't stocked, **glossy black is acceptable**
(less visually preferred but mechanically identical). Avoid TPU,
ABS, or any flexible material.

---

## Print settings (FDM)

```
Printer:       Any 0.4 mm nozzle FDM (Prusa MK3/4, Bambu A1/X1, Ender 3+, Creality K1)
Layer height:  0.2 mm  (frame, back panel)
               0.15 mm (LED diffuser — finer for light transmission)
Walls:         4 perimeters (= 1.6 mm wall thickness; design wall is 2.5 mm)
Infill:        20% honeycomb / gyroid (frame, back panel)
               100% (LED diffuser — solid for diffusion)
Supports:      Tree / organic, only on bottoms of internal screen
               standoffs and Jetson standoffs in back panel
Build plate:   Bed temp 70 °C (PETG), 60 °C (PLA)
Print speed:   50 mm/s outer perimeters, 80 mm/s infill
Brim:          5 mm (PETG specifically — first-layer adhesion)

Print orientation:
  jarvis-frame-v4.stl       — front face DOWN on build plate (the
                              FACE that has the screen cutout —
                              gives the cleanest front finish)
  jarvis-back-panel-v4.stl  — flat side DOWN, port-cluster face UP
  jarvis-led-diffuser-v4.stl — flat (any orientation, no supports needed)
```

Approximate print times on a typical FDM printer:

| Part | Time |
|---|---|
| Frame | 14–16 hours |
| Back panel | 3–4 hours |
| LED diffuser | 45–60 min |
| **Total** | **~18–21 hours** sequential, or ~14 h if frame and back panel run on two printers in parallel |

---

## Laser-cut acrylic settings

```
Material:      3 mm clear cast acrylic, 1 sheet ~30×30 cm
Quantity:      Cut TWICE (left and right side windows are identical
                — same DXF gives both panels)
Cutter power:  Whatever the shop normally uses for 3 mm acrylic
               (typical 80 W CO₂ laser at 18-22 mm/s, 100% power)
Edge finish:   Standard polished edge from cast acrylic is sufficient;
               no flame-polishing needed.
```

The DXF defines a single rectangle with 4 corner mounting marks
(small etched circles where steel washers will be glued for magnetic
mounting). Both panels are identical so cut the same DXF twice.

---

## Tolerance notes

These are the dimensions where mis-tolerance causes assembly issues:

- **Screen cutout** (front face): rectangular hole sized to expose
  the LCD active area. Designed at 154 × 86 mm with 1.5 mm overhang
  on each side hiding the bezel. Print accurate to ±0.3 mm.
- **Screen mounting standoffs** (interior, behind front face): four
  M3 brass-insert pockets, each 4 mm dia × 5 mm deep. The user
  drills these post-print to receive heat-set inserts — print
  needs the marker dimples to be visible and approximately on
  the design coordinates.
- **Side opening** (rabbet for acrylic panel): the acrylic should
  slide in flush with ~0.5 mm play. If shop tolerance is
  unusually tight (<±0.1 mm), a 0.5 mm shim might be needed; if
  loose, acrylic gets sanded to fit.
- **Snap-fit between back panel and frame**: 4 corner snap pillars.
  Tolerance ±0.2 mm is fine — anything more and snap-fit doesn't
  click.

If any dimension comes out >0.5 mm off design, print a quick test
of just the affected face before reprinting the whole frame.

---

## Cost estimate (Indian print shops, May 2026)

Based on quotes from Robu.in, 3Ding, and local Gurgaon FabLabs:

| Part | Material | Approx. cost |
|---|---|---|
| Frame (PETG, 340g) | PETG | ₹1,800 – ₹2,400 |
| Back panel (PETG, 80g) | PETG | ₹500 – ₹700 |
| LED diffuser (PLA, 3g) | PLA | ₹100 – ₹200 |
| 2× acrylic side panels | 3 mm cast | ₹400 – ₹700 (set of 2) |
| **Total** | | **₹2,800 – ₹4,000** |

Local Gurgaon shops generally come in at the lower end of this
range AND have 1-day turnaround — strongly preferred over
shipping from out of city. The frame is the long-pole print
(~15 hours); a shop with parallel printers can do everything
overnight.

---

## What's flexible / what's fixed

The user is mid-decision on some hardware so the enclosure has
**internal buffer**:

- **Fixed**: Waveshare 7" HDMI LCD (Rev 4.1, 1024×600). Screen
  cutout and mounting holes are sized exactly for this model.
- **Fixed**: NVIDIA Jetson Orin Nano dev kit. Back panel mounting
  posts and port-cluster cutout are sized for this board.
- **Fixed**: 50 mm round speaker, fires downward. Bottom face has
  a circular cutout + decorative grille for it.
- **Flexible**: microphone choice — top face has marker dimples,
  user drills based on whether ReSpeaker (4 holes), single I²S
  mic (1 hole), or USB lavalier (passthrough hole) is chosen.
- **Flexible**: amp board choice — the +10 mm depth buffer means
  either an I²S amp on a breadboard OR a USB sound-card dongle
  fits inside without modifications.

The print shop **does not need to know which hardware path is
chosen** — just print the four files as-is.

---

## Quick sanity-check before quoting

Print shop should validate:

- [ ] All 3 STLs load as **manifold meshes** (no holes / inverted
      normals) in their slicer
- [ ] Frame fits within their printer's build volume
      (200 × 145 × 70 mm — fits any modern desktop FDM)
- [ ] PETG filament is in stock (or quote for alternate)
- [ ] Cast acrylic 3 mm is in stock for the laser-cut panels

If any of those fail, contact the requester before printing.

---

## Contact / questions

For technical questions about the design (tolerances, alternate
materials, print orientation), reply to the order with your
specific question and we'll respond within a day. The design
generator is Python and parameter-driven — minor changes
(e.g., screen swap to 5", different speaker size) regenerate in
seconds and we can ship updated files quickly.

---

## Files included in the bundle

```
stl-v4/
├── jarvis-frame-v4.stl          ← print 1× in PETG
├── jarvis-back-panel-v4.stl     ← print 1× in PETG
├── jarvis-led-diffuser-v4.stl   ← print 1× in clear/natural PLA
└── jarvis-side-panel-v4.dxf     ← laser-cut 2× in 3 mm clear acrylic

PRINT_SHOP_BRIEF.md              ← this file
ASSEMBLY_GUIDE_V3.md             ← (reference — assembly steps; v3 and
                                    v4 use the same assembly process)
```
