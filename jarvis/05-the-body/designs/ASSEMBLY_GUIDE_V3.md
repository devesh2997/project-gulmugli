# JARVIS Enclosure v3 — Assembly Guide

**Form factor:** Tablet-on-side framed display (190 × 135 × 60mm).
**Designed around:** Waveshare 7inch HDMI LCD (C) Rev 4.1 + Jetson Orin Nano Super dev kit.
**Aesthetic:** Matte-black opaque frame + clear acrylic side windows + light-grey wool felt belt + RGB LED status bar.

This document walks through every step from "files generated" to "powered-on demo."

---

## 0. Bill of materials

### Already on hand
- Jetson Orin Nano Super Dev Kit + 19V 45W barrel adapter
- Waveshare 7inch HDMI LCD (C) Rev 4.1 — confirmed, Spotpear-branded variant
- ReSpeaker 4-Mic Array (USB, 65×65mm)
- 50mm 4Ω speaker driver + MAX98357A I2S amp
- NVMe SSD with JetPack 6.x flashed
- Wipro smart bulb (dev/test)
- HDMI cable + micro-USB cable (came with screen — both short)

### To order (~₹3,000–4,000 total)

| Item | Qty | Source | Notes |
|---|---|---|---|
| WS2812B 60-LED/m strip, 5V | 1m | Robocraze / Robu.in | Cut to lengths: 12-LED bottom bar (≈200mm), 6-LED ×2 belt-glow strips (≈100mm each) |
| N42 neodymium disc magnets, 6×3mm | 8 | Amazon.in | 4 per side panel × 2 sides; +spares |
| M3 stainless washers (12mm OD) | 8 | Hardware shop | Glue 4 per acrylic panel — magnetic keepers |
| M3 brass threaded inserts | 4 | Robu / Amazon | For screen mounting posts in front face |
| M3 × 6mm stainless screws | 4 | Hardware shop | Screen to frame |
| M2.5 brass threaded inserts | 4 | Robu / Amazon | For Jetson mounting posts in back panel |
| M2.5 × 8mm stainless screws | 4 | Hardware shop | Jetson to back panel |
| Wool felt sheet, light grey, 1.5mm thick, ~50×80cm | 1 | Sadar Bazaar (Delhi, ~30 min from Gurgaon) or Amazon "wool felt sheet 1.5mm" | Plenty for belt + alternates |
| Steel belt-keeper strip, 5mm × 0.5mm × 1m | 1 | Hardware shop | Glued inside frame at belt height; magnetic anchor for felt belt |
| 3M VHB or strong double-sided tape, 6mm | 1 roll | Hardware shop | Mounts speaker, MAX98357A, LED strips |
| 3mm clear cast acrylic sheet, ~30×30cm | 1 | Local laser-cut shop (any signage shop on MG Road / Sector 14 / Cyber Hub) | Two side panels cut from this — bring `jarvis-side-panel-v3.dxf` |
| Cable ties, 100mm small | 20 | Hardware shop | Internal cable management |
| Noctua NF-A4x10 5V fan (insurance only) | 1 | Amazon.in | Install only if thermal testing shows >75°C |

### Print services (Gurgaon-based, recommended)

For the three STLs (`jarvis-frame-v3`, `jarvis-back-panel-v3`, `jarvis-led-diffuser-v3`):

- **Local Gurgaon FabLab / 3D print service** — strongly preferred. Search "3D printing service Gurgaon" or check Sector 21 / Cyber Hub area. Walk-in shops do same-day or 1-day turnaround at ₹3,500–5,000 for the full set. Critical advantage: if dimensions are off, you can re-print one part overnight.
- **3Ding (Chennai)** — ~₹3,500 for the set; 4-6 day delivery to Gurgaon.
- **Robu.in 3D Printing** — ~₹3,000; 5-7 day delivery.

Material recommendation: **PETG, matte black** for frame and back panel; **clear / natural PLA** for the LED diffuser.

---

## 1. Print settings

```
Material:       PETG (frame + back panel)
                Clear PLA (LED diffuser)
Layer height:   0.2mm (frame), 0.15mm (diffuser — finer for light transmission)
Infill:         20% honeycomb (frame), 100% (diffuser — solid for diffusion)
Wall thickness: 2.5mm (4 perimeters at 0.4mm nozzle)
Supports:       Tree/organic, only on bottoms of internal screen standoffs
                and Jetson standoffs in back panel
Bed temp:       70°C (PETG), 60°C (PLA)
Print speed:    50mm/s outer perimeters, 80mm/s infill

Print orientation:
  jarvis-frame-v3.stl       — front face DOWN (best front finish)
  jarvis-back-panel-v3.stl  — flat side DOWN (port-cluster face up)
  jarvis-led-diffuser-v3.stl — flat (any orientation)
```

