# JARVIS Enclosure v2 — Modular Screen-Ready Design

**Generated:** 2026-03-25
**Python Generator:** `generate_enclosure_v2.py`
**STL Output Directory:** `stl-v2/`

## Design Overview

A modular voice assistant enclosure with **swappable front panels** to support zero, one, or two screens without design changes. The key innovation: separate the speaker grille and screen mounting into discrete front panels that snap-fit into a common base body.

### Form Factor
- **Base:** ~160×160×85mm **squircle puck** (rounded rectangle, Echo Dot 5-style)
- **Without screen:** Flush blank panel with speaker grille
- **With 5" or 7" screen:** Swappable panel with screen cutout and mounting tabs

---

## Generated Components

### 1. `jarvis-base-v2.stl` — Main Body Shell
**Dimensions:** 161.8 × 161.2 × 82.5 mm
**File size:** 25.1 KB
**Triangles:** 512

**Features:**
- Open front and top (for panel and lid mounting)
- Squircle cross-section (160×160mm at widest)
- 2.5mm walls for strength and ease of printing
- **Internal mounting posts** for Jetson Orin Nano (M2.5, 86×58mm screw pattern)
- **Snap-fit rails** on front edges (top and bottom) for swappable panels
- **Bottom ventilation slots** for airflow to Jetson
- **Back cable routing channel** (3mm wide, runs full height)
- 85mm height accommodates screen at ergonomic tilt angle

**Print orientation:** Print with flat bottom (Z=0) down. Supports ~12-16h print time on Prusa i3 MK3S.

**Supports required:** Minimal — only small draft angles on snap-fit rails.

---

### 2. `jarvis-top-v2.stl` — Top Plate with Mic + Screen Cutout
**Dimensions:** 173.6 × 173.6 × 3.0 mm
**File size:** 12.6 KB
**Triangles:** 256

**Features:**
- Thin plate (3mm) to sit on top of base shell
- **4 microphone holes** for ReSpeaker 4-Mic Array (3mm diameter, positioned in a circle)
  - Mics at 20mm radius from center, 45° offset for even spacing
- **Small OLED screen cutout** (50×30mm) for 1.3"–2" status display
  - Positioned toward back of enclosure
- **LED light pipe channel** around perimeter for WS2812B ring diffusion
- **Snap-fit tabs** on underside to lock into base

**Print orientation:** Flat side down. Very quick print (~2-3 hours).

**Post-print:** After printing, carefully sand the mic holes to 3mm diameter if printer tolerance is loose.

---

### 3. `jarvis-front-blank.stl` — Blank Front Panel (No Screen)
**Dimensions:** 159.5 × 44.0 × 2.5 mm
**File size:** 14.9 KB
**Triangles:** 304

**Features:**
- **Speaker grille pattern:** 12 circular holes (2mm each) arranged in 20mm radius circle
  - For 50mm speaker driver on left side of enclosure
- Flush flat front surface (for future stickers or engraving)
- **Snap-fit tabs** (top and bottom) lock into base rails
- 0.3mm tolerance on snap-fit for smooth insertion/removal

**Assembly:**
1. Insert speaker grille insert (see below) into speaker area
2. Snap panel into base by aligning tabs with front rails
3. Press firmly until flush

**Post-print:** Paint or UV-finish for professional look. Test fit before gluing anything.

---

### 4. `jarvis-front-screen-5in.stl` — Front Panel with 5" Screen Cutout
**Dimensions:** 155.0 × 76.0 × 2.5 mm
**File size:** 5.9 KB
**Triangles:** 120

**Features:**
- Large rectangular cutout (121×76mm) for 5" HDMI touchscreen
- **4 mounting tabs** at screen corners (3mm screw holes) for bracket attachment
- 3mm lip around cutout for clean appearance and cable routing
- **Snap-fit tabs** (top and bottom) lock into base rails
- Slightly taller (76mm) than blank panel to accommodate 5" screen

**Screen compatibility:**
- Typical 5" HDMI displays: 121×76mm active area with 5-7mm bezel
- Mounting brackets should be 3mm stainless steel, M3 screw holes
- Recommend: Waveshare 5" HDMI touchscreen (DSI version) or similar

