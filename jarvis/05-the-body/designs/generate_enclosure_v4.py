#!/usr/bin/env python3
"""
generate_enclosure_v4.py — buffer-padded enclosure for the unfinalized
hardware decision.

## Why v4 (not just regenerate v3)

V3 was sized tightly around a specific BOM:
  - Waveshare 7" LCD (fixed — confirmed)
  - ReSpeaker 4-Mic Array (65×65mm USB)
  - MAX98357A I2S amp on a tight breadboard layout
  - 50mm bare-wire speaker fired through the bottom

After the hardware checkpoint (jarvis/05-the-body/HARDWARE_NOTES.md),
the actual mic + amp + speaker combo is undecided across THREE paths:

  1. Pre-soldered INMP441 + MAX98357A + 50mm speaker (breadboard inside)
  2. USB sound-card dongle + small lavalier mic + small powered speaker
  3. Solder-helped originals (same internal layout as Path 1)

V3 fits Path 3 cleanly, fits Path 1 tightly, and fits Path 2 awkwardly
(no breadboard slack but also extra cables that need home).

V4 keeps the v3 design language (tablet-on-side framed display, 7"
LCD, snap-on back, side acrylic panels, LED bar across the bottom)
but adds **modest internal buffer** so all three paths fit:

  - Depth:  60 → 70 mm  (+10mm rear cavity for breadboard OR
                          USB-dongle pocket + powered speaker)
  - Width:  190 → 200mm (+10mm lateral; helps cable routing both
                          sides of the screen)
  - Height: 135 → 145mm (+5mm top, +5mm bottom — room for ReSpeaker
                          OR a single I²S mic OR a USB lav mic
                          all on the top face)

The screen, Jetson, speaker, and ReSpeaker mounting geometry stays
identical to v3 — only the enclosure shell grows. Internal mounts
that were already plenty-spaced (LED bar, magnet pockets, side
opening rabbets) scale with the new external dimensions.

## What this script does

1. Imports the v3 generator's mesh builders verbatim.
2. Constructs Frame / Screen / Jetson / Speaker / ReSpeaker dataclass
   instances, but with the v4-bumped Frame dimensions.
3. Calls the same builder functions with the new config.
4. Writes STLs into `stl-v4/`.
5. Generates the matching acrylic-side-panel DXF (recomputed from
   the new W/D).

Result: `stl-v4/` contains the four hand-to-print-shop files —
frame, back panel, LED diffuser, acrylic-side-panel DXF — that
work for any of the three hardware paths.

## Run

    cd jarvis/05-the-body/designs
    python3 generate_enclosure_v4.py

Output is deterministic — running it twice produces byte-identical
STLs. Safe to re-run after edits.
"""

from __future__ import annotations

import os

# Reuse v3's mesh builders + primitives + dataclass shapes. The
# generator was written to be parametric on Frame / Screen / etc.;
# we only override Frame here.
from generate_enclosure_v3 import (
    Frame, Screen, Jetson, ReSpeaker, Speaker,
    build_frame_meshes, build_back_panel_meshes,
    build_led_diffuser_meshes, write_acrylic_dxf,
    merge, to_stl_mesh,
)


# ── V4 Frame: buffer-padded for hardware uncertainty ────────────────


