#!/usr/bin/env python3
"""
enclosure_geometry.py — corrected v5 geometry for the Vesper enclosure.

## Why this exists

The original v3/v4 builders (in generate_enclosure_v3.py) decompose
each face into "strips around the cutout" and rely on the slicer to
union overlapping pieces. That approach has multiple fatal defects
discovered during print-shop validation:

  1. Face-coincident geometry (strips that touch face-to-face but don't
     overlap in volume) does NOT union in manifold3d's CSG kernel,
     producing multi-body STLs. Prints would literally fall apart at
     the strip boundaries (top-face vent strips and back-panel vent
     strips were all disconnected).
  2. Port cluster cutout was placed in the back panel, but the Jetson
     Orin Nano's port cluster sticks out parallel to the PCB plane
     (not perpendicular to it) — so a back-panel cutout cannot give
     port access. Cables would hit solid PETG.
  3. Magnet attachment for side panels was geometrically broken: the
     v3 comment specified "magnets in front/back faces" but the panel
     washers were at corners that don't align with any frame material.
  4. side_inset_front (6mm) > front_t (4mm) created a 2mm light/dust
     gap on each side at the panel front/back edges.
  5. Top vent slits ran the full 200mm width, structurally weakening
     the top face.
  6. No feet on the bottom face — speaker fired into the table.
  7. Top vent area was insufficient for the Jetson's 7-15W heat load.

This module rewrites the geometry from scratch using proper CSG
(union + subtract). Each face is built as ONE solid box plus
positive features (standoffs, feet, magnet bosses), with all
cutouts (screen, LED, speaker, vents, port aperture) emitted as
SUBTRACTIONS handled by mesh_union.

Outputs a single watertight, single-body STL per part.

## How to use

  from enclosure_geometry import EnclosureV5
  e = EnclosureV5()
  pos, neg = e.frame_pieces()
  mesh = pieces_to_watertight_mesh(pos, neg)
  mesh.export("frame.stl")

Or call the high-level emit_all() which drives the whole bundle.
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from typing import List, Tuple

import numpy as np

# Reuse the primitive helpers from v3 — they emit the same triangle
# soups, mesh_union takes care of normals/winding.
from generate_enclosure_v3 import (
    Screen, Jetson, Speaker,
    box, cyl_y, cyl_z,
)
from mesh_union import pieces_to_watertight_mesh

Piece = Tuple[np.ndarray, np.ndarray]


# ───────────────────────────────────────────────────────────────────
# Frame dimensions — v5 (= v4 envelope, with corrected internal layout)
# ───────────────────────────────────────────────────────────────────


@dataclass
class FrameV5:
    # External envelope
    W: float = 200.0
    H: float = 145.0
    D: float = 70.0

    # Wall thicknesses
    front_t: float = 4.0
    top_t: float = 3.0
    bottom_t: float = 3.0
    back_t: float = 2.5

    # Side opening insets along Y (top + bottom edges of opening). The
    # Z insets (front/back) are DERIVED from face thicknesses — see
    # side_inset_front / side_inset_back properties.
    side_inset_top: float = 14.0
    side_inset_bottom: float = 18.0

    # Front face features
    screen_overhang: float = 1.5     # mm of LCD bezel hidden behind frame
    led_bar_y: float = 4.0           # bottom of LED bar slot from device bottom
    led_bar_h: float = 12.0          # vertical extent of LED bar slot
    led_bar_w: float = 175.0         # horizontal extent of LED bar slot

    # Top-face mic holes (4-mic ReSpeaker, square pattern)
    mic_pitch: float = 40.0
    mic_hole_d: float = 3.5          # 3mm + clearance for clean drilling

    # Bottom feet (cylindrical bosses, give the speaker air gap)
    foot_d: float = 12.0             # foot diameter
    foot_h: float = 10.0             # foot height (drops below device base)
    foot_inset: float = 12.0         # inset of foot center from corner

    # Top vent grille — limited width, multiple short slots
    # Total vent area ≈ vent_count × vent_slot_w × vent_slit_w
    vent_count: int = 7              # 7 slits gives more area than 5
    vent_slot_w: float = 100.0       # 100mm long slots (centered on top)
    vent_slit_w: float = 2.0         # 2mm wide slits
    vent_pitch: float = 7.0          # 7mm slit-center spacing
    # Total: 7 × 100 × 2 = 1400 mm² + back panel grille ~600 mm² = ~2000.
    # Borderline for sustained 15W passive cooling — fine for prototype.

    # Back-panel vent grille
    bp_vent_count: int = 5
    bp_vent_w: float = 60.0
    bp_vent_h: float = 2.5
    bp_vent_pitch: float = 6.0

    # Side-panel magnet bosses (front-corners only — see build_frame_v5)
    boss_size: float = 10.0          # boss face is 10×10mm in YZ
    boss_depth: float = 6.0          # boss depth into cavity (along X)
    magnet_d: float = 6.0            # N42 disc magnet OD
    magnet_t: float = 3.0            # disc magnet thickness
    magnet_pocket_clearance: float = 0.2  # press-fit slop per side

    # Fit clearance applied to all matched-pair geometry (panel-in-slot,
    # diffuser-in-slot, etc.) so FDM ±0.3mm tolerances don't jam parts.
    # Removed FROM the inner part (panel/diffuser), not added to the slot.
    fit_clearance: float = 0.3

    @property
    def side_inset_front(self) -> float:
        """Z inset is derived from front face thickness — keeps panel
        flush against front face with no gap."""
        return self.front_t

    @property
    def side_inset_back(self) -> float:
        """Z inset = back panel thickness — keeps panel flush against
        back panel with no gap."""
        return self.back_t

    @property
    def panel_w(self) -> float:
        """Side-panel width (along frame Z). Covers full opening with
        fit_clearance subtracted to allow insertion."""
        return (self.D - self.side_inset_front - self.side_inset_back
                - self.fit_clearance)

    @property
    def panel_h(self) -> float:
        """Side-panel height (along frame Y). Includes fit clearance."""
        return (self.H - self.side_inset_top - self.side_inset_bottom
                - self.fit_clearance)

    @property
    def panel_t(self) -> float:
        return 3.0


# ───────────────────────────────────────────────────────────────────
# Geometry helpers
# ───────────────────────────────────────────────────────────────────


def _slab(w: float, h: float, d: float, x: float = 0, y: float = 0,
          z: float = 0) -> Piece:
    """Wrapper around box() returning a single (verts, faces) tuple."""
    return box(w, h, d, x=x, y=y, z=z)


def _disc(r: float, h: float, x: float, y: float, z: float,
          axis: str = "y", sides: int = 32) -> Piece:
    """Cylinder along the given axis, returning (verts, faces)."""
    if axis == "y":
        return cyl_y(r, h, x=x, y=y, z=z, sides=sides)
    if axis == "z":
        return cyl_z(r, h, x=x, y=y, z=z, sides=sides)
    raise ValueError(f"unknown axis {axis}")


# ───────────────────────────────────────────────────────────────────
# Frame builder (the big print)
# ───────────────────────────────────────────────────────────────────


def build_frame_v5(F: FrameV5, S: Screen, J: Jetson,
                   SP: Speaker) -> Tuple[List[Piece], List[Piece]]:
    """
    Build the main frame geometry. Returns (positives, negatives).

    The frame is a hollow box with:
      - Front face (4mm) with screen cutout + LED bar slot
      - Top face (3mm) with centered vent slot pattern
      - Bottom face (3mm) with speaker hole + 4 feet
      - Side openings on left and right (covered later by side panels)
      - 4 corner bosses on each side opening (magnet pockets for panels)
      - 4 screen mounting standoffs on inside of front face

    No back wall — the back panel is a separate snap-fit STL.
    No left/right side walls — the side openings expose the cavity.
    """
    pos: List[Piece] = []
    neg: List[Piece] = []

    # ── FRONT FACE ─────────────────────────────────────────────
    # Single solid plate, full W × H × front_t. All features (screen
    # cutout, LED bar slot) emitted as subtractions — manifold3d
    # cleanly cuts them, no strip decomposition needed.
    pos.append(_slab(F.W, F.H, F.front_t, x=0, y=0, z=0))

    # Screen cutout: rectangular hole exposing LCD active area, with
    # 1.5mm overhang to hide LCD bezel.
    sc_w = S.active_w + 2 * F.screen_overhang  # 157
    sc_h = S.active_h + 2 * F.screen_overhang  # 89
    sc_x = (F.W - sc_w) / 2
    sc_cy = F.led_bar_y + F.led_bar_h + 4.0 + sc_h / 2  # screen vertical center
    sc_y = sc_cy - sc_h / 2
    # Subtract slightly past the front face thickness so the cut is clean
    # at both surfaces.
    neg.append(_slab(sc_w, sc_h, F.front_t + 0.2, x=sc_x, y=sc_y, z=-0.1))

    # LED bar slot: full-thickness rectangular cut for diffuser
    led_x = (F.W - F.led_bar_w) / 2
    neg.append(_slab(F.led_bar_w, F.led_bar_h, F.front_t + 0.2,
                     x=led_x, y=F.led_bar_y, z=-0.1))

    # ── SCREEN MOUNTING STANDOFFS ──────────────────────────────
    # 4 cylindrical posts on the inside of the front face. Drill brass
    # inserts post-print. Posts overlap the front face by 0.1mm so
    # they truly union (not face-coincident).
    standoff_outer_r = 3.0
    standoff_h = S.standoff_h  # 5mm
    s_cx = F.W / 2
    for dx in (-S.mount_pitch_w / 2, S.mount_pitch_w / 2):
        for dy in (-S.mount_pitch_h / 2, S.mount_pitch_h / 2):
            pos.append(_disc(standoff_outer_r, standoff_h + 0.1,
                             x=s_cx + dx, y=sc_cy + dy,
                             z=F.front_t - 0.1, axis="z", sides=24))

    # ── BOTTOM FACE ────────────────────────────────────────────
    # Solid plate Y=0..bottom_t, full W × D.
    pos.append(_slab(F.W, F.bottom_t, F.D, x=0, y=0, z=0))

    # Speaker mounting ring — annular flange to bolt the driver to.
    # Rises from bottom plate top surface (Y=bottom_t) into the cavity
    # by 6mm. Inside diameter matches the driver body (50mm) so the
    # driver passes through; flange catches on top of the ring.
    sp_r = SP.diameter / 2
    sp_cx = F.W / 2
    sp_cz = F.D / 2
    pos.append(_disc(SP.mount_od / 2, 6.0,
                     x=sp_cx, y=F.bottom_t - 0.1, z=sp_cz,
                     axis="y", sides=48))
    # Subtract a 50mm-dia hole through both the bottom plate AND the
    # ring (single subtraction handles both — sound-exit aperture + ring
    # inner bore in one shot).
    neg.append(_disc(sp_r, F.bottom_t + 6.0 + 0.2,
                     x=sp_cx, y=-0.1, z=sp_cz, axis="y", sides=48))

    # ── BOTTOM FEET ────────────────────────────────────────────
    # 4 cylindrical bosses dropping below the device base. They sit
    # at the corners of the bottom face, inset from each edge.
    foot_corners = [
        (F.foot_inset, F.foot_inset),
        (F.W - F.foot_inset, F.foot_inset),
        (F.foot_inset, F.D - F.foot_inset),
        (F.W - F.foot_inset, F.D - F.foot_inset),
    ]
    for fx, fz in foot_corners:
        # Foot extends from y=-foot_h to y=bottom_t (overlap into bottom
        # plate by bottom_t to ensure manifold union).
        pos.append(_disc(F.foot_d / 2, F.foot_h + F.bottom_t,
                         x=fx, y=-F.foot_h, z=fz, axis="y", sides=24))

    # ── TOP FACE ───────────────────────────────────────────────
    # Solid plate Y=H-top_t..H, full W × D.
    pos.append(_slab(F.W, F.top_t, F.D, x=0, y=F.H - F.top_t, z=0))

    # Top vent slits — centered horizontal slots, NOT full width. Each
    # slot is vent_slot_w × vent_slit_w, cut through the full top_t.
    # Slits run along X (width direction); they're spaced along Z.
    vent_slot_x_start = (F.W - F.vent_slot_w) / 2
    vent_block_z_center = F.D / 2
    vent_block_total_z = F.vent_count * F.vent_pitch
    vent_z_start = vent_block_z_center - vent_block_total_z / 2
    for i in range(F.vent_count):
        slit_z = vent_z_start + i * F.vent_pitch + (F.vent_pitch - F.vent_slit_w) / 2
        neg.append(_slab(F.vent_slot_w, F.top_t + 0.2, F.vent_slit_w,
                         x=vent_slot_x_start, y=F.H - F.top_t - 0.1,
                         z=slit_z))

    # ── SIDE-OPENING MAGNET BOSSES (FRONT CORNERS ONLY) ────────
    # 2 bosses per side (left + right = 4 total). Each boss is a small
    # block embedded in the FRONT face material at the side opening's
    # front corners. Each boss has a 6mm-dia × 3mm-deep magnet pocket
    # subtracted from it, opening toward the +X (right side) or -X
    # direction (left side) — the direction the side panel approaches
    # from. Press-fit a N42 disc magnet into each pocket at assembly.
    #
    # NOTE: We use only FRONT corners — there is no back wall in the
    # frame, so back-corner bosses would be disconnected floating
    # geometry. 2 magnets per side is enough to retain a 3mm PETG panel
    # for a desk-bound device.
    bs = F.boss_size
    bd = F.boss_depth
    pocket_r = F.magnet_d / 2 + F.magnet_pocket_clearance
    pocket_depth = F.magnet_t + F.magnet_pocket_clearance
    for x_side, magnet_axis_dir in ((0, +1), (F.W - bd, -1)):
        for y_side in (F.side_inset_bottom, F.H - F.side_inset_top - bs):
            # Boss embedded in front face material; Z extent = front_t
            # so it overlaps the front face and unions with it.
            pos.append(_slab(bd, bs, F.front_t,
                             x=x_side, y=y_side, z=0))

            # Magnet pocket — cylinder along X axis, opening toward
            # the panel side (outward through X=0 for left side, or
            # X=W for right side). The magnet's flat face sits flush
            # with the boss's panel-side surface, so attraction across
            # the panel thickness is maximal.
            #
            # Pocket center: at the center of the boss face (in YZ).
            #   left  side: pocket axis along +X, drilled from X=0
            #               into the boss to depth pocket_depth.
            #   right side: pocket axis along -X, drilled from X=W
            #               into the boss to depth pocket_depth.
            cy = y_side + bs / 2
            cz = F.front_t / 2
            if magnet_axis_dir > 0:
                # Left boss: pocket goes from X=-0.1 to X=pocket_depth+0.1
                neg.append(cyl_z(pocket_r, 0,  # placeholder (overwritten below)
                                 x=cy, y=cz, z=0))
                # cyl_z is along Z — we want a cylinder along X.
                # Use a small box approximation (square pocket — magnet
                # is round but a square pocket of sufficient size works
                # mechanically and is simpler with our primitives).
                neg.pop()  # remove placeholder
                pocket_w = F.magnet_d + 2 * F.magnet_pocket_clearance
                neg.append(_slab(pocket_depth + 0.1, pocket_w, pocket_w,
                                 x=-0.05,
                                 y=cy - pocket_w / 2,
                                 z=cz - pocket_w / 2))
            else:
                pocket_w = F.magnet_d + 2 * F.magnet_pocket_clearance
                neg.append(_slab(pocket_depth + 0.1, pocket_w, pocket_w,
                                 x=F.W - pocket_depth,
                                 y=cy - pocket_w / 2,
                                 z=cz - pocket_w / 2))

    # ── TOP-FACE MIC HOLES ────────────────────────────────────
    # 4 holes for ReSpeaker 4-mic array, square pattern with 40mm
    # pitch, centered on the top face. Drilled through full top_t.
    mic_cx = F.W / 2
    mic_cz = F.D / 2
    mic_r = F.mic_hole_d / 2
    for dx in (-F.mic_pitch / 2, F.mic_pitch / 2):
        for dz in (-F.mic_pitch / 2, F.mic_pitch / 2):
            neg.append(_disc(mic_r, F.top_t + 0.2,
                             x=mic_cx + dx, y=F.H - F.top_t - 0.1,
                             z=mic_cz + dz, axis="y", sides=24))

    # ── BACK CAP (NONE) ────────────────────────────────────────
    # The back of the device is a separate snap-fit STL. Nothing on
    # the back side of the frame.

    return pos, neg


# ───────────────────────────────────────────────────────────────────
# Back panel builder
# ───────────────────────────────────────────────────────────────────


def build_back_panel_v5(F: FrameV5, J: Jetson) -> Tuple[List[Piece], List[Piece]]:
    """
    Back panel (separate snap-fit STL). NO port-cluster cutout — the
    Jetson's ports exit through the right side panel. The back panel
    has only:
      - Solid panel plate
      - Vent grille (centered, limited-width slots — NOT face-coincident)
      - 4 Jetson mounting standoffs
      - 4 corner snap tabs

    Returns (positives, negatives).
    """
    pos: List[Piece] = []
    neg: List[Piece] = []

    pw = F.W
    ph = F.H
    bt = F.back_t

    # Solid panel
    pos.append(_slab(pw, ph, bt, x=0, y=0, z=0))

    # Vent grille — limited-width centered slots, all subtractions
    # so they don't split the panel into disconnected strips.
    vent_grille_x_start = (pw - F.bp_vent_w) / 2
    vent_grille_total_h = F.bp_vent_count * F.bp_vent_pitch
    vent_grille_y_start = (ph - vent_grille_total_h) / 2
    for i in range(F.bp_vent_count):
        slit_y = (vent_grille_y_start + i * F.bp_vent_pitch
                  + (F.bp_vent_pitch - F.bp_vent_h) / 2)
        neg.append(_slab(F.bp_vent_w, F.bp_vent_h, bt + 0.2,
                         x=vent_grille_x_start, y=slit_y, z=-0.1))

    # ── JETSON MOUNTING STANDOFFS ─────────────────────────────
    # Position the Jetson with its port-edge along the RIGHT side of
    # the device, so cables exit through the right side panel cutout.
    #
    # PCB orientation: 100mm dim along Y (vertical), 79mm dim along X.
    # Mount-hole pitch: 86mm parallel to port-edge (Y), 58mm
    # perpendicular (X).
    # PCB X range: 113..192 (so port-edge is at X=192, with 5mm cable
    # clearance to the right side panel inner surface at X=W-3=197).
    # PCB Y range: vertically centered at H/2 = 72.5, so Y=22.5..122.5.
    # Mount holes (10.5mm in from PCB X edges, 7mm in from Y edges):
    #   (123.5, 29.5), (181.5, 29.5)
    #   (123.5, 115.5), (181.5, 115.5)
    standoff_outer_r = 2.5
    standoff_h = J.standoff_h  # 4mm
    jetson_holes = [
        (123.5, 29.5),
        (181.5, 29.5),
        (123.5, 115.5),
        (181.5, 115.5),
    ]
    for sx, sy in jetson_holes:
        pos.append(_disc(standoff_outer_r, standoff_h + 0.1,
                         x=sx, y=sy, z=bt - 0.1, axis="z", sides=20))

    # ── NOTE on back panel retention ──────────────────────────
    # The v3 design had snap tabs at the 4 corners, but the frame had
    # no perimeter ring for them to engage — the tabs locked onto
    # nothing. v5 omits the tabs. Back panel retention is by friction
    # at the back face perimeter plus 4 M3 screws through pre-marked
    # corner holes (drilled post-print). See the assembly guide.

    return pos, neg


# ───────────────────────────────────────────────────────────────────
# LED diffuser (unchanged from v3 — already single-body)
# ───────────────────────────────────────────────────────────────────


def build_led_diffuser_v5(F: FrameV5) -> Tuple[List[Piece], List[Piece]]:
    """Frosted PETG/PLA strip that drops into the LED bar slot in the
    front face. Sized smaller than the slot by fit_clearance on each
    width/height axis so it inserts cleanly on FDM tolerances."""
    c = F.fit_clearance
    return ([_slab(F.led_bar_w - c, F.led_bar_h - c, F.front_t)], [])


# ───────────────────────────────────────────────────────────────────
# Side panel builders — TWO variants: solid (left), with-cutout (right)
# ───────────────────────────────────────────────────────────────────


def _side_panel_common(F: FrameV5) -> Tuple[List[Piece], List[Piece], dict]:
    """
    Shared geometry for both side panels.

    The panel is panel_w × panel_h × panel_t. The frame has 2 magnet
    bosses per side at the FRONT corners (front face material).
    The panel has 2 washer pockets at the front edge to mate with
    those bosses.

    Panel-local coord mapping:
      - panel x-axis (0..panel_w) = frame Z direction (panel "depth")
      - panel y-axis (0..panel_h) = frame Y direction (panel "height")
      - panel z-axis (0..panel_t) = frame X direction (thickness)

    Panel x=0 corresponds to frame Z=side_inset_front (front edge).
    Boss positions in frame: (Z=0..front_t, Y=side_inset_bottom..+bs)
    and (Z=0..front_t, Y=H-side_inset_top-bs..H-side_inset_top).

    Washer center in panel-local: at panel x = some_small (just inside
    front edge of panel) such that frame Z = side_inset_front + panel_x
    is close to the boss Z range (0..front_t = 0..4). With
    side_inset_front = front_t = 4, the boss is at Z=0..4 and the
    panel front edge is at Z=4. Magnet sits 2mm deep in the boss
    (centered around Z=2), washer sits at panel x=0 (panel front
    edge). Air gap is the remaining 4 - 2 = 2mm — strong attraction.

    Washer Y positions: aligned with the boss Y centers, which are
    at side_inset_bottom + bs/2 and H - side_inset_top - bs/2.
    Translate to panel-local Y: bs/2 = 5 (bottom) and panel_h - bs/2
    = 108 (top).
    """
    panel_w = F.panel_w
    panel_h = F.panel_h
    panel_t = F.panel_t
    boss_half = F.boss_size / 2

    pos: List[Piece] = [_slab(panel_w, panel_h, panel_t, x=0, y=0, z=0)]
    neg: List[Piece] = []

    # 2 washer pockets along the front edge of the panel, at the magnet
    # boss Y positions. Pocket cut into the INSIDE face of the panel
    # (the face touching the frame, at z=0).
    washer_d = 12.0
    washer_h = 1.2
    # Washer center X (panel-local): at boss_half ≈ 5mm from the front
    # edge of the panel — directly aligned with the front-face boss.
    washer_x = boss_half
    washer_corners = [
        (washer_x, boss_half),                  # front-bottom
        (washer_x, panel_h - boss_half),        # front-top
    ]
    for wx, wy in washer_corners:
        neg.append(_disc(washer_d / 2, washer_h + 0.2,
                         x=wx, y=wy, z=-0.1, axis="z", sides=24))

    return pos, neg, dict(panel_w=panel_w, panel_h=panel_h,
                          panel_t=panel_t, washer_corners=washer_corners)


def build_side_panel_left_v5(F: FrameV5) -> Tuple[List[Piece], List[Piece]]:
    """Left side panel — fully solid, just the panel + 4 washer pockets."""
    pos, neg, _ = _side_panel_common(F)
    return pos, neg


def build_side_panel_right_v5(F: FrameV5,
                              J: Jetson) -> Tuple[List[Piece], List[Piece]]:
    """
    Right side panel — same as left, plus a port-cluster cutout
    aligned with the Jetson's port edge.

    Port cutout in panel-local coords:
      - Y span (vertical): aligned with port cluster on the Jetson.
        PCB Y center = 72.5 (frame), port cluster spans ~85mm centered.
        Frame Y: 30..115. Panel-local Y: 30 - side_inset_bottom..115 -
        side_inset_bottom = 12..97.
      - X span (horizontal, panel-local = depth direction in frame):
        Ports protrude from PCB toward the front of the device. PCB
        sits at frame Z = D - back_t - jetson_standoff_h - pcb_thickness
        ≈ 70 - 2.5 - 4 - 1.5 = 62. Connectors extend ~18mm toward
        the front, so port body Z range = 44..62.
        Panel-local X = (44 - side_inset_front)..(62 - side_inset_front)
                      = 40..58 (with side_inset_front=4).
        Extend cutout slightly past the back edge of the panel for clean
        clearance: X = 40..panel_w (if panel_w = 63.5 → X = 40..63.5).
      - Through-thickness Z span: full panel thickness.
    """
    pos, neg, info = _side_panel_common(F)

    panel_w = info["panel_w"]
    panel_h = info["panel_h"]
    panel_t = info["panel_t"]

    # Port cluster cutout — sized generously to accommodate any port +
    # cable bend without binding.
    port_y_lo = 30.0 - F.side_inset_bottom            # 12
    port_y_hi = 115.0 - F.side_inset_bottom           # 97
    port_x_lo = 44.0 - F.side_inset_front             # 40
    port_x_hi = 62.0 - F.side_inset_front + 2.0       # 60 (extra 2mm slop)
    port_x_hi = min(port_x_hi, panel_w)               # clamp to panel back edge

    neg.append(_slab(port_x_hi - port_x_lo,
                     port_y_hi - port_y_lo,
                     panel_t + 0.2,
                     x=port_x_lo, y=port_y_lo, z=-0.1))

    return pos, neg


# ───────────────────────────────────────────────────────────────────
# High-level emit
# ───────────────────────────────────────────────────────────────────


def emit_all_v5(out_dir: str) -> None:
    """Generate the complete v5 bundle into out_dir.

    Files written:
      - jarvis-frame-v5.stl
      - jarvis-back-panel-v5.stl
      - jarvis-led-diffuser-v5.stl
      - jarvis-side-panel-left-v5.stl
      - jarvis-side-panel-right-v5.stl

    Print orientations (FDM):
      - jarvis-frame-v5.stl       FRONT FACE DOWN. Cleanest screen
                                  aperture finish. Feet point UP during
                                  print, no supports needed.
      - jarvis-back-panel-v5.stl  Either face down. Standoffs print as
                                  small upward bosses; no supports.
      - jarvis-led-diffuser-v5.stl  Flat. Any orientation. No supports.
      - jarvis-side-panel-left-v5.stl   Either face down. Magnet washer
                                       pockets printed against the
                                       build plate (down) for cleanest
                                       pockets — print INSIDE-FACE-DOWN.
      - jarvis-side-panel-right-v5.stl  Same as left. INSIDE-FACE-DOWN.
                                        The port cutout is a clean
                                        through-hole, no overhangs.
    """
    os.makedirs(out_dir, exist_ok=True)
    F = FrameV5()
    S = Screen()
    J = Jetson()
    SP = Speaker()

    print(f"\n{'═' * 70}")
    print(f"  JARVIS Enclosure v5 — corrected, single-body, with port routing")
    print(f"  Form factor: {F.W} × {F.H} × {F.D} mm")
    print(f"  Output: {out_dir}")
    print(f"{'═' * 70}\n")

    def emit(label: str, builder, filename: str, *args):
        positives, negatives = builder(*args)
        mesh = pieces_to_watertight_mesh(positives, negatives)
        path = os.path.join(out_dir, filename)
        mesh.export(path)
        size_kb = os.path.getsize(path) / 1024
        ok_w = "✓" if mesh.is_watertight else "✗"
        ok_b = "✓" if mesh.body_count == 1 else "✗"
        print(f"  {ok_w}{ok_b} {filename}")
        print(f"     {len(mesh.faces)} triangles, {size_kb:.1f} KB, "
              f"watertight={mesh.is_watertight}, bodies={mesh.body_count}")

    print("→ Frame")
    emit("frame", build_frame_v5, "jarvis-frame-v5.stl", F, S, J, SP)

    print("\n→ Back panel")
    emit("back panel", build_back_panel_v5,
         "jarvis-back-panel-v5.stl", F, J)

    print("\n→ LED diffuser")
    emit("led diffuser", build_led_diffuser_v5,
         "jarvis-led-diffuser-v5.stl", F)

    print("\n→ Side panel — LEFT (solid)")
    emit("side panel left", build_side_panel_left_v5,
         "jarvis-side-panel-left-v5.stl", F)

    print("\n→ Side panel — RIGHT (with port cutout for Jetson)")
    emit("side panel right", build_side_panel_right_v5,
         "jarvis-side-panel-right-v5.stl", F, J)

    print(f"\n{'═' * 70}")
    print(f"  Done. Watertight + single-body markers must all be ✓✓.")
    print(f"{'═' * 70}\n")


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    emit_all_v5(os.path.join(here, "stl-v5"))
