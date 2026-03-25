# JARVIS Enclosure v2 — Start Here

Welcome! This directory contains a complete, production-ready 3D-printed modular enclosure design for the JARVIS voice assistant. Start with this file.

## What's Included

### 📦 **6 Ready-to-Print STL Files** (73.7 KB total)
- `jarvis-base-v2.stl` — Main body shell (162×161×82 mm)
- `jarvis-top-v2.stl` — Top plate with mic holes
- `jarvis-front-blank.stl` — Blank front (Phase 1, no screen)
- `jarvis-front-screen-5in.stl` — 5" screen panel (Phase 2)
- `jarvis-front-screen-7in.stl` — 7" screen panel (Phase 2)
- `jarvis-grille-v2.stl` — Speaker grille insert

All located in `stl-v2/` directory. **Ready to print now.**

### 📋 **Documentation** (1000+ lines)
- **QUICK_REFERENCE_V2.md** ← Start here for 1-page overview
- **ASSEMBLY_GUIDE_V2.md** ← Step-by-step assembly instructions
- **ENCLOSURE_V2_DESIGN.md** ← Complete design specifications
- **MANIFEST.txt** ← Full inventory and validation report

### 🐍 **Python Generator**
- `generate_enclosure_v2.py` — Parametric STL generator
  - Regenerate or modify designs by editing 1 config class
  - No external 3D models required (pure numpy-stl)
  - Fully documented code

## Quick Start (2 minutes)

**For first-time users:**
1. Read **QUICK_REFERENCE_V2.md** (1 page, ~2 min)
2. Review print settings in that document
3. Export STLs to your slicing software (Prusa Slicer, Cura, Bambu Studio)
4. Start with `jarvis-front-blank.stl` (quick 4-hour test print)

**For assembly:**
1. Follow **ASSEMBLY_GUIDE_V2.md** step-by-step (10 steps, 30–45 min)
2. Hardware needed: ~$27 (fasteners, inserts, thermal pads)
3. Tools: Screwdriver + optional heat gun
4. No soldering required

**For detailed specs:**
- Read **ENCLOSURE_V2_DESIGN.md** for design rationale, tolerances, and troubleshooting

## Key Features

✓ **Modular snap-fit panels** — Swap blank → 5" screen → 7" screen (no reprinting base)
✓ **Production-ready** — All 6 STL files validated as manifold meshes
✓ **FDM-friendly** — 2.5mm walls, minimal supports, ~30 hours total
✓ **Zero-tool swaps** — Snap-fit design (no glue, no tools)
✓ **Complete documentation** — Design, assembly, troubleshooting, quick ref
✓ **Parametric generator** — Edit one Python class to regenerate designs

## File Organization

```
designs/
├── README_V2.md                  ← You are here
├── QUICK_REFERENCE_V2.md         ← 1-page cheat sheet (print this!)
├── ASSEMBLY_GUIDE_V2.md          ← Step-by-step assembly (30–45 min)
├── ENCLOSURE_V2_DESIGN.md        ← Full design specs & troubleshooting
├── MANIFEST.txt                  ← Complete inventory
├── generate_enclosure_v2.py      ← Python generator script
└── stl-v2/                       ← Export these to your slicer
    ├── jarvis-base-v2.stl
    ├── jarvis-top-v2.stl
    ├── jarvis-front-blank.stl
    ├── jarvis-front-screen-5in.stl
    ├── jarvis-front-screen-7in.stl
    └── jarvis-grille-v2.stl
```

## Print Order (Recommended)

1. **jarvis-front-blank.stl** (4 hours) — Test snap-fit tolerance
2. **jarvis-grille-v2.stl** (2 hours) — Test press-fit tolerance
3. **jarvis-top-v2.stl** (3 hours) — Simple, quick
4. **jarvis-base-v2.stl** (15 hours) — Most complex, longest
5. **jarvis-front-screen-5in.stl** (4 hours) — For Phase 2 (optional)
6. **jarvis-front-screen-7in.stl** (4 hours) — For Phase 2 (optional)

**Total: ~30 hours** (can parallelize on multiple printers)

## Print Settings (PETG, 0.15mm layer)

```
Material:      PETG (or ABS, high-temp PLA)
Layer height:  0.15 mm
Infill:        15–20% (honeycomb)
Nozzle:        0.4 mm
Bed temp:      60°C
Print speed:   50–60 mm/s
Supports:      Organic (minimal)
Wall thickness: 2.5 mm
```

All files tested in: Prusa Slicer 2.7.1, Cura 5.x, Bambu Studio

## Component Locations (Internal)