Approximate print times on a Prusa MK4 / Bambu A1:
- Frame: 12–14 hours
- Back panel: 2.5–3 hours
- LED diffuser: 45 min
- **Total: ~16 hours**, parallelizable across 2 printers in 14 hours

---

## 2. Pre-build verification (do BEFORE assembly)

Order matters — fix issues now, not at 11pm on May 13th.

1. **Check screen mounting hole pitch.** Place the screen face-down on a soft cloth. Measure horizontal pitch between left mounting hole and right mounting hole, and vertical pitch between top and bottom holes. They should be **158 × 93mm** (the values in `generate_enclosure_v3.py:Screen`). If they differ by >2mm, edit `Screen.mount_pitch_w` and `Screen.mount_pitch_h` in the generator and re-run **before printing**.
2. **Test-fit screen tabs into frame holes** *before* installing inserts. The four 3.4mm holes in the frame's interior should align with the screen's M3 corner tabs. If misaligned, sand or re-print the frame.
3. **Test-fit Jetson onto back-panel standoffs.** The Jetson's 4 mounting holes should drop onto the four standoffs without forcing.
4. **Test-fit acrylic panel into side opening.** Should slide into place flush with outer side surface, with ~0.5mm play. If too tight: sand the acrylic edges. If too loose: print a 0.5mm shim or add felt strips around the edge.

---

## 3. Step-by-step assembly

**Tools needed:** Phillips screwdriver, 3.5mm hand drill (for drilling brass-insert pockets), soldering iron (for LED strips), wire strippers, cable ties.

### Step A — Prepare the frame (15 min)

1. Inspect the print — sand any layer-line ridges on the front face with 220-grit, especially around the screen cutout. Smooth.
2. **Drill brass-insert pockets** in the four screen-mounting standoffs on the inside of the front face. Use a 4.0mm drill bit, depth ~5mm. Press in M3 brass inserts using a soldering iron at 220°C (heat-set inserts; 5-second contact each).
3. Drill 4.0mm pockets for the Jetson M2.5 brass inserts on the four standoffs in the back panel. Heat-set M2.5 inserts.
4. **Drill magnet pockets** in the 8 corners of the side openings (4 per side, one at each corner of the rectangular opening). Use a 6.2mm drill bit at 3mm depth. The magnets press-fit; secure with a tiny dab of CA glue.
5. **Glue steel belt-keeper strip** along the belt zone on the inside of the frame. The belt zone is at y=51.5mm to y=83.5mm (32mm tall band centered at y=67.5mm). Cut a 5mm-wide steel ribbon to ~150mm length and glue it to the inside of the front strip just inside the cavity, with strong adhesive (epoxy or VHB).

### Step B — Mount the screen (10 min)

1. Remove the screen's protective film from the LCD glass.
2. Place the screen face-down on a soft cloth. Identify the 4 corner mounting tabs (visible in the photos as small extensions beyond the PCB).
3. From INSIDE the frame, slide the screen toward the front face so the 4 corner holes align with the 4 brass inserts.
4. Drive 4× M3×6 screws through the screen tabs into the inserts. Tighten gently — don't crush the PCB tabs.
5. Verify: screen LCD active area is centered in the front cutout. The black LCD bezel should be hidden behind the matte-black frame edges.

### Step C — Wire and mount the LED bar (15 min)

1. Cut the WS2812B strip to **12 LEDs** (≈200mm). The strip should fit in the LED-bar slot at the bottom of the front face.
2. Solder 3 wires to the strip's input end:
   - **Red (5V)** — 22 AWG to JST connector
   - **Black (GND)** — same
   - **Green (Data IN)** — to the LED-controller GPIO pin
3. Peel the LED strip's adhesive backing and stick it to the inside of the front face, directly behind the LED bar slot. Center horizontally.
4. Snap the **LED bar diffuser** (frosted/natural PLA print) into the slot from outside. It should friction-fit.

### Step D — Wire and mount the belt-glow LEDs (15 min)

1. Cut TWO 6-LED segments from the WS2812B strip.
2. Each segment goes inside the frame on the **left and right walls** at belt height (y ≈ 51.5–83.5mm range). Stick to the inside of the frame at the belt zone center, oriented horizontally so the LEDs face outward through the side opening.
3. Wire the two segments in series (output of segment 1 → input of segment 2) so they appear as 12 contiguous LEDs to the controller. Run the wires up over the top edge of the frame interior to the controller area.

### Step E — Mount the speaker (10 min)

