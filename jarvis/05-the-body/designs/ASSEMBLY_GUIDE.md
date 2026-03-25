# JARVIS Enclosure v2 — Quick Assembly Guide

**Difficulty:** 🟡 Intermediate (no soldering, some precision needed)
**Time:** 30–45 minutes
**Tools required:**
- Screwdriver (Phillips/Pozidriv for M2.5 and M3)
- Optional: Heat gun (60°C) for tight fits
- Small cable ties for wire management

---

## Bill of Materials (Hardware Only)

| Item | Qty | Size | Source | Purpose |
|------|-----|------|--------|---------|
| Brass threaded inserts | 4 | M2.5×3mm | Amazon | Jetson mounting posts |
| Screws | 4 | M2.5×6mm | Hardware store | Jetson to inserts |
| Screws | 4 | M3×4mm | Hardware store | Screen mounting (if using screen) |
| Thermal pads | 2 | 25×25×1mm | Amazon | Jetson heat dissipation |
| Cable ties | 10 | 100mm | Amazon | Wire routing |
| Double-sided tape | 1 | 3M foam tape | Amazon | Amplifier mounting |

**Electronics (already owned):**
- Jetson Orin Nano Dev Kit
- ReSpeaker 4-Mic Array USB hat
- 50mm speaker driver (any impedance 4-16Ω)
- MAX98357A amplifier board
- WS2812B addressable LED ring (24 LEDs, 72mm OD)
- 5" or 7" HDMI touchscreen (optional)
- Micro-USB power cable
- HDMI cable (optional)
- 3.5mm audio jack or speaker connectors

---

## Assembly Steps

### ⓪ Pre-Assembly Check
Before starting, verify all 3D-printed parts:
- [ ] `jarvis-base-v2.stl` — main body, no cracks
- [ ] `jarvis-top-v2.stl` — top plate, mic holes clear
- [ ] Front panel (blank or screen) — snap-fit tabs intact
- [ ] `jarvis-grille-v2.stl` — speaker grille insert, no warping

**Note:** Light sanding of snap-fit tabs (120 grit) can improve fit.

---

### ① Prepare Base Shell for Internal Components

**Jetson mounting:**
1. Identify 4 internal mounting posts on base shell (one at each corner, ~50mm from edges)
2. Gently insert M2.5 brass threaded inserts into posts
   - Use insert tool or small screwdriver to twist in gently
   - Do NOT force; inserts should thread smoothly into plastic
3. Verify all 4 inserts sit flush with post tops

**Cable routing channel:**
1. Inspect back wall of enclosure for thin vertical channel (3mm wide)
2. This will route USB power and audio cables; leave clear

---

### ② Mount Jetson Orin Nano

1. **Position:** Jetson should sit flat on bottom of enclosure, 30mm from front edge
2. **Alignment:** Top of Jetson should be ~23mm from bottom (to clear micro-USB port for connectors)
3. **Screwing:** Insert 4 M2.5×6mm screws through Jetson mounting holes into threaded inserts
   - Tighten gently; do NOT overtighten (plastic can strip)
   - Use light hand-tightness ("finger + quarter turn" with screwdriver)
4. **Thermal pads:** Stick thermal pads on top of Jetson's GPU area (stick to plastic, not directly to chip)

**Verify:** Jetson should be rock-solid and level.

---

### ③ Mount Speaker Driver

1. **Position:** 50mm speaker driver on left side wall, ~80mm from front edge, 40mm up from bottom
2. **Mounting method:** Use speaker mounting ring (if available) or 4 small M2 standoffs
3. **Orientation:** Speaker cone pointing outward (into blank/screen panel space)
4. **Secure:** Tighten with small M2 screws; ensure no vibration

**Verify:** Gently push on speaker cone; should not flex excessively.

---

### ④ Install MAX98357A Amplifier Board