def make_v4_frame() -> Frame:
    """
    V4 Frame: same design language as v3, ~10mm more depth + lateral.
    Component-specific dimensions (LED bar size, screen overhang, side
    inset, belt zone, magnet pockets) stay identical — they're tuned
    to the screen + LCD bezel + acrylic-panel geometry, none of which
    change between paths.
    """
    return Frame(
        # ── External envelope (the buffer change) ────────────────
        W=200.0,          # was 190
        H=145.0,          # was 135
        D=70.0,           # was 60 — biggest improvement: rear cavity

        # ── Wall thicknesses (unchanged) ─────────────────────────
        front_t=4.0,
        top_t=3.0,
        bottom_t=3.0,
        back_t=2.5,
        side_rabbet_t=2.0,

        # ── LED bar (unchanged — still 12 LEDs) ──────────────────
        led_bar_y=4.0,
        led_bar_h=12.0,
        led_bar_w=175.0,

        # ── Screen cutout (unchanged — same screen) ──────────────
        screen_overhang=1.5,

        # ── Side opening insets ──────────────────────────────────
        # Slight increase top/bottom to keep the acrylic window
        # vertically centered now that H is taller. Front/back
        # inset stays the same — preserves rabbet rigidity.
        side_inset_top=14.0,        # was 12
        side_inset_bottom=18.0,     # was 16 (still hides speaker mount)
        side_inset_front=6.0,
        side_inset_back=6.0,

        # ── Belt zone (re-centered for new H) ────────────────────
        # Belt visually centered at H/2; band still 32mm tall.
        belt_y_center=72.5,         # was 67.5; centered to new H=145
        belt_height=32.0,
        belt_glow_led_pitch=16.7,

        # ── Magnet pockets (unchanged) ───────────────────────────
        magnet_d=6.0,
        magnet_t=3.0,
        magnet_clearance=0.2,
    )


# ── Generation ──────────────────────────────────────────────────────


def main():
    F = make_v4_frame()
    S = Screen()
    J = Jetson()
    SP = Speaker()
    R = ReSpeaker()

    out_dir = os.path.join(os.path.dirname(__file__), "stl-v4")
    os.makedirs(out_dir, exist_ok=True)

    print(f"\n{'═' * 70}")
    print(f"  JARVIS Enclosure v4 — buffer-padded for hardware flexibility")
    print(f"  Form factor: {F.W} × {F.H} × {F.D} mm  (W × H × D)")
    print(f"  v3 was:      190.0 × 135.0 × 60.0 mm")
    print(f"  Designed for: Waveshare 7\" LCD (fixed) + flexible internals")
    print(f"  Output to: {out_dir}")
    print(f"{'═' * 70}\n")

    # Frame
    print("→ Frame (main body, opaque PETG, ~14-16h FDM print)")
    fp = build_frame_meshes(F, S, J, SP, R)
    fv, ff = merge(*fp)
    fm = to_stl_mesh(fv, ff)
    fpath = os.path.join(out_dir, "jarvis-frame-v4.stl")
    fm.save(fpath)
    print(f"  ✓ {fpath}")
    print(f"    {len(ff)} triangles, {os.path.getsize(fpath) / 1024:.1f} KB")

    # Back panel
    print("\n→ Back panel (snap-fit, opaque PETG, ~3-4h print)")
    bp = build_back_panel_meshes(F, J)
    bv, bf_ = merge(*bp)
    bm = to_stl_mesh(bv, bf_)
    bpath = os.path.join(out_dir, "jarvis-back-panel-v4.stl")
    bm.save(bpath)
    print(f"  ✓ {bpath}")
    print(f"    {len(bf_)} triangles, {os.path.getsize(bpath) / 1024:.1f} KB")

    # LED diffuser
    print("\n→ LED bar diffuser (frosted/natural PLA, ~1h print)")
    lp = build_led_diffuser_meshes(F)
    lv, lf = merge(*lp)
    lm = to_stl_mesh(lv, lf)
    lpath = os.path.join(out_dir, "jarvis-led-diffuser-v4.stl")
    lm.save(lpath)
    print(f"  ✓ {lpath}")
    print(f"    {len(lf)} triangles, {os.path.getsize(lpath) / 1024:.1f} KB")

    # Acrylic side panel DXF
    print("\n→ Acrylic side panel DXF (laser-cut 3mm clear acrylic ×2)")
    dxf_path = os.path.join(out_dir, "jarvis-side-panel-v4.dxf")
    write_acrylic_dxf(dxf_path, F)
    print(f"  ✓ {dxf_path}")
    print(f"    {os.path.getsize(dxf_path)} bytes")

    print(f"\n{'═' * 70}")
    print(f"  ✓ All v4 files generated.")
    print(f"  Next: see PRINT_SHOP_BRIEF.md  (or ASSEMBLY_GUIDE_V4.md")
    print(f"        for assembly steps once printed).")
    print(f"{'═' * 70}\n")


if __name__ == "__main__":
    main()
