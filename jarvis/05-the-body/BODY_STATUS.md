# JARVIS Body — Hardware Enclosure Status

**Last updated:** March 25, 2026
**Deadline:** May 14, 2026 (50 days remaining)
**Status:** ✓ Enclosure CAD complete, ready for printing

## Completed

- [x] **Enclosure 3D models** — Three modular STL files generated:
  - `jarvis-base.stl` (58.9 KB) — Bottom shell with Jetson posts, speaker mount, ventilation
  - `jarvis-top.stl` (30.4 KB) — Top plate with mic holes, LED channel, snap-fit tabs
  - `jarvis-grille.stl` (30.4 KB) — Speaker grille insert (press-fit)

- [x] **Generator script** — `generate_enclosure_stl.py` (fully functional)
  - Creates valid, manifold STL meshes ready for slicing
  - All geometry utilities implemented (squircle profile, cylinders, boxes, extrusions)
  - Tested and verified: all three files generate successfully

- [x] **Component integration** — CAD accounts for all parts:
  - Jetson Orin Nano (100×79×21 mm) + M2.5 mounting posts
  - ReSpeaker 4-Mic Array (65×65×9 mm) + 4 mic holes
  - 24-LED WS2812B ring (72 mm) + light pipe channel
  - Speaker driver (40–50 mm) + mounting boss
  - MAX98357A amplifier board (~25×25 mm)

- [x] **Assembly documentation** — `ENCLOSURE_README.md` includes:
  - Step-by-step assembly instructions
  - Cable routing guide
  - Print settings (layer height, infill, support strategy)
  - Troubleshooting tips for Ultimaker, Creality, Bambulab

## Next Phase: Manufacturing (March 26 — April 15)

### Print & Assemble (Week 1–2)
1. **Order prints** from Craftcloud, Xometry, or Shapeways
   - Budget: ~$80–150 for full enclosure prototype
   - Lead time: 3–5 business days
   - Material: PLA recommended (PETG if thermal testing shows need)

2. **Receive parts** → test fit all components
   - Jetson with M2.5 posts
   - ReSpeaker mic holes alignment
   - Speaker grille snap-fit tabs
   - Snap-fit top plate tabs

3. **Iterate on tolerances** (if needed)
   - Scale snap-fit tabs ±2–3% in slicer
   - Adjust screw post hole sizes based on measurements
   - Reprint single part if issues found

### Integration Testing (Week 3–4)
1. Install all components
2. Test thermal management (thermal imaging under load)
3. Acoustic testing (speaker driver + grille)
4. LED light transmission (LED ring inside light pipe channel)
5. Verify all cable routing works

### Final Polish (Week 4–5)
1. Sand and smooth all external surfaces
2. Paint (matte black recommended for aesthetic)
3. Apply LED diffusers if needed
4. Final assembly and photography for birthday reveal

## Component Status

| Component | Status | Owner | Notes |
|-----------|--------|-------|-------|
| **Enclosure CAD** | ✓ Ready | ET | STL files generated |
| **Jetson Orin Nano** | ✓ Acquired | ET | In development |
| **ReSpeaker 4-Mic** | ✓ Testing | ET | Confirmed layout in CAD |
| **WS2812B Ring** | ✓ Available | ET | 24-LED, 72 mm outer Ø |
| **Speaker Driver** | ✓ Available | ET | 40–50 mm, 4–8 Ω |
| **MAX98357A Amp** | ✓ Available | ET | 3.7W @ 4 Ω |
| **M2.5 Screw Posts** | ✓ Ready | ET | 10 mm tall, brass inserts |
| **Thermal Pads** | Ordered | ET | 1–2 mm, TIM150 or similar |

## File Locations

```
project-gulmugli/jarvis/05-the-body/
├── BODY_STATUS.md                    ← You are here
├── designs/
│   ├── generate_enclosure_stl.py     # Generator script (executable)
│   ├── ENCLOSURE_README.md           # Assembly guide + design rationale
│   └── stl/
│       ├── jarvis-base.stl           # 58.9 KB, 1,204 triangles
│       ├── jarvis-top.stl            # 30.4 KB, 620 triangles
│       └── jarvis-grille.stl         # 30.4 KB, 620 triangles
```

## How to Run the Generator

```bash
cd jarvis/05-the-body/designs
python3 generate_enclosure_stl.py
```

Output goes to `stl/` directory. Each run overwrites previous STL files.

## Customization Guide

### Modify Enclosure Dimensions
Edit `generate_enclosure_stl.py`:
- Line ~200: `outer_w, outer_h = 160, 160` → change outer dimensions
- Line ~205: `outer_height = 35` → change shell height
- Line ~260: `post_positions` → adjust Jetson mounting post locations
- Line ~275: `radius=20, height=8` → speaker mount size

### Add New Components
Example: adding a temperature sensor mount
```python
# In create_base_shell(), after speaker mount:
sensor_v, sensor_f = box_mesh(10, 10, 3, z_offset=25)  # 10×10×3mm box at z=25mm
sensor_v[:, 0] += 40  # position at X=40
sensor_v[:, 1] += 40  # position at Y=40
all_vertices.append(sensor_v)
all_faces.append(sensor_f + vertex_offset)
```

### Adjust Wall Thickness
Edit line ~185: `extrude_profile(outer_profile, 2.5, z_offset=0)` → change `2.5` to desired thickness.

### Change Corner Radius
Edit line ~78: `radius=20` in `squircle_points()` → adjust rounded corner radius.

## Known Limitations & Future Work

1. **Expansion bay cutout** — Currently a placeholder; proper Boolean subtraction needed for production.
   - Workaround: Use slicer (PrusaSlicer) to subtract 60×45 mm box manually.

2. **LED light pipe** — Design assumes translucent material or post-processing.
   - Consider: print in clear resin, or apply diffusant spray to top plate interior.

3. **Cable routing channel** — Simplified rectangular slot; could add custom clips for HDMI/USB.
   - Future: add gravity-assist cable supports inside channel.

4. **Thermal analysis** — Current design is empirical (2.5 mm wall thickness).
   - Future: run FEA simulation (SolidWorks, FreeCAD) to verify Jetson doesn't exceed 75°C at full load.

5. **Acoustic optimization** — Speaker grille hole pattern is radial grid.
   - Future: model impedance tube response, optimize hole diameter/spacing for speech (100–8000 Hz).

## Testing Checklist (Before May 14)

- [ ] All three STL files print without errors (Ultimaker/Creality test)
- [ ] Jetson fits in base with M2.5 posts
- [ ] ReSpeaker micro holes align with board screw holes
- [ ] Speaker driver press-fits into mounting boss
- [ ] WS2812B ring fits in LED channel (verify light transmission)
- [ ] Top plate snap-fit tabs click onto base (no manual force needed)
- [ ] Speaker grille press-fits into side opening (stays in place, doesn't rattle)
- [ ] Cable routing: power + HDMI fit through rear channel
- [ ] Thermal imaging: Jetson stays below 75°C under full load
- [ ] Acoustic test: speaker output audible at 1 meter
- [ ] Cosmetic: all surfaces smooth, no layer lines visible

## Birthday Reveal Plan (May 14)

1. Final assembly complete
2. Demo JARVIS with voice input, music playback, light control
3. Show enclosure with components visible (or translucent top for aesthetics)
4. Highlight hardware (Jetson, ReSpeaker, LED ring) with quick explainer

---

**Next action:** Order first print run from Craftcloud or Xometry (March 26–27).