1. **Position:** Near speaker driver, on same side wall
2. **Mounting:** Use double-sided 3M foam tape or small M2 standoffs
3. **Wiring:**
   - Data line (DIN) → Jetson GPIO pin (GPIO17 default, or configure)
   - Clock (BCLK) → Jetson GPIO pin (GPIO27 default)
   - Sync (LRCLK) → Jetson GPIO pin (GPIO22 default)
   - GND → Jetson GND
   - See `config.yaml` for pin configuration
4. **Speaker connection:** Solder or use push-fit connectors to 50mm driver

**Note:** Do NOT power on amplifier until Jetson is fully assembled and config is verified.

---

### ⑤ Mount ReSpeaker 4-Mic Array

1. **Position:** Will sit on top plate, centered
2. **Alignment:** 4 mic holes on top plate should align with 4 corner holes on ReSpeaker PCB
3. **Screwing:** Use M2 screws through holes, into ReSpeaker mounting posts
   - Tighten gently
4. **USB cable:** Connect USB cable from ReSpeaker to Jetson USB 3.0 port
   - Route cable along back wall through cable channel
5. **Audio input:** If ReSpeaker has 3.5mm audio output, connect to MAX98357A DIN line

**Verify:** Mic array should sit flat and level on top plate.

---

### ⑥ Install WS2812B LED Ring

1. **Position:** Around perimeter of enclosure, between top plate and back wall
2. **Mounting:** Use clear silicone adhesive or small U-channel clips
3. **Alignment:** LEDs should be visible from top when top plate is installed
4. **Wiring:**
   - Data (DIN) → Jetson GPIO pin (GPIO18 default)
   - GND → Jetson GND
   - 5V power → External power supply (do NOT draw from Jetson GPIO; LEDs pull 1.5A peak)
5. **Cable routing:** Feed power and data cables through back cable channel

**Verify:** All LEDs light up when powered (test with simple script).

---

### ⑦ Install Optional Small OLED Screen (1.3–2")

1. **Position:** Mount on back wall of top plate
2. **Mounting:** Use double-sided tape or small M2 standoffs
3. **Alignment:** Should be centered on top plate, ~50×30mm cutout
4. **Wiring:**
   - I2C (SDA/SCL) → Jetson I2C pins (GPIO2/GPIO3 default)
   - GND/5V → Jetson power
5. **Connection:** Small OLED via short USB or I2C ribbon cable

**Optional:** Use for status display (time, volume, mic status icons).

---

### ⑧ Route All Cables

1. **Back channel:** Feed all cables (USB, audio, LED power) through 3mm back wall channel
2. **Cable ties:** Use small ties to bundle and secure cables to internal posts (if added in future revision)
3. **Avoid:** Do NOT let cables pinch when snap-fit panels are inserted
4. **Test:** Verify nothing blocks when panels are snapped in/out

---

### ⑨ Snap Fit Top Plate

1. **Alignment:** Top plate has snap-fit tabs on underside (front and back edges)
2. **Insertion:** Slide top plate forward along front rails (from back toward front)
3. **Engagement:** Press firmly until you feel/hear soft click (tabs lock into rails)
4. **Verification:** Gentle tug should require firm pull to remove

**Note:** If top plate is tight, remove and lightly sand snap-fit tabs on base rails (120 grit).

---

### ⑩ Install Front Panel (Blank or Screen)

#### **Option A: Blank Panel + Grille Insert**

1. **Grille insert preparation:**
   - If press-fit is tight, gently heat blank panel to 60°C (hair dryer on low)
   - Hold grille insert with tweezers
2. **Insertion:** Press grille insert firmly into speaker cutout area (left side of panel)
   - Should sit flush or slightly recessed
   - If too loose, apply thin line of plastic-safe epoxy around edge
3. **Panel snap-fit:**
   - Align snap-fit tabs (top and bottom) with front rails on base
   - Slide panel forward smoothly
   - Press firmly until click
4. **Verify:** Panel should be flush with base edges; no gaps

#### **Option B: Screen Front Panel (5" or 7")**

1. **Panel snap-fit:** Same as blank panel above
2. **Screen mounting brackets:**
   - Align 5" or 7" HDMI display in front panel cutout
   - Insert M3×4mm screws through screen mounting tabs
   - Tighten gently (do NOT overtighten; thin plastic)