1. The speaker driver fits into the speaker mounting ring on the bottom face (visible from outside as a 50mm circle on the bottom).
2. Apply VHB tape around the rim of the speaker driver and press it onto the mounting ring from inside. Center the cone over the speaker hole.
3. Wire the speaker to the **MAX98357A I2S amp board**:
   - Speaker + → MAX98357A `OUT+`
   - Speaker - → MAX98357A `OUT-`
4. Mount the MAX98357A board on the inside back wall using foam tape, near the speaker.
5. Wire the MAX98357A to the Jetson's I2S pins (see `WIRING_V3.md` for pin map):
   - VIN → 5V
   - GND → GND
   - DIN → I2S TX
   - LRC → I2S LRCLK
   - BCLK → I2S BCLK

### Step F — Mount the ReSpeaker mic (10 min)

1. Drill 4 mic holes through the top face (3mm dia each) at the positions shown in the print — they're marked as small dimples on the top of the print. Use a 3mm bit, drill straight through.
2. Place the ReSpeaker board on the **inside** of the top face with the 4 mics aligned with the holes you drilled.
3. Secure with M2 screws through the ReSpeaker's mounting holes into the top face. If the print doesn't have receiving holes, drill 1.6mm pilot holes and use self-tapping M2 screws.
4. Connect the ReSpeaker's USB cable to one of the Jetson's USB ports.

### Step G — Mount the Jetson (5 min)

1. Place the Jetson Orin Nano dev kit onto the four standoffs on the back panel. The Jetson's 4 mounting holes should align with the brass M2.5 inserts.
2. Secure with 4× M2.5×8 screws.
3. Position the back panel near the rear of the frame (don't snap in yet — leave room for cable routing).

### Step H — Cable routing (15 min)

This is the part that determines whether assembly is clean or messy. Take time.

1. **Screen → Jetson HDMI**: connect the short HDMI cable from screen's HDMI port (on the screen's right side as viewed from front, left edge of PCB) to one of Jetson's HDMI outputs. Route the cable around the right side of the screen, over the top of the Jetson, and into Jetson's HDMI port.
2. **Screen → Jetson USB (touch + power)**: micro-USB cable from screen's micro-USB port to one of Jetson's USB-A ports.
3. **MAX98357A → Jetson I2S**: 5 wires (5V, GND, DIN, LRC, BCLK) running from amp to Jetson 40-pin GPIO header.
4. **WS2812B LED data**: GREEN data wire from LED bar input + belt-glow input → Jetson GPIO pin (e.g., pin 12 = BCM 18). Wire RED (5V) and BLACK (GND) to Jetson 5V/GND pins.
5. Use cable ties to bundle all wires neatly along the inside of the frame edges, away from the Jetson's heatsink.

### Step I — Snap on the back panel (5 min)

1. Align the 4 corner snap tabs on the back panel with the matching grooves in the frame. (NB: if the frame doesn't have receiving grooves yet — they're a v3.1 todo — secure the back with 4× M3 screws through the corners into pillars in the frame.)
2. Press the back panel firmly until tabs click into place.
3. Verify the Jetson's rear ports (Ethernet, USB, HDMI input, power) align with the port-cluster cutout in the back panel.

### Step J — Mount the acrylic side panels (5 min)

1. Glue 4 M3 steel washers to the inside face of each acrylic panel at the 4 corner positions (etch marks on the DXF show where). Use CA glue or epoxy.
2. Hold an acrylic panel against a side opening — it should snap into place magnetically. The 6×3mm N42 magnets in the frame attract the steel washers in the acrylic.
3. Repeat for the other side.

### Step K — Wrap the felt belt (5 min)

1. Cut the felt sheet to a strip: **width = 32mm**, **length = belt circumference = 2 × (D - 2) + 2 × W = 2×58 + 2×190 = 496mm + 30mm overlap = ~530mm**.
2. Wrap the felt around the device at the belt zone (y=51.5–83.5mm, the middle band). The felt should:
   - Cross the back of the device (snaps to the steel keeper strip via magnets sewn into the felt)
   - Wrap across the left and right side openings (visible glow zone)
   - End somewhere on the back, not on the front
3. Optional: sew tiny neodymium magnets into the inside of the felt at the back overlap point, so the belt holds onto the steel keeper strip. Or use velcro.

### Step L — Power on (5 min)

1. Plug the Jetson's 19V barrel adapter in.
2. Power on. The screen should illuminate and show JetPack boot.
3. Watch for first audio response from the speaker.
4. Test mics with: `arecord -l` should show ReSpeaker. `arecord -D plughw:1,0 -f S16_LE -r 16000 -d 5 test.wav && aplay test.wav`
5. Test LEDs with the existing `assistant/providers/voice/...` LED helper or a quick Python script using `rpi_ws281x`.

---

## 4. Tuning + iteration

If something doesn't fit / look right:

