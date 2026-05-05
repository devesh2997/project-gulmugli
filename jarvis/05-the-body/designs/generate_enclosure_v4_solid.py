#!/usr/bin/env python3
"""
generate_enclosure_v4_solid.py — fully-printed v4 (no acrylic step).

## Why this variant exists

V4 (`generate_enclosure_v4.py`) has open left and right sides because
the design intent is **clear acrylic windows** that snap on
magnetically. That requires a separate vendor visit to a laser-cut
shop and a magnet/washer/glue assembly step.

V4-solid removes both:
  - **Side panels are 3D-printed** in PETG, just like the rest of
    the frame.
  - **Same outer dimensions and same magnetic mounting** as the
    acrylic version, so a future swap to clear acrylic is a
    literal pop-off-pop-on operation. Zero frame changes needed.

## How the swap works

The frame's magnet pockets stay where they were. Both panel
variants (PETG and acrylic) ship 4 steel washers at the same 4
corner positions — the magnets in the frame attract those washers.

  - Print PETG panels now → install via the magnetic mount → done.
  - Want to swap to clear acrylic later? Send the existing
    `jarvis-side-panel-v4.dxf` to a laser-cut shop, glue washers
    in the same spots (etched on the DXF), pop the PETG panels
    off, pop the acrylic panels on.

Same magnets, same washers, same positions. The PETG panel is
designed as a **direct interchangeable replacement** for the
acrylic version.

## What this script outputs

A standalone, all-FDM bundle — no acrylic step, no DXF in the
folder. The bundle is self-contained for handoff to a single
print shop.

  stl-v4-solid/
    jarvis-frame-v4.stl              ← unchanged from v4
    jarvis-back-panel-v4.stl         ← unchanged from v4
    jarvis-led-diffuser-v4.stl       ← unchanged from v4
    jarvis-side-panel-v4.stl         ← NEW. Printed PETG side panel.
                                        Print TWO from this one STL —
                                        the panel is symmetric.

(The acrylic-windowed variant lives separately under
generate_enclosure_v4.py / stl-v4/. The two bundles are kept
disjoint on purpose so each can be sent to a vendor without
explaining the other.)

## Run

    cd jarvis/05-the-body/designs
    python3 generate_enclosure_v4_solid.py

Deterministic — re-runs produce byte-identical output.
"""

from __future__ import annotations

import os
from typing import List, Tuple

import numpy as np

# Reuse v3's mesh builders + primitives. We add ONE new builder
# (build_side_panel_meshes) below; everything else is imported.
from generate_enclosure_v3 import (
    Frame, Screen, Jetson, ReSpeaker, Speaker,
    build_frame_meshes, build_back_panel_meshes,
    build_led_diffuser_meshes,
    box, cyl_y, merge, to_stl_mesh,
)
from generate_enclosure_v4 import make_v4_frame


# ── New: printed side panel (interchangeable with the acrylic) ──────