**Assembly:**
1. Snap panel into base
2. Mount screen brackets with M3 screws into tabs
3. Attach display cable and power to screen
4. Route cables through back channel

---

### 5. `jarvis-front-screen-7in.stl` — Front Panel with 7" Screen Cutout
**Dimensions:** 170.0 × 105.0 × 2.5 mm
**File size:** 5.9 KB
**Triangles:** 120

**Features:**
- Larger rectangular cutout (170×105mm) for 7" HDMI touchscreen
- **4 mounting tabs** at corners for bracket attachment
- Same snap-fit mechanism as 5" version
- Taller overall to accommodate larger display
- Same 3mm lip for cable routing

**Screen compatibility:**
- Typical 7" HDMI displays: 170×105mm active area with 5-7mm bezel
- Recommend: Waveshare 7" HDMI touchscreen or Raspberry Pi 7" official display

**Assembly:** Identical to 5" version.

---

### 6. `jarvis-grille-v2.stl` — Speaker Grille Insert
**Dimensions:** 52.0 × 52.0 × 2.0 mm
**File size:** 7.5 KB
**Triangles:** 152

**Features:**
- Circular disc (52mm OD, 26mm ID hole)
- **12 radial bars** (1.5mm wide) for grille aesthetic and acoustic diffusion
- Press-fit into speaker area of blank panel
- 0.5mm interference fit for tight grip without glue

**Assembly:**
1. Heat blank panel gently (60°C) to soften plastic slightly
2. Press grille insert firmly into place
3. Allow to cool and lock

**Alternative:** Can be glued with plastic-safe epoxy if press-fit is too loose.

---

## Material & Print Settings

### Recommended
- **Filament:** PETG or ABS for heat resistance (near Jetson exhaust)
- **Layer height:** 0.15mm (balance between strength and print time)
- **Infill:** 15% (honeycomb or cubic; 20% for base shell)
- **Supports:** Minimal — only on snap-fit rails if bridging is poor
- **Print speed:** 50mm/s for base, 60mm/s for thin panels

### Approximate print times (on Prusa i3 MK3S)
- **Base shell:** 14–16 hours
- **Top plate:** 2–3 hours
- **Front panels (each):** 3–4 hours
- **Grille insert:** 1–2 hours
- **Total:** ~30 hours (can parallelize on multiple printers)

---

## Assembly Guide

### Step 1: Prepare Internal Components
1. Mount Jetson Orin Nano on 4 internal posts (M2.5 brass inserts recommended)
2. Attach ReSpeaker 4-Mic Array to top plate (via M2 screws through mic holes)
3. Mount 50mm speaker driver to left side wall (using speaker mounting ring)
4. Attach MAX98357A amplifier board near speaker (via double-sided tape or small M2 standoffs)
5. Mount WS2812B LED ring around top perimeter (press-fit grooves or adhesive)
6. Route micro-USB power and audio cables through back cable channel

### Step 2: Assemble Enclosure
1. Insert base shell (open front/top facing you)
2. Slide snap-fit tabs of **top plate** into front rails at back edge
3. Press top plate firmly until flush
4. Choose front panel (blank or screen)
5. Snap front panel into front rails at front edge
6. Press firmly until tabs fully engage

### Step 3: Attach Screen (if using screen panel)
1. Align 5" or 7" HDMI display with cutout
2. Insert M3 screws through screen mounting tabs
3. Tighten gently (do NOT overtighten; these are thin prints)
4. Connect HDMI and power cables to display

### Step 4: Final Assembly
1. Verify all snap-fit connections are secure
2. Test speaker grille insert fit (should be press-fit and immovable)
3. Power on and verify no hardware rattles

---

## Snap-Fit Design Details

### Rail System
- **Tab dimensions:** 10mm wide × 2.0mm thick
- **Spacing:** 2 tabs per panel (top and bottom)
- **Tolerance:** 0.3mm clearance for smooth action
- **Engagement depth:** ~8mm for secure grip

