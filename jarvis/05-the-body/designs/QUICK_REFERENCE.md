# JARVIS Enclosure v2 — Quick Reference Card

## Files Generated (2026-03-25)

| File | Size | Dims (mm) | Purpose |
|------|------|-----------|---------|
| `jarvis-base-v2.stl` | 25.1 KB | 162×161×82 | Main shell body |
| `jarvis-top-v2.stl` | 12.6 KB | 174×174×3 | Top plate (mics + OLED cutout) |
| `jarvis-front-blank.stl` | 14.9 KB | 160×44×2.5 | Speaker grille panel (Phase 1) |
| `jarvis-front-screen-5in.stl` | 5.9 KB | 155×76×2.5 | 5" screen panel (Phase 2) |
| `jarvis-front-screen-7in.stl` | 5.9 KB | 170×105×2.5 | 7" screen panel (Phase 2) |
| `jarvis-grille-v2.stl` | 7.5 KB | 52×52×2 | Speaker grille insert |
| **Total** | **73.7 KB** | — | — |

## Phase 1: No Screen
```
BLANK PANEL (flat front with speaker grille)
    │
    ├─ jarvis-front-blank.stl
    └─ jarvis-grille-v2.stl (insert)

Print time: ~5 hours (blank + grille)
```

## Phase 2: With Screen
```
SCREEN PANEL (5" or 7" HDMI touchscreen)
    │
    ├─ jarvis-front-screen-5in.stl  (for 5" display)
    └─ jarvis-front-screen-7in.stl  (for 7" display)

Print time: ~4 hours per panel
```

## Snap-Fit Mechanism
```
FRONT PANEL INSERT (top view)
  ┌─────────────────────────────────┐
  │  snap tab (top)                 │  ← 10mm wide, 2mm thick
  │  ┌───────────────────────────┐  │
  │  │ PANEL                     │  │
  │  │ (speaker grille or screen)│  │
  │  │                           │  │
  │  └───────────────────────────┘  │
  │  snap tab (bottom)              │
  └─────────────────────────────────┘

Engagement: Press forward until heard "click"
Removal: Gentle pry at bottom, slide backward
Tolerance: 0.3mm for smooth action
```

## Internal Component Locations