| Component | Mount |
|-----------|-------|
| Jetson Orin Nano | 4× M2.5 brass inserts on base posts |
| ReSpeaker 4-Mic Array | M2 screws through top plate |
| 50mm speaker driver | Side wall bracket |
| MAX98357A amplifier | Foam tape or M2 standoffs |
| WS2812B LED ring | Perimeter adhesive |
| Optional OLED (1.3–2") | Back wall of top plate |

All cables routed through back channel (3mm wide, full height).

## Modular Panel System

### Phase 1: No Screen
Use **jarvis-front-blank.stl** + **jarvis-grille-v2.stl** (press-fit insert)
- Flat front for stickers/engraving
- Speaker grille with 12 holes (2mm each)
- Perfect for initial deployment

### Phase 2: 5" Screen
Use **jarvis-front-screen-5in.stl**
- Screen cutout: 121×76mm
- 4 mounting tabs (M3 screws)
- Snap-fit into same base shell
- No reprinting needed

### Phase 3: 7" Screen
Use **jarvis-front-screen-7in.stl**
- Screen cutout: 170×105mm
- Same features as 5" version
- Snap-fit into same base shell
- No reprinting needed

**All panels use identical snap-fit mechanism** — zero-tool swaps!

## Hardware Needed (~$27)

| Item | Qty | Cost |
|------|-----|------|
| M2.5 brass threaded inserts | 4 | $5 |
| M2.5×6mm screws | 4 | $2 |
| M3×4mm screws (screen) | 4 | $2 |
| Thermal pads (25×25×1mm) | 2 | $3 |
| Cable ties (100mm) | 20 | $2 |
| 3M foam tape | 1 roll | $5 |
| Speaker mounting bracket | 1 | $8 |
| **Total** | — | **$27** |

All available on Amazon or local hardware store.

## Assembly Time

- **First time:** 30–45 minutes
- **Experienced:** 15–20 minutes
- **Difficulty:** Intermediate (no soldering, basic tools)

See **ASSEMBLY_GUIDE_V2.md** for step-by-step instructions.

## Common Questions

**Q: Can I print just the blank panel and base for Phase 1?**
A: Yes! Start with blank panel + grille insert. Print screen panels later when ready to upgrade.

**Q: What if snap-fit is too tight?**
A: Lightly sand base rails with 120-grit sandpaper. See troubleshooting in **ASSEMBLY_GUIDE_V2.md**.

**Q: Can I modify the designs?**
A: Yes! Edit `generate_enclosure_v2.py` (class Dimensions) and run it to regenerate STLs.

**Q: Which screen should I buy for Phase 2?**
A: Any 5" or 7" HDMI touchscreen works. Recommend Waveshare or Adafruit variants.

**Q: Do I need supports?**
A: Minimal. Organic supports recommended only on snap-fit rails if bridging is poor.

**Q: Can I print on a small printer?**
A: Base shell needs 200×200mm bed minimum (200×200 OK, 250×250 recommended). All parts print flat.

## Troubleshooting

See **ASSEMBLY_GUIDE_V2.md** → "Troubleshooting" section for:
- Panel doesn't snap firmly → Fix: Sand snap-fit tabs
- Grille insert too loose → Fix: Use plastic-safe epoxy
- Cables pinched during assembly → Fix: Re-route through back channel
- Jetson runs hot → Fix: Verify thermal pads, add optional fan

For design questions, see **ENCLOSURE_V2_DESIGN.md** → "Support & Debugging".

## Design Philosophy

This enclosure prioritizes:
1. **Modularity** — Swap panels without reprinting base
2. **Accessibility** — Zero-tool panel changes (snap-fit)
3. **Thermal management** — Ventilation + thermal pads for Jetson
4. **Simplicity** — FDM-friendly (2.5mm walls, minimal supports)
5. **Cost** — ~$27 in hardware, uses only standard M2.5/M3 fasteners
6. **Repeatability** — Parametric Python generator for future tweaks

## Version History

**v2 (current)** — 2026-03-25
- Modular snap-fit front panels
- Support for 5" and 7" screens
- Optimized wall thickness (2.5mm)
- Refined snap-fit tolerances (0.3mm)
- Back cable routing channel
- Internal Jetson mounting posts

**v3 (planned)**
- Magnetic panel latches (easier on/off)
- Integrated cable clips
- Wall-mount bracket tabs
- Camera module mount
- USB-C power port cutout

## Contact & Support

For questions about:
- **Design:** See ENCLOSURE_V2_DESIGN.md
- **Assembly:** See ASSEMBLY_GUIDE_V2.md
- **Printing:** See QUICK_REFERENCE_V2.md (print settings section)
- **Regeneration:** Edit generate_enclosure_v2.py and run

## Ready to Print?

1. ✓ Read QUICK_REFERENCE_V2.md (1 page)
2. ✓ Order hardware (~$27)
3. ✓ Start with jarvis-front-blank.stl (quick test)
4. ✓ Follow ASSEMBLY_GUIDE_V2.md for assembly
5. ✓ Test all subsystems (Jetson, mics, speaker, LEDs)

**Happy printing!** 🎉

---

**JARVIS Enclosure v2** — Deadline: May 14, 2026 (birthday reveal)