3. **Cable routing:**
   - HDMI cable → route along back channel from Jetson to screen
   - Power cable → route to external power supply
   - Connect cables to screen back panel
4. **Verify:** Screen should be flush and centered in cutout

**Tip:** If screen has bezel, ensure bezel is fully seated against lip on front panel for best appearance.

---

## Final Checks

- [ ] All screws tightened (but not stripped)
- [ ] No cables pinched by snap-fit panels
- [ ] Top plate and front panel both click and are secure
- [ ] Speaker driver makes no rattling sound when tapped
- [ ] No internal parts touching enclosure walls
- [ ] Cable routing through back channel is organized
- [ ] Thermal pads on Jetson feel secure (sticky)
- [ ] (Optional) All LEDs light up and respond to commands
- [ ] (Optional) Microphone array picks up voice from all directions

---

## Power-On Sequence

1. **Before first power:**
   - Verify all GPIO pins are correctly configured in `config.yaml`
   - Test Jetson with external display (HDMI monitor) separately if possible
   - Verify Ollama is running on Jetson or MacBook (if using remote inference)

2. **First power-on:**
   - Plug Jetson micro-USB power (15W recommended)
   - Let Jetson boot (takes ~30 seconds)
   - LEDs should flash briefly during startup
   - Listen for speaker (should make soft "ready" tone if configured)

3. **Test sequence:**
   - `python main.py --text` to verify voice assistant boots
   - Speak near microphone array; verify LED ring reacts
   - Test speaker output: "play Sajni" (should search YouTube Music)

---

## Troubleshooting

### Panel doesn't snap firmly
- **Check:** Snap-fit tabs are bent or warped
- **Fix:** Lightly sand tabs with 120 grit sandpaper, round edges slightly
- **Or:** Add thin 0.1mm shim on inside of rails for tighter fit

### Speaker grille insert is loose
- **Check:** Tolerance may be too tight or too loose
- **Fix (if loose):** Wrap thin electrical tape around insert edge for diameter increase
- **Fix (if tight):** Heat plastic to 60°C, insert with gentle twist motion
- **Permanent:** Use plastic-safe epoxy around entire edge

### Top plate rocks or is uneven
- **Check:** Snap-fit tabs on base shell may be warped
- **Fix:** Gently sand base shell snap-fit rail edges with 120 grit until smooth
- **Or:** Verify base shell printed level (no warping on bottom)

### Cable getting pinched when inserting panel
- **Check:** Cables in back channel are not routed cleanly
- **Fix:** Re-route cables; ensure they stay in center of back channel, not touching side walls
- **Use:** Small cable ties to bundle cables out of insertion path

### Jetson runs hot
- **Check:** Thermal pads are in contact with Jetson GPU
- **Check:** Fan not blocked by any internal walls
- **Add:** Small 40mm fan on side wall pointing at Jetson (optional upgrade)

### Microphone array not picking up sound
- **Check:** ReSpeaker USB cable is fully seated on Jetson USB port
- **Check:** Mic holes on top plate are not blocked (no dust, no solder blob)
- **Check:** Jetson sees ReSpeaker in USB device list (`lsusb` on command line)

---

## Disassembly (if needed)

**To remove top plate:**
1. Gently lift rear edge of top plate
2. Slide backward toward back wall
3. Lift straight up

**To remove front panel:**
1. Gently pry bottom edge of front panel away from base
2. Slide backward (out of snap-fit rails)
3. Lift straight up

**To remove Jetson:**
1. Unplug USB and audio cables
2. Remove 4 M2.5 screws (hand-tight removal)
3. Lift Jetson straight up and out

---

## Next Steps

After assembly:
1. Power on and verify all components respond to commands
2. Run song disambiguation eval against baseline to confirm improvement
3. (Optional) 3D print cable clips to organize internal wiring in next revision
4. (Optional) Design and print alternative front panels (dark, translucent, with logos)

---

**Estimated total assembly time: 30–45 minutes (first time)**
**Once familiar: 15–20 minutes**

Good luck! 🎉