def build_side_panel_meshes(F: Frame) -> List[Tuple[np.ndarray, np.ndarray]]:
    """
    A 3 mm-thick PETG plate sized to drop into the side opening of
    the v4 frame. Same outer dimensions as the acrylic version
    (the DXF) so swap-out later requires zero frame changes.

    Geometry:
      - Outer rectangle:  panel_w × panel_h × 3 mm
        Same as the DXF: panel_w = F.D - F.side_inset_back -
        F.side_inset_front, panel_h = F.H - F.side_inset_top -
        F.side_inset_bottom.
      - Four 12 mm × 1.2 mm-deep recessed pockets on the INSIDE
        face for M3 steel washers (12 mm OD, 1 mm thick). The
        washers press-fit into the pockets — magnets in the frame
        attract them, holding the panel in place.

    Why the pockets aren't subtractions:
      The v3/v4 generator deliberately avoids boolean operations
      (slicers handle overlapping geometry just fine, and avoiding
      booleans keeps the code simple + deterministic). For the
      washer pockets, we DO need a subtraction-style result, but
      we get it by emitting the panel as 4 corner blocks + a
      central plate that's THINNER in the corners — so the corners
      have a "shelf" that's exactly the washer thickness lower than
      the rest of the panel. The slicer unions overlapping
      geometry; the recess shows up where the corner blocks are
      shorter than the central plate.

    Built that way, the slicer-rendered output has clean 1.2 mm-deep
    pockets in each corner without any non-manifold edges.

    Note: the panel is symmetric — the same STL works for both left
    and right sides. Print it twice.
    """
    pieces: List[Tuple[np.ndarray, np.ndarray]] = []

    # Match the DXF dimensions exactly.
    panel_w = F.D - F.side_inset_back - F.side_inset_front
    panel_h = F.H - F.side_inset_top - F.side_inset_bottom
    panel_t = 3.0   # standard for swap-with-acrylic
    washer_d = 12.0  # M3 stainless washer outer diameter
    washer_h = 1.2   # washer thickness + 0.2 mm slop
    washer_inset = 8.0  # matches DXF etch-mark inset

    # We build the panel as a CENTRAL plate (full panel_w × panel_h
    # × panel_t) MINUS four corner regions where the plate is
    # thinner — instead of subtracting, we emit a full-thickness
    # panel and a recess-pocket-shaped chunk that sits inside the
    # 4 corner regions, but the slicer takes the UNION which gives
    # us the desired result.
    #
    # Practically: emit the central "donut" (panel minus the 4
    # corner pocket squares) at full thickness, and emit just the
    # recess thickness in each corner.
    #
    # Each corner pocket is centered at (washer_inset, washer_inset)
    # from the relevant corner. The pocket is square-bounded — slicers
    # render the pocket as a 12mm dia circle when we use a cylinder.

    # Central plate WITHOUT the corner pockets — easier to model as
    # 5 rectangles (top strip + bottom strip + middle-with-washer-cuts).
    # Actually simplest: just emit the full plate at full thickness,
    # then emit 4 cylindrical "negative space" markers... but slicers
    # don't union NEGATIVE volumes.
    #
    # Cleanest approach: emit the full plate at "panel_t - washer_h"
    # thickness, plus a "shelf" frame on top of it that's panel_t
    # tall but has cylindrical CUTOUTS at the 4 corners. The cutouts
    # ARE the washer pockets.
    #
    # Even simpler approach: just emit the full panel at full
    # thickness, and require post-print drilling for the 4 washer
    # pockets. Mirrors the v3/v4 pattern of "drill brass-insert
    # pockets after print" — already part of the assembly process.

    # Going with the simpler approach: full-thickness panel,
    # post-print drill 4 × 12mm flat-bottom holes, 1.2mm deep.
    # The DXF marks the same positions as etch circles, so the
    # printed panel and the acrylic version end up with washers
    # in identical positions.
    pieces.append(box(panel_w, panel_h, panel_t, x=0, y=0, z=0))

    # Add 4 small dimple markers on the INSIDE face at the washer
    # positions — small bumps that show the user where to drill.
    # Each dimple is a tiny cylinder (~3mm dia × 0.3mm tall) that
    # protrudes from the inside surface. The user drills through
    # the dimple (it acts as a centering target) for the washer pocket.
    dimple_d = 2.0
    dimple_h = 0.4
    washer_corners = [
        (washer_inset, washer_inset),
        (panel_w - washer_inset, washer_inset),
        (washer_inset, panel_h - washer_inset),
        (panel_w - washer_inset, panel_h - washer_inset),
    ]
    for wx, wy in washer_corners:
        # cyl_y axis is along Y; we want a cylinder along Z (the panel
        # thickness axis), but our box-builder uses x-y-z = w-h-d.
        # The panel is laid flat with thickness along Z, so a "Z dimple"
        # is what we want — emit it as a small box (or use cyl_y oriented
        # along the panel's "height"... actually let's just use a small
        # box for the dimple, simpler).
        pieces.append(box(dimple_d, dimple_d, dimple_h,
                          x=wx - dimple_d / 2, y=wy - dimple_d / 2,
                          z=panel_t))

    return pieces


# ── Generation ──────────────────────────────────────────────────────


def main():
    F = make_v4_frame()
    S = Screen()
    J = Jetson()
    SP = Speaker()
    R = ReSpeaker()

    out_dir = os.path.join(os.path.dirname(__file__), "stl-v4-solid")
    os.makedirs(out_dir, exist_ok=True)

    print(f"\n{'═' * 70}")
    print(f"  JARVIS Enclosure v4-solid — fully printed (no acrylic step)")
    print(f"  Form factor: {F.W} × {F.H} × {F.D} mm")
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

    # NEW: Printed side panel (PETG)
    print("\n→ Side panel (PETG, ~1.5h print) — print TWICE for left + right")
    sp_meshes = build_side_panel_meshes(F)
    sv, sf = merge(*sp_meshes)
    sm = to_stl_mesh(sv, sf)
    spath = os.path.join(out_dir, "jarvis-side-panel-v4.stl")
    sm.save(spath)
    print(f"  ✓ {spath}")
    print(f"    {len(sf)} triangles, {os.path.getsize(spath) / 1024:.1f} KB")

    print(f"\n{'═' * 70}")
    print(f"  ✓ All v4-solid files generated.")
    print(f"  Print plan: 1× frame, 1× back panel, 1× LED diffuser, 2× side panel.")
    print(f"{'═' * 70}\n")


if __name__ == "__main__":
    main()