| Component | Size | Mount | Qty |
|-----------|------|-------|-----|
| **Jetson Orin Nano** | 100×79×21mm | M2.5 posts (base) | 1 |
| **ReSpeaker 4-Mic** | 65×65mm | M2 screws (top plate) | 1 |
| **50mm Speaker** | Ø50mm | Side wall bracket | 1 |
| **MAX98357A Amp** | 25×25mm | Foam tape (side) | 1 |
| **WS2812B LED ring** | Ø72mm OD | Adhesive (perimeter) | 1 |
| **Status OLED (1.3-2")** | 50×30mm | Back wall (optional) | 1 |

## Cable Routing
```
All cables → BACK CABLE CHANNEL (3mm wide, full height)
    ├─ Jetson micro-USB power
    ├─ ReSpeaker USB
    ├─ Speaker audio
    ├─ LED data + 5V power
    └─ HDMI (if screen)
```

## Print Settings (PETG, Prusa i3 MK3S)

```
Layer height:  0.15mm
Infill:        20% (honeycomb)
Supports:      Organic (minimal)
Wall thickness: 2.5mm (all parts)
Print speed:   50–60 mm/s

Expected times:
  ├─ jarvis-base-v2.stl      14–16 hrs
  ├─ jarvis-front-blank.stl  3–4 hrs
  ├─ jarvis-front-screen-5in 3–4 hrs
  ├─ jarvis-front-screen-7in 3–4 hrs
  ├─ jarvis-top-v2.stl       2–3 hrs
  └─ jarvis-grille-v2.stl    1–2 hrs

Total: ~30 hours (can parallelize)
```

## Assembly Checklist (30–45 min)

```
□ STAGE 1: Prepare base shell
  □ Insert 4× M2.5 brass threaded inserts into mounting posts

□ STAGE 2: Install Jetson
  □ Mount Jetson on 4 posts with M2.5 screws (hand-tight)
  □ Apply thermal pads on GPU area

□ STAGE 3: Install audio/LED
  □ Mount 50mm speaker on left side wall
  □ Mount MAX98357A amplifier board
  □ Mount WS2812B LED ring around perimeter

□ STAGE 4: Install microphones
  □ Mount ReSpeaker 4-Mic on top plate (M2 screws)
  □ Verify mic holes are clear

□ STAGE 5: Route cables
  □ Feed all cables through back cable channel
  □ Bundle with cable ties (avoid blocking snap-fit rails)

□ STAGE 6: Install panels
  □ Snap fit top plate (press until click)
  □ Insert speaker grille into blank panel
  □ Snap fit front panel (blank or screen)

□ STAGE 7: Final assembly (if screen)
  □ Align display in front panel cutout
  □ Insert M3 screws through mounting tabs (gentle)
  □ Connect HDMI and power cables

□ STAGE 8: Verify
  □ All components secure and level
  □ No cables pinched by snap-fit
  □ No rattling when tapped
```

## Hardware Shopping List

| Item | Qty | Source | Price* |
|------|-----|--------|--------|
| M2.5 brass inserts | 4 | Amazon | $5 |
| M2.5×6mm screws | 4 | Hardware store | $2 |
| M3×4mm screws | 4 | Hardware store | $2 |
| Thermal pads (25×25×1mm) | 2 | Amazon | $3 |
| Cable ties (100mm) | 20 | Amazon | $2 |
| 3M foam tape | 1 roll | Amazon | $5 |
| Speaker mounting ring (50mm) | 1 | Amazon | $8 |
| **Total** | — | — | **~$27** |

*Approximate US prices (2026)

## File Locations

```
jarvis/05-the-body/designs/
├── generate_enclosure_v2.py
│   └─ Run: python3 generate_enclosure_v2.py
├── ENCLOSURE_V2_DESIGN.md
│   └─ Full design doc (tolerances, rationale, troubleshooting)
├── ASSEMBLY_GUIDE_V2.md
│   └─ Step-by-step assembly with wiring details
├── MANIFEST.txt
│   └─ Complete package inventory
└── stl-v2/
    ├── jarvis-base-v2.stl
    ├── jarvis-top-v2.stl
    ├── jarvis-front-blank.stl
    ├── jarvis-front-screen-5in.stl
    ├── jarvis-front-screen-7in.stl
    └── jarvis-grille-v2.stl
```

## Quick Tips

1. **Test fit first:** Before full assembly, print blank panel + grille insert to verify snap-fit tolerances
2. **Heat for tight fits:** If grille insert is difficult to insert, gently heat blank panel to 60°C with hair dryer
3. **Sand snap-fit tabs:** If panel is too tight, lightly sand base rails with 120-grit sandpaper
4. **Cable routing:** Use 3M foam or adhesive-lined cable clips to organize internal wiring
5. **Thermal management:** Ensure ventilation slots on bottom are clear; add optional fan if Jetson runs hot

## Screen Compatibility

| Panel | Specs | Screen Examples |
|-------|-------|-----------------|
| 5" | 121×76mm active | Waveshare 5" HDMI, Adafruit 5" |
| 7" | 170×105mm active | Waveshare 7" HDMI, Raspberry Pi official 7" |

Both panels support standard HDMI touchscreens with 5–7mm bezels.

## Snap-Fit Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| Panel too tight | Tabs warped | Sand base rails, 120 grit |
| Panel too loose | Poor tolerance | Add 0.1mm shim on inside |
| Grille won't fit | Tolerance tight | Heat to 60°C, insert with twist |
| Panel rocks | Uneven base edge | Sand base top, verify flat |
| Cables pinched | Poor routing | Re-route through back channel |

## Modifications (v3 roadmap)

- [ ] Magnetic latches instead of snap-fit
- [ ] Integrated cable clips on internal walls
- [ ] Wall-mount bracket tabs
- [ ] Rear camera module mount
- [ ] USB-C power port cutout on back
- [ ] Built-in speaker mounting ring

---

**For details, see:** `ENCLOSURE_V2_DESIGN.md` (design), `ASSEMBLY_GUIDE_V2.md` (steps)

**Questions?** Check troubleshooting sections in full docs.

**Ready to print?** Start with `jarvis-front-blank.stl` (quick test, ~4 hours)