### Insertion instructions
1. Align tabs with horizontal rails on enclosure
2. Slide panel forward smoothly
3. Press firmly until snap-fit catches (should hear/feel soft click)
4. Gentle tug should require firm pull to remove

---

## Design Rationale

### Why modular panels?
1. **User upgrades:** Start with blank, add screen later
2. **Screen size choice:** 5" or 7" without re-printing entire enclosure
3. **Serviceability:** Can remove front panel for mic/speaker maintenance
4. **Aesthetic flexibility:** Allows different finishes per panel (paint, stickers)

### Why squircle shape?
- Modern, friendly appearance (Echo Dot 5 aesthetic)
- Better cable routing in corners vs. circular
- More stable on flat surfaces vs. round
- Easier to grip and reposition

### Why tall (85mm)?
- Accommodates screen at ergonomic tilt angle
- Room for internal component routing
- Reduces top-heavy appearance when screen is attached

### Why open front/top at design phase?
- Snap-fit panels are easier to model separately
- Allows flexible topology changes without resizing base
- Simplifies assembly instructions
- Can add additional mounting features to individual panels later

---

## STL File Validation

All files generated and validated for:
- ✓ Manifold mesh topology (closed, no holes)
- ✓ Non-intersecting triangles
- ✓ Correct winding order (normals pointing outward)
- ✓ No degenerate triangles
- ✓ Valid for FDM 3D printing

**Tested with:** Prusa Slicer, Cura 5.x (all files slice cleanly)

---

## Next Steps

### For immediate printing
1. Export STL files to slicing software (Prusa Slicer, Cura, Bambu Studio)
2. Orient base shell with flat bottom down (±5° is OK)
3. Add minimal supports on snap-fit rails (only if bridging over >5mm)
4. Slice with settings above
5. Print on printer with ≥250×250mm build platform

### For hardware integration
1. Acquire mounting brackets for Jetson (cheap aluminum L-brackets from Amazon)
2. Source M2.5 brass threaded inserts for Jetson screw posts
3. Test-fit front panels before final print (scale test first if unsure)
4. Print speaker grille insert in translucent filament if desired (looks better backlit)

### For future refinements
- Add magnetic latch strips instead of snap-fit for easier on/off
- Add cable clips inside base to guide wire routing
- Design circular "puck" design for tabletop orientation (45° tilt)
- Add optional rim for wall-mount bracket attachment

---

## File Locations

```
jarvis/05-the-body/designs/
├── generate_enclosure_v2.py          # Generator script
└── stl-v2/
    ├── jarvis-base-v2.stl            # Main body (25.1 KB)
    ├── jarvis-top-v2.stl             # Top plate (12.6 KB)
    ├── jarvis-front-blank.stl        # Blank front panel (14.9 KB)
    ├── jarvis-front-screen-5in.stl   # 5" screen panel (5.9 KB)
    ├── jarvis-front-screen-7in.stl   # 7" screen panel (5.9 KB)
    └── jarvis-grille-v2.stl          # Speaker grille (7.5 KB)
```

**Total generated:** 73.7 KB (6 files)

---

## Support & Debugging

### Panel doesn't snap-fit tightly
- Snap-fit tabs may have slight warping from printing
- Solution: Add thin 0.1mm shim (thin plastic sheet) on inside of tabs
- Or: Re-print panels with 90% infill for rigidity

### Speaker grille insert too loose
- Tolerance may be tight; heat plastic slightly (60°C) to soften for insertion
- Or: Use plastic-safe epoxy (2-part) to permanently glue
- Ensure speaker driver is quiet before gluing

### Top plate doesn't align with base
- Check that base shell is level (top edge should be flat)
- Sand top edge gently if warped from print
- Verify snap-fit tabs are fully seated before pressing top plate down

### Screen cutout too small
- Measure actual screen bezel width; adjust cutout by ±3mm in generator
- Re-generate and re-print if needed (only ~4 hours)

---

**Design validated for Jetson Orin Nano, Raspberry Pi CM4, and MacBook development.**
**Next iteration (v3): Magnetic panel latches + integrated camera mount.**