- **Screen too high or low in the cutout**: edit `Frame.led_bar_h` or `mid_h` in `generate_enclosure_v3.py:build_frame_meshes()`, regenerate, reprint just the frame.
- **Jetson doesn't fit**: check `Frame.D` (depth) — increase to 65mm.
- **LED bar too dim**: print the diffuser at 50% infill instead of 100% (less PLA = more transmission). Or sand the diffuser surface lightly.
- **Belt doesn't stay up**: increase magnet count from 8 to 12, OR switch to velcro under the belt overlap.
- **Speaker rattles**: add foam gasket between driver and mounting ring.

---

## 5. Wiring quick reference

```
                     ┌────────────────────┐
                     │   Jetson Orin Nano │
                     │                    │
       ┌─────────────┤ HDMI ───┐ USB ─────┤
       │             │ I2S pins│ GPIO 18  │
       │             └─────────┴──────────┘
       │                  │         │
       │                  │         │
   ┌───▼───┐         ┌────▼───┐ ┌──▼────────────┐
   │ Screen│         │ MAX98357│ │ WS2812B strip │
   │ HDMI  │         │ I2S amp │ │  bottom bar  │
   │ +USB  │         └─────┬───┘ │  + belt glow │
   │ touch │               │      └───────────────┘
   └───────┘            ┌──▼──┐
                        │50mm  │
                        │spkr  │
                        └─────┘

   ┌──────────────┐
   │  ReSpeaker   │ ← USB to Jetson
   │  4-mic array │
   └──────────────┘

LED data line (single 24-LED strand, addressed by Jetson):
  GPIO 18 → bottom bar (12 LEDs, indices 0-11) → left belt (6 LEDs, 12-17) → right belt (6 LEDs, 18-23)
```

LED state-machine code already lives in `assistant/providers/...` — adapt the existing 24-LED ring code; the address scheme is identical, just split functionally:
- Indices 0-11 → status bar (idle/listening/thinking/speaking/etc.)
- Indices 12-23 → ambient/personality glow

---

## 6. Sourcing notes (Gurgaon-specific)

**Felt** — Sadar Bazaar (Delhi, ~30 min from Gurgaon) has the entire fabric district. Wool felt is sold by the meter. Light grey 1.5mm wool felt should be ~₹150–300 per meter. Alternatives: Amazon search "wool felt sheet 1.5mm light grey" delivers in 2 days, ₹200–400.

**Acrylic + laser cutting** — any signage shop in Sector 14, MG Road, Cyber Hub does this. Bring the DXF on a USB stick. ~₹100–200 per cut for our small panels. Same-day usually.

**Hardware (M3, M2.5, magnets, washers)** — Robocraze.com (Bangalore, 2-day delivery) is the most reliable single source. Or Amazon.in (1-2 day delivery).

**Magnets specifically** — search Amazon.in for "neodymium 6mm 3mm disc N42" — multiple sellers, ~₹250-400 for a pack of 20.

---

## 7. Known limitations / v3.1 wishlist

- **Snap-fit tabs in main frame** — the back panel has tabs but the frame doesn't yet have matching grooves; for v3 first iteration, secure the back panel with 4 corner screws instead. v3.1 will add proper grooves.
- **No fan mount** — if thermal testing shows Jetson >75°C under load, the next revision will integrate a Noctua NF-A4x10 fan mount above the Jetson.
- **Mic holes are drill-after-print** — current STL doesn't punch the holes (slicer artifacts on small features); user drills 4× 3mm holes after print using the stencil marks on the top face.
- **Speaker grille is a single hole** — no decorative hole pattern. The speaker driver itself has a protective grille, and the bottom-firing orientation hides it.
- **No status OLED** — the v2 design had an optional 1.3" OLED on the top plate. Not included in v3 since the front 7" screen serves the same purpose.

---

## 8. Final check before declaring "done"

- [ ] Screen powers on, displays JetPack boot
- [ ] Touch input works (`evtest /dev/input/eventX` shows touch events)
- [ ] Mic array detected (`arecord -l` shows ReSpeaker)
- [ ] Speaker plays audio (`aplay /usr/share/sounds/alsa/Front_Center.wav`)
- [ ] LED bar lights up in test colors
- [ ] Belt-glow LEDs visible through felt
- [ ] All ports accessible from back panel
- [ ] No cable rattling inside enclosure
- [ ] Jetson temp < 75°C under sustained LLM load
- [ ] Felt belt stays in place when device is moved
- [ ] Acrylic side panels stay attached when device is tilted

---

**Generated:** 2026-05-04
**Author:** JARVIS enclosure team
**For:** Birthday reveal May 14, 2026

If anything in this document doesn't match what you see during build, that's a bug in the generator or this guide — log it in `notes/v3-build-issues.md` and we'll fix in v3.1.
