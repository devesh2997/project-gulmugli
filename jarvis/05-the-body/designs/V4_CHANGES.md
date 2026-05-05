# Enclosure v4 — what changed from v3

V3 was sized tightly around a specific BOM: ReSpeaker 4-Mic Array,
MAX98357A I²S amp, 50 mm bare-wire speaker, all on a tightly-packed
breadboard. V4 keeps the same design language but adds **modest
internal buffer** because the actual mic + amp combo is undecided
across three hardware paths (see `jarvis/05-the-body/HARDWARE_NOTES.md`).

## External envelope

| Dimension | v3 | v4 | Δ |
|---|---|---|---|
| Width  | 190 mm | **200 mm** | +10 mm |
| Height | 135 mm | **145 mm** | +10 mm |
| Depth  | 60 mm  | **70 mm**  | +10 mm |

Volume increase: ~22%. Print time goes up by ~10-15% (frame from
~12-14h to ~14-16h).

## What the buffer buys you

- **+10 mm depth** is the most important: rear cavity goes from
  ~28.5 mm (tight for a breadboard + components) to ~38.5 mm
  (comfortable for breadboard OR USB-dongle pocket OR a small
  powered speaker driver).
- **+10 mm width** smooths cable routing on both sides of the
  screen. Was tight at 190 mm.
- **+10 mm height** gives more room above and below the screen for
  the LED bar, mic, and decorative bezel breathing room.

## What didn't change

- **Screen mounting geometry.** Same Waveshare 7" LCD assumed; same
  158 × 93 mm M3 mount pitch and same active-area cutout. Screen
  drops in identically.
- **Jetson mounting.** Same 86 × 58 mm M2.5 standoff pattern on the
  back panel. Same port-cluster cutout.
- **Speaker.** Same 50 mm circular cutout in the bottom face with
  decorative grille pattern. Same VHB-mount surface inside.
- **LED bar.** Same 175 mm × 12 mm slot across the bottom front.
  Diffuser STL is unchanged in cross-section (only longer to fit
  the new W).
- **Side openings + acrylic panels.** Same rabbet depth, same
  magnet pockets, same N42 6×3 mm magnets for snap-mount.
- **Belt zone.** Still 32 mm tall, just re-centered for the new
  H = 145 mm (belt center moves from y = 67.5 → y = 72.5).

## What's still flexible after v4

The buffer is sized for any of these mic + amp paths:

1. **INMP441 (single I²S mic) + MAX98357A amp on breadboard** —
   breadboard fits with ~10 mm clearance behind the screen module
2. **USB sound-card dongle + USB lavalier mic + small powered
   speaker** — dongle pocket fits anywhere along the rear wall;
   lav mic clips to the inside of the top face
3. **Original boards + soldering help** — same as #1

Any of the three paths uses the same v4 print, just different
internal mounting (wires + tape, no enclosure changes).

## Files

```
stl-v4/
├── jarvis-frame-v4.stl          (35 KB, 716 triangles)
├── jarvis-back-panel-v4.stl     (33 KB, 668 triangles)
├── jarvis-led-diffuser-v4.stl   (684 B, 12 triangles)
├── jarvis-side-panel-v4.dxf     (977 B)
└── MANIFEST.txt
```

Total bundle: ~70 KB. Email-attachable; no need to zip for transfer.

## Regenerating

```
cd jarvis/05-the-body/designs
python3 generate_enclosure_v4.py
```

Deterministic — running it again produces byte-identical output
unless `generate_enclosure_v4.py:make_v4_frame()` changes. To bump
dimensions further, edit that function and re-run.

## v3 → v4 migration

If you've already shared v3 STLs with a print shop and want to
upgrade: hand them v4 with the same instructions. Print settings
are identical. Materials are identical. Assembly process is
identical (the v3 assembly guide applies; only "fits comfortably"
becomes "fits very comfortably").

If v3 prints already exist and assembly hasn't started: they still
work. The buffer is "nice to have," not strictly required for
Path 3 (the original I²S BOM).
