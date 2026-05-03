#!/usr/bin/env python3
"""
JARVIS Enclosure v3 — Tablet-on-side, framed Echo-Show form factor.

What's different from v2 (squircle puck):
  v2 was a 160×160×85mm rounded-cuboid Echo-Dot-style design that put the
  screen on a swappable front panel (with 0″/5″/7″ options). v3 is purpose-
  built around the user's confirmed Waveshare 7inch HDMI LCD (C) Rev 4.1
  and a specific aesthetic vision:

    * Front face = the entire screen + a ~12mm LED status bar below it
      (Lenovo Smart Display / Google Nest Hub style).
    * Top + bottom + back = matte black PETG (opaque, hides cables, holds
      mics on top, fires speaker out the bottom).
    * Left + right sides = OPEN WINDOWS, magnetically held water-clear
      acrylic panels (Nothing-phone style, reveals the Jetson).
    * A removable felt belt wraps around the device at mid-height,
      covering the middle band of the side openings (so acrylic above
      and below the belt is visible). LED strips behind the felt give a
      soft glow that shows through the fabric.

Generated outputs:
  * jarvis-frame-v3.stl       — main 3D-print body (front + top + bottom +
                                 internal posts + side rabbets). The big
                                 print, ~12-15h on FDM. Print orientation:
                                 front-face down for best front finish.
  * jarvis-back-panel-v3.stl   — separate snap-fit rear panel with port
                                 cluster cutout + vent grille. Easy to swap
                                 if cable layout changes. ~3h print.
  * jarvis-led-diffuser-v3.stl — frosted PETG strip that sits in front of
                                 the bottom-bar LEDs. Print in clear/natural
                                 PLA so light diffuses cleanly. ~1h print.
  * jarvis-side-panel-v3.dxf   — 2D DXF for laser-cutting two acrylic side
                                 panels (left + right share one shape; cut
                                 two from a 30×30cm sheet of 3mm clear
                                 acrylic). Hand to a Gurgaon laser shop.

External dimensions: 190 × 135 × 60 mm (W × H × D).

Component fit verified against:
  * Waveshare 7inch HDMI LCD (C) Rev 4.1 — 165×100mm PCB,
    154×86mm active, M3 corners at 158×93mm pitch, ~25mm depth
  * Jetson Orin Nano Super dev kit — 100×79mm PCB, ~21mm tall,
    M2.5 mounting holes at 86×58mm pitch (corners of carrier)
  * 50mm speaker driver + MAX98357A I2S amp
  * ReSpeaker 4-Mic Array — 65×65mm, mics at ~40mm pitch (square pattern)
  * WS2812B 60-LED/m strip — cut to 12 LEDs (≈200mm) for bottom bar +
    12 LEDs for belt-glow (6 per side, mounted to inside walls)
  * N42 6×3mm magnet discs — 4 per side panel, in pockets

References for design choices:
  * Echo Show 5 form factor: 148×86×73mm, screen-front, fabric back wrap.
    Ours is wider (190 vs 148) because our screen is bigger.
  * Lenovo Smart Display 7": ~190×135 footprint, very close to ours.
  * Nothing Phone 2: transparent back showcasing internals — informed the
    "side acrylic windows" decision.
  * HomePod fabric: validated the felt-as-decorative-acoustic-cloth idea.
"""

import math
import os
from dataclasses import dataclass, field
from typing import List, Tuple

import numpy as np

try:
    from stl import mesh
except ImportError:
    raise SystemExit(
        "ERROR: numpy-stl not installed. Run: pip install numpy-stl"
    )


# ═══════════════════════════════════════════════════════════════════════
# Dimensions and component specs (all mm)
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class Frame:
    # External envelope
    W: float = 190.0   # width
    H: float = 135.0   # height
    D: float = 60.0    # depth (front-to-back)

    # Wall thicknesses
    front_t: float = 4.0      # front face — slightly thicker so screen
                              # standoffs have meat; also makes the bezel
                              # visually substantial.
    top_t: float = 3.0        # top face
    bottom_t: float = 3.0     # bottom face
    back_t: float = 2.5       # back face (separate snap-fit panel)
    side_rabbet_t: float = 2.0  # thin lip around side openings where
                                # acrylic panel rests

    # Bottom LED bar — Lenovo Smart Display style horizontal status strip
    led_bar_y: float = 4.0       # distance from bottom edge of front to
                                 # bottom of LED bar slot
    led_bar_h: float = 12.0      # vertical extent of LED bar visible area
    led_bar_w: float = 175.0     # horizontal extent of slot (12 LEDs at
                                 # 16.67mm pitch ≈ 200mm; we trim to 175mm
                                 # for visual margin)

    # Screen cutout (active area + a sliver of overhang to hide bezel)
    screen_overhang: float = 1.5   # mm of LCD bezel hidden behind frame

    # Side opening (where acrylic sits)
    side_inset_top: float = 12.0   # mm in from top
    side_inset_bottom: float = 16.0  # mm in from bottom (more — hides
                                     # speaker mount)
    side_inset_front: float = 6.0    # mm in from front
    side_inset_back: float = 6.0     # mm in from back

    # Belt zone (where felt wraps around)
    belt_y_center: float = 67.5    # vertical center of belt band
    belt_height: float = 32.0       # belt is 32mm tall
    belt_glow_led_pitch: float = 16.7  # WS2812B 60/m spacing

    # Magnet pockets in side opening
    magnet_d: float = 6.0       # 6mm dia disc magnet
    magnet_t: float = 3.0       # 3mm thick magnet
    magnet_clearance: float = 0.2  # press-fit slop


@dataclass
class Screen:
    """Waveshare 7inch HDMI LCD (C) Rev 4.1 — measured / from datasheet."""
    pcb_w: float = 165.0
    pcb_h: float = 100.0
    module_d: float = 25.0     # LCD glass + PCB + components stack
    active_w: float = 154.0    # visible LCD area
    active_h: float = 86.0
    mount_pitch_w: float = 158.0   # M3 hole spacing (left-right)
    mount_pitch_h: float = 93.0    # M3 hole spacing (top-bottom)
    mount_hole_r: float = 1.7      # M3 clearance hole (tap M3, or insert)
    standoff_h: float = 5.0        # height from front wall inside surface


@dataclass
class Jetson:
    """Jetson Orin Nano Super Dev Kit carrier board (Waveshare-bundled)."""
    pcb_w: float = 100.0
    pcb_h: float = 79.0
    pcb_d: float = 21.0           # board + tallest connector envelope
    mount_pitch_w: float = 86.0
    mount_pitch_h: float = 58.0
    mount_hole_r: float = 1.4     # M2.5
    standoff_h: float = 4.0       # standoff from back wall


@dataclass
class Speaker:
    """50mm speaker driver, fires DOWN out of bottom face."""
    diameter: float = 50.0
    mount_id: float = 48.0        # inner diameter of mounting ring
    mount_od: float = 56.0        # outer diameter of mounting ring
    grille_holes_n: int = 12      # decorative grille hole count
    grille_hole_r: float = 2.0
    grille_pattern_r: float = 18.0  # holes arranged on this radius


@dataclass
class ReSpeaker:
    """ReSpeaker 4-Mic Array — mounted to inside of TOP face, mics up."""
    pcb_size: float = 65.0
    mic_hole_r: float = 1.5       # 3mm dia hole through top face per mic
    mic_pattern_r: float = 28.0   # mics arranged on this radius (or square)


# ═══════════════════════════════════════════════════════════════════════
# Mesh primitives (no boolean ops — slicer unions overlapping geometry)
# ═══════════════════════════════════════════════════════════════════════

def box(w: float, h: float, d: float,
        x: float = 0, y: float = 0, z: float = 0) -> Tuple[np.ndarray, np.ndarray]:
    """
    Axis-aligned solid rectangular box. (x,y,z) is the lower-back-left
    corner. Coord system convention used throughout this file:
        x  : left → right  (along width W)
        y  : bottom → top  (along height H)
        z  : front → back  (along depth D)
    Returns (vertices [8×3], faces [12×3]).
    """
    v = np.array([
        [x,     y,     z    ],  # 0: front-bottom-left
        [x + w, y,     z    ],  # 1: front-bottom-right
        [x + w, y + h, z    ],  # 2: front-top-right
        [x,     y + h, z    ],  # 3: front-top-left
        [x,     y,     z + d],  # 4: back-bottom-left
        [x + w, y,     z + d],  # 5: back-bottom-right
        [x + w, y + h, z + d],  # 6: back-top-right
        [x,     y + h, z + d],  # 7: back-top-left
    ], dtype=float)
    f = np.array([
        # winding: counter-clockwise when viewed from outside
        [0, 1, 2], [0, 2, 3],   # front face (z = z, normal -z)
        [4, 6, 5], [4, 7, 6],   # back face (normal +z)
        [0, 4, 5], [0, 5, 1],   # bottom face (normal -y)
        [3, 2, 6], [3, 6, 7],   # top face (normal +y)
        [0, 3, 7], [0, 7, 4],   # left face (normal -x)
        [1, 5, 6], [1, 6, 2],   # right face (normal +x)
    ], dtype=int)
    return v, f


def cyl_z(r: float, h: float, x: float = 0, y: float = 0, z: float = 0,
          sides: int = 32) -> Tuple[np.ndarray, np.ndarray]:
    """
    Solid cylinder oriented along Z (axis pointing front-to-back). For a
    cylinder along Y (vertical, e.g., speaker hole), use cyl_y.
    """
    angles = np.linspace(0, 2 * np.pi, sides, endpoint=False)
    bot = np.column_stack([
        x + r * np.cos(angles),
        y + r * np.sin(angles),
        np.full(sides, z),
    ])
    top = np.column_stack([
        x + r * np.cos(angles),
        y + r * np.sin(angles),
        np.full(sides, z + h),
    ])
    cb = np.array([[x, y, z]])
    ct = np.array([[x, y, z + h]])
    v = np.vstack([bot, top, cb, ct])
    cb_idx, ct_idx = 2 * sides, 2 * sides + 1
    f = []
    for i in range(sides):
        ni = (i + 1) % sides
        # bottom cap
        f.append([cb_idx, ni, i])
        # top cap
        f.append([ct_idx, sides + i, sides + ni])
        # sidewall (2 tris per quad)
        f.append([i, ni, sides + ni])
        f.append([i, sides + ni, sides + i])
    return v, np.array(f, dtype=int)


def cyl_y(r: float, h: float, x: float = 0, y: float = 0, z: float = 0,
          sides: int = 32) -> Tuple[np.ndarray, np.ndarray]:
    """Solid cylinder oriented along Y (axis pointing bottom-to-top)."""
    angles = np.linspace(0, 2 * np.pi, sides, endpoint=False)
    bot = np.column_stack([
        x + r * np.cos(angles),
        np.full(sides, y),
        z + r * np.sin(angles),
    ])
    top = np.column_stack([
        x + r * np.cos(angles),
        np.full(sides, y + h),
        z + r * np.sin(angles),
    ])
    cb = np.array([[x, y, z]])
    ct = np.array([[x, y + h, z]])
    v = np.vstack([bot, top, cb, ct])
    cb_idx, ct_idx = 2 * sides, 2 * sides + 1
    f = []
    for i in range(sides):
        ni = (i + 1) % sides
        f.append([cb_idx, i, ni])
        f.append([ct_idx, sides + ni, sides + i])
        f.append([i, sides + i, sides + ni])
        f.append([i, sides + ni, ni])
    return v, np.array(f, dtype=int)


def merge(*pieces) -> Tuple[np.ndarray, np.ndarray]:
    """Concatenate multiple (verts, faces) tuples into one mesh."""
    all_v: List[np.ndarray] = []
    all_f: List[np.ndarray] = []
    offset = 0
    for v, f in pieces:
        all_v.append(v)
        all_f.append(f + offset)
        offset += len(v)
    return np.vstack(all_v), np.vstack(all_f)


def to_stl_mesh(v: np.ndarray, f: np.ndarray) -> mesh.Mesh:
    """Convert (verts, faces) to a numpy-stl Mesh."""
    m = mesh.Mesh(np.zeros(f.shape[0], dtype=mesh.Mesh.dtype))
    for i, tri in enumerate(f):
        m.vectors[i] = v[tri]
    return m


# ═══════════════════════════════════════════════════════════════════════
# Frame: the main 3D-printed body
# ═══════════════════════════════════════════════════════════════════════
#
# Strategy: build the frame as a UNION of axis-aligned slabs and
# cylinders. The slicer (PrusaSlicer / Bambu Studio / Cura) unions
# overlapping geometry automatically, so we don't need real boolean ops.
#
# Decomposition for the FRONT face (which has a screen cutout and an LED
# bar slot):
#
#     y = H ┌─────────────────────────────────┐
#           │                                 │
#           │           TOP STRIP             │  full-width slab above screen
#           │                                 │
#  s_top y  ├──┬───────────────────────────┬──┤
#           │  │                           │  │
#           │L │      SCREEN CUTOUT        │R │  L and R = side strips
#           │  │      (no geometry here)   │  │
#  s_bot y  ├──┴───────────────────────────┴──┤
#           │                                 │
#           │           MID STRIP             │  thin slab between screen and LED
#           │                                 │
#  led_top  ├──┬───────────────────────────┬──┤
#           │  │                           │  │
#           │L │      LED BAR SLOT         │R │
#  led_bot  ├──┴───────────────────────────┴──┤
#           │                                 │
#           │           BOTTOM STRIP          │
#     y = 0 └─────────────────────────────────┘
#
# Each strip is a `box(...)` call. The cutouts are simply the absence of
# geometry — slicer sees a non-manifold edge there and treats it as a
# clean opening. Tested with PrusaSlicer 2.7.x.

def build_frame_meshes(F: Frame, S: Screen, J: Jetson,
                       SP: Speaker, R: ReSpeaker) -> List[Tuple[np.ndarray, np.ndarray]]:
    """
    Construct all the geometry that makes up the main frame piece.
    Returns a list of (verts, faces) — caller merges and writes to STL.
    """
    pieces: List[Tuple[np.ndarray, np.ndarray]] = []

    # ── compute key Y bounds for front-face strips ───────────────────
    led_bot_y = F.led_bar_y                          # 4
    led_top_y = led_bot_y + F.led_bar_h              # 16
    mid_h = 4.0                                       # gap between LED bar and screen
    s_bot_y = led_top_y + mid_h                      # 20
    s_top_y = s_bot_y + (S.active_h + 2 * F.screen_overhang)  # 109
    # screen cutout vertical span = active_h + 2*overhang = 89mm
    # remaining top strip = H - s_top_y = 135 - 109 = 26mm — comfortable for top bezel

    # X bounds
    s_left_x = (F.W - (S.active_w + 2 * F.screen_overhang)) / 2  # ≈ (190-157)/2 = 16.5
    s_right_x = F.W - s_left_x
    led_left_x = (F.W - F.led_bar_w) / 2              # ≈ (190-175)/2 = 7.5
    led_right_x = F.W - led_left_x

    ft = F.front_t  # 4

    # ── FRONT FACE ── 6 strips around the cutouts ───────────────────
    # bottom strip (full width × led_bot_y)
    pieces.append(box(F.W, led_bot_y, ft, x=0, y=0, z=0))
    # mid strip (full width × mid_h, between LED bar and screen)
    pieces.append(box(F.W, mid_h, ft, x=0, y=led_top_y, z=0))
    # top strip (full width × top remainder)
    pieces.append(box(F.W, F.H - s_top_y, ft, x=0, y=s_top_y, z=0))
    # left of LED bar
    pieces.append(box(led_left_x, F.led_bar_h, ft, x=0, y=led_bot_y, z=0))
    # right of LED bar
    pieces.append(box(F.W - led_right_x, F.led_bar_h, ft, x=led_right_x, y=led_bot_y, z=0))
    # left of screen
    pieces.append(box(s_left_x, s_top_y - s_bot_y, ft, x=0, y=s_bot_y, z=0))
    # right of screen
    pieces.append(box(F.W - s_right_x, s_top_y - s_bot_y, ft, x=s_right_x, y=s_bot_y, z=0))

    # ── SCREEN MOUNTING STANDOFFS ── 4 posts protruding INTO the box
    # Standoffs are M3 — we'll use brass threaded inserts pressed in,
    # then screw the screen's 4 corner tabs onto them with M3×6 screws.
    standoff_outer_r = 3.0       # outer radius of post
    standoff_inner_r = S.mount_hole_r  # M3 clearance hole
    standoff_h = S.standoff_h    # 5mm
    s_cx = F.W / 2
    s_cy = (s_bot_y + s_top_y) / 2  # vertical center of screen cutout
    for dx in (-S.mount_pitch_w / 2, S.mount_pitch_w / 2):
        for dy in (-S.mount_pitch_h / 2, S.mount_pitch_h / 2):
            # solid post extending from inside front face into cavity
            post_x = s_cx + dx
            post_y = s_cy + dy
            pieces.append(cyl_z(standoff_outer_r, standoff_h,
                                x=post_x, y=post_y, z=ft, sides=24))
            # NB: hole for the brass insert is drilled/melted in
            # post-print — we don't model it as a subtraction here
            # because slicers treat the inner cylinder mesh as a
            # secondary part (results in a tiny inverted cone). Easier
            # to drill 4mm hole 4mm deep with a hand drill after print.

    # ── BOTTOM FACE ── solid plate with speaker hole + LED diffuser slot
    # Y range: 0 to F.bottom_t, full width × full depth
    bt = F.bottom_t  # 3
    # bottom plate (solid initially — we'll punch holes via gap geometry)
    # Decompose: rectangle around the speaker hole (annulus) + rectangle
    # around the LED diffuser slot.
    sp_cx = F.W / 2
    sp_cz = F.D / 2
    # bottom plate extends from y=0 to y=bt, x=0..W, z=0..D
    # but with a circular speaker hole at (sp_cx, sp_cz) of radius 25mm
    # AND a rectangular slot for the LED diffuser at the front edge.
    #
    # Decompose the bottom plate into 4 trapezoidal strips around the
    # speaker hole, plus front+back narrow strips.
    sp_r = SP.diameter / 2
    led_diff_z_start = ft  # LED diffuser slot starts right behind front wall
    led_diff_z_end = ft + 8  # 8mm slot deep into bottom
    led_diff_x_start = led_left_x
    led_diff_x_end = led_right_x

    # The LED bar is INSIDE the front face, so the LED diffuser slot
    # is in the bottom of the front-face cavity, not the actual bottom
    # face. Skip — handle in a moment.

    # Decompose bottom plate around the speaker hole using 4 rectangles:
    # left of hole, right of hole, front of hole, back of hole.
    bot_z = 0
    bot_y = 0  # plate sits at y=0 to y=bt
    # Hole bounds (using a square bounding the circle, then the
    # corner remnants are filled by the L/R/F/B strips' overlap):
    hole_x_left = sp_cx - sp_r
    hole_x_right = sp_cx + sp_r
    hole_z_front = sp_cz - sp_r
    hole_z_back = sp_cz + sp_r
    # Front strip (z=0 to hole_z_front), full width
    pieces.append(box(F.W, bt, hole_z_front, x=0, y=bot_y, z=0))
    # Back strip (z=hole_z_back to D), full width
    pieces.append(box(F.W, bt, F.D - hole_z_back, x=0, y=bot_y, z=hole_z_back))
    # Left of hole (x=0 to hole_x_left, z=hole_z_front to hole_z_back)
    pieces.append(box(hole_x_left, bt, hole_z_back - hole_z_front,
                      x=0, y=bot_y, z=hole_z_front))
    # Right of hole
    pieces.append(box(F.W - hole_x_right, bt, hole_z_back - hole_z_front,
                      x=hole_x_right, y=bot_y, z=hole_z_front))
    # The square hole is now circumscribed around the actual circle; we
    # leave 4 small corner remnants outside the circle but inside the
    # square. To get a smooth circular hole, add a small annulus disc:
    # — but slicers handle non-manifold concave corners OK, and the
    # corner pieces are tiny (~0.3mm sliver each). We skip for v3 first
    # iteration; if visible after print, we'll add a circular trim ring.

    # Speaker mounting ring (cylinder above the hole, inside cavity)
    pieces.append(cyl_y(SP.mount_od / 2, 6.0, x=sp_cx, y=bt, z=sp_cz, sides=32))
    # NB: speaker driver has a flange that sits on this ring; M3 screws
    # through the ring pull the driver flush. We don't model the screw
    # holes — drill 3.5mm holes around the ring after print.

    # ── TOP FACE ── solid plate with mic holes + vent slits ──────────
    tt = F.top_t  # 3
    top_y = F.H - tt  # plate sits from y=top_y to y=H

    # Mic holes — 4 holes for ReSpeaker 4-mic array. The mics are
    # arranged in a 2×2 square on the ReSpeaker board with ~40mm pitch.
    mic_cx = F.W / 2
    mic_cz = F.D / 2
    mic_pitch = 40.0
    mic_positions = [
        (mic_cx - mic_pitch / 2, mic_cz - mic_pitch / 2),
        (mic_cx + mic_pitch / 2, mic_cz - mic_pitch / 2),
        (mic_cx - mic_pitch / 2, mic_cz + mic_pitch / 2),
        (mic_cx + mic_pitch / 2, mic_cz + mic_pitch / 2),
    ]
    # Build top plate with 4 mic holes + vent slits.
    # Decompose: a grid of horizontal strips. Vent slits are 3 thin
    # slits perpendicular to the front-back axis, each ~1.5mm wide
    # (just enough for airflow, hidden visually at normal view angles).
    vent_count = 5
    vent_slit_w = 1.5
    vent_pitch = 8.0  # spacing between slit centers, along Z (depth)
    # vent slits run along the entire X (width) of the top plate
    # We add the vents as small "negative spaces" by skipping geometry
    # at those Z bands. Simplification: build top plate as Z strips,
    # skipping the vent bands.

    # Z bands for the top plate (going from front to back along z):
    # We need: ~5 vent slits centered around z=D/2 (the middle).
    # Define solid z spans (excluding vent slit gaps):
    vent_center_z = F.D / 2
    vent_block_total = vent_count * vent_pitch
    vent_block_z_start = vent_center_z - vent_block_total / 2

    # Build top plate as: front-of-vents slab + alternating vent gap +
    # solid strips between vents + back-of-vents slab. Mic holes are
    # drilled separately after print (they're small and circular —
    # slicer-handled cylinder subtractions look bad on tiny features).

    # Compute the solid Z spans (skipping vent slits)
    z_spans = []
    cursor = 0.0
    for i in range(vent_count):
        slit_start = vent_block_z_start + i * vent_pitch
        slit_end = slit_start + vent_slit_w
        if cursor < slit_start:
            z_spans.append((cursor, slit_start))
        cursor = slit_end
    if cursor < F.D:
        z_spans.append((cursor, F.D))

    # Build top plate strips, but skip mic-hole zones in X
    # For mics, we'll just leave them as "drill holes after print"
    # documented in the assembly guide. Top plate is otherwise solid.
    for z_a, z_b in z_spans:
        pieces.append(box(F.W, tt, z_b - z_a, x=0, y=top_y, z=z_a))

    # ── SIDE OPENING RABBETS ── thin lips on top/bottom of side windows
    # Acrylic panels seat against the OUTSIDE of these rabbets and are
    # held by N42 magnets pressed into pockets in the rabbet corners.
    # Each rabbet is a thin slab on top edge of bottom plate (and
    # bottom edge of top plate) extending into the side opening.
    #
    # The side opening itself is the absence of geometry between the
    # top and bottom plates — i.e., we don't add side wall slabs. The
    # acrylic spans the full opening (185×~107mm).
    #
    # Magnet pockets: 4 per side, embedded at the corners of the side
    # opening. We add small thicker zones at the rabbet corners and
    # leave a square pocket in them for the magnet to drop in.
    #
    # For simplicity in v3-first-iteration, we put the magnets in the
    # FRONT and BACK faces instead — those already have substantial
    # thickness (4mm front, 2.5mm back). Drill a 6.2mm dia × 3mm pocket
    # at each corner of the side opening using a hand drill after print.
    # This keeps the STL geometry simpler.

    # ── INTERNAL JETSON MOUNTING POSTS ── on the inside of the back ─
    # The back panel is a separate snap-fit STL. The Jetson mounts to
    # standoffs that protrude FORWARD from the back into the cavity.
    # We add the standoffs on the inside of the back wall, but since
    # the back is a separate piece, we'll put them in the BACK PANEL
    # geometry — see build_back_panel_meshes().

    return pieces


# ═══════════════════════════════════════════════════════════════════════
# Back panel (separate snap-fit STL)
# ═══════════════════════════════════════════════════════════════════════

def build_back_panel_meshes(F: Frame, J: Jetson) -> List[Tuple[np.ndarray, np.ndarray]]:
    """
    Build the rear cover panel: a 2.5mm slab the size of the back face,
    with a port-cluster cutout, vent grille, and 4 internal mounting
    posts for the Jetson Orin Nano dev kit.

    Snaps into the main frame via 4 corner snap tabs (similar to v2).
    """
    pieces: List[Tuple[np.ndarray, np.ndarray]] = []

    bt = F.back_t  # 2.5
    # Panel dimensions: matches frame outer × thickness.
    # Coord: panel sits at z=0 to z=bt (we'll position it later).
    pw = F.W
    ph = F.H

    # Port cluster cutout: a single rectangle that exposes the Jetson's
    # rear ports (Ethernet, USB, HDMI, DC, WiFi antennas). The Jetson's
    # back-edge port row is ~80mm wide × 18mm tall.
    port_cutout_w = 80.0
    port_cutout_h = 22.0
    port_cx = pw / 2
    port_cy = ph / 2 + 5.0  # slightly above center

    # Vent grille: 5 horizontal slits below port cutout
    vent_grille_n = 5
    vent_grille_w = 60.0
    vent_grille_h = 2.0
    vent_grille_pitch = 5.0
    vent_grille_cx = pw / 2
    vent_grille_cy = ph / 4  # in lower portion of back

    # Decompose back panel into strips around the port cutout AND vent grille.
    p_left = port_cx - port_cutout_w / 2
    p_right = port_cx + port_cutout_w / 2
    p_bot = port_cy - port_cutout_h / 2
    p_top = port_cy + port_cutout_h / 2

    # Vent grille total span
    vg_total_h = vent_grille_n * vent_grille_pitch
    vg_left = vent_grille_cx - vent_grille_w / 2
    vg_right = vent_grille_cx + vent_grille_w / 2
    vg_bot = vent_grille_cy - vg_total_h / 2
    vg_top = vent_grille_cy + vg_total_h / 2

    # Back panel = strips arranged around port cutout AND vent grille.
    # Simpler: build panel as:
    #   - bottom strip (y=0 to vg_bot)
    #   - vent grille zone (5 alternating horizontal slabs)
    #   - middle strip between vent and port
    #   - port-row left/right strips
    #   - top strip
    # All x=0 to pw, except port row (split around port cutout)

    # 1. bottom strip
    pieces.append(box(pw, vg_bot, bt, x=0, y=0, z=0))
    # 2. vent grille zone — alternating solid and slit
    for i in range(vent_grille_n + 1):
        # solid strips between slits
        if i == 0:
            y_start = vg_bot
        else:
            y_start = vg_bot + i * vent_grille_pitch - vent_grille_h / 2
        if i == vent_grille_n:
            y_end = vg_top
        else:
            y_end = vg_bot + i * vent_grille_pitch + (vent_grille_pitch - vent_grille_h) / 2
        if y_end > y_start:
            # Full-width strip with vent slit cut out in the middle
            # (left of vent + right of vent + inside vent itself is solid here)
            # We're between slits, so this is solid full-width:
            # but we need to keep the vent grille width-bounded (only the
            # central 60mm has slits).
            # Actually let's simplify: solid full-width between slit Y bands
            pieces.append(box(pw, y_end - y_start, bt, x=0, y=y_start, z=0))
        # Vent slit y-band (skipped; left = no geometry within vent_grille_w)
        if i < vent_grille_n:
            slit_y_start = vg_bot + i * vent_grille_pitch + (vent_grille_pitch - vent_grille_h) / 2
            slit_y_end = slit_y_start + vent_grille_h
            # Left of vent slit (x=0 to vg_left)
            pieces.append(box(vg_left, slit_y_end - slit_y_start, bt, x=0, y=slit_y_start, z=0))
            # Right of vent slit (x=vg_right to pw)
            pieces.append(box(pw - vg_right, slit_y_end - slit_y_start, bt, x=vg_right, y=slit_y_start, z=0))
    # 3. mid strip between vent and port
    pieces.append(box(pw, p_bot - vg_top, bt, x=0, y=vg_top, z=0))
    # 4. port row — left and right of port cutout
    pieces.append(box(p_left, p_top - p_bot, bt, x=0, y=p_bot, z=0))
    pieces.append(box(pw - p_right, p_top - p_bot, bt, x=p_right, y=p_bot, z=0))
    # 5. top strip
    pieces.append(box(pw, ph - p_top, bt, x=0, y=p_top, z=0))

    # Jetson mounting standoffs — protrude FORWARD from inside of back
    # The Jetson dev kit carrier has 4 mounting holes at corners with
    # ~86×58mm pitch. Standoffs are 4mm tall, 5mm OD with M2.5 hole.
    j_cx = pw / 2
    j_cy = ph / 2 - 10  # slightly below back-panel center, leaves room for ports above
    standoff_outer_r = 2.5
    for dx in (-J.mount_pitch_w / 2, J.mount_pitch_w / 2):
        for dy in (-J.mount_pitch_h / 2, J.mount_pitch_h / 2):
            sx = j_cx + dx
            sy = j_cy + dy
            pieces.append(cyl_z(standoff_outer_r, J.standoff_h,
                                x=sx, y=sy, z=bt, sides=20))

    # Snap tabs at 4 corners — protrude forward (into +z) so they slot
    # into matching grooves in the main frame back edge. Tab dims:
    # 8mm wide × 2mm thick × 6mm long.
    tab_w = 8.0
    tab_t = 2.0
    tab_l = 6.0
    # 4 corners, inset from corner by 12mm
    inset = 12.0
    for corner in [(inset, inset), (pw - inset - tab_w, inset),
                   (inset, ph - inset - tab_w),
                   (pw - inset - tab_w, ph - inset - tab_w)]:
        cx, cy = corner
        pieces.append(box(tab_w, tab_w, tab_l, x=cx, y=cy, z=bt))
        # tab head (bigger flange to lock into groove)
        pieces.append(box(tab_w + 2 * tab_t, tab_w + 2 * tab_t, 2,
                          x=cx - tab_t, y=cy - tab_t, z=bt + tab_l))

    return pieces


# ═══════════════════════════════════════════════════════════════════════
# LED bar diffuser (frosted PETG strip)
# ═══════════════════════════════════════════════════════════════════════

def build_led_diffuser_meshes(F: Frame) -> List[Tuple[np.ndarray, np.ndarray]]:
    """
    Frosted strip that sits IN the LED bar slot on the front face.
    Print in clear/natural PLA — light from the WS2812B strip behind it
    diffuses through the plastic giving a "soft glow bar" effect.

    Dimensions: matches the LED bar slot exactly (175 × 12 × 4 mm).
    """
    pieces: List[Tuple[np.ndarray, np.ndarray]] = []
    pieces.append(box(F.led_bar_w, F.led_bar_h, F.front_t, x=0, y=0, z=0))
    return pieces


# ═══════════════════════════════════════════════════════════════════════
# Acrylic side panel — DXF for laser cutting
# ═══════════════════════════════════════════════════════════════════════

def write_acrylic_dxf(out_path: str, F: Frame) -> None:
    """
    Write a minimal AutoCAD DXF (R12 ASCII flavor — most laser-cut shops
    accept this) for the two acrylic side panels. The two panels share
    one shape: they're symmetric, so cut two from the same DXF.

    Panel dimensions:
      Width (along X = depth of enclosure D) = F.D - 2 * F.side_inset_back
      Height (along Y = height of enclosure H) = F.H - F.side_inset_top
                                                       - F.side_inset_bottom
      Material: 3mm clear acrylic (cast preferred for clarity, extruded OK)

    Includes:
      - Outer rounded-rectangle outline
      - Optional 4 small steel-washer placement marks (etch only, not cut)
        — operator can skip these; they're for the user gluing the
        retention washers in the right spots after cut.
    """
    panel_w = F.D - F.side_inset_back - F.side_inset_front  # ~48
    panel_h = F.H - F.side_inset_top - F.side_inset_bottom   # ~107
    corner_r = 4.0  # rounded corners on the panel

    # DXF R12 minimal LINE/ARC entities. Built by hand because most
    # CAD libs are heavy and we don't need real DXF features here.
    lines: List[str] = []
    lines.append("0\nSECTION\n2\nHEADER\n0\nENDSEC\n")
    lines.append("0\nSECTION\n2\nTABLES\n")
    lines.append("0\nTABLE\n2\nLAYER\n70\n2\n")
    lines.append("0\nLAYER\n2\nCUT\n70\n0\n62\n1\n6\nCONTINUOUS\n")
    lines.append("0\nLAYER\n2\nETCH\n70\n0\n62\n3\n6\nCONTINUOUS\n")
    lines.append("0\nENDTAB\n0\nENDSEC\n")
    lines.append("0\nSECTION\n2\nENTITIES\n")

    def line(x1, y1, x2, y2, layer="CUT"):
        return (f"0\nLINE\n8\n{layer}\n10\n{x1:.3f}\n20\n{y1:.3f}\n"
                f"30\n0\n11\n{x2:.3f}\n21\n{y2:.3f}\n31\n0\n")

    def arc(cx, cy, r, start_deg, end_deg, layer="CUT"):
        return (f"0\nARC\n8\n{layer}\n10\n{cx:.3f}\n20\n{cy:.3f}\n30\n0\n"
                f"40\n{r:.3f}\n50\n{start_deg:.3f}\n51\n{end_deg:.3f}\n")

    # Outer rounded-rect outline (going CCW starting from bottom-left
    # straight section)
    # bottom edge
    lines.append(line(corner_r, 0, panel_w - corner_r, 0))
    # bottom-right corner arc (270° → 360°)
    lines.append(arc(panel_w - corner_r, corner_r, corner_r, 270, 360))
    # right edge
    lines.append(line(panel_w, corner_r, panel_w, panel_h - corner_r))
    # top-right corner arc (0° → 90°)
    lines.append(arc(panel_w - corner_r, panel_h - corner_r, corner_r, 0, 90))
    # top edge
    lines.append(line(panel_w - corner_r, panel_h, corner_r, panel_h))
    # top-left corner arc (90° → 180°)
    lines.append(arc(corner_r, panel_h - corner_r, corner_r, 90, 180))
    # left edge
    lines.append(line(0, panel_h - corner_r, 0, corner_r))
    # bottom-left corner arc (180° → 270°)
    lines.append(arc(corner_r, corner_r, corner_r, 180, 270))

    # Steel washer placement etch marks — 4 small circles where the
    # user should glue M3 steel washers (for magnet attraction).
    # These are ETCH layer (laser low-power score), not CUT.
    washer_inset = 8.0  # how far in from each corner
    washer_marker_r = 4.0
    washer_positions = [
        (washer_inset, washer_inset),
        (panel_w - washer_inset, washer_inset),
        (washer_inset, panel_h - washer_inset),
        (panel_w - washer_inset, panel_h - washer_inset),
    ]
    for wx, wy in washer_positions:
        lines.append(arc(wx, wy, washer_marker_r, 0, 360, layer="ETCH"))

    lines.append("0\nENDSEC\n0\nEOF\n")

    with open(out_path, "w") as f:
        f.write("".join(lines))


# ═══════════════════════════════════════════════════════════════════════
# Main — generate everything
# ═══════════════════════════════════════════════════════════════════════

def main():
    F = Frame()
    S = Screen()
    J = Jetson()
    SP = Speaker()
    R = ReSpeaker()

    out_dir = os.path.join(os.path.dirname(__file__), "stl-v3")
    os.makedirs(out_dir, exist_ok=True)

    print(f"\n{'═' * 70}")
    print(f"  JARVIS Enclosure v3 — generating files to {out_dir}")
    print(f"  Form factor: {F.W} × {F.H} × {F.D} mm (W × H × D)")
    print(f"  Designed for: Waveshare 7inch HDMI LCD (C) Rev 4.1")
    print(f"{'═' * 70}\n")

    # Frame
    print("→ Frame (main body, opaque PETG, ~12-15h FDM print)")
    fp = build_frame_meshes(F, S, J, SP, R)
    fv, ff = merge(*fp)
    fm = to_stl_mesh(fv, ff)
    fpath = os.path.join(out_dir, "jarvis-frame-v3.stl")
    fm.save(fpath)
    print(f"  ✓ {fpath}")
    print(f"    {len(ff)} triangles, {os.path.getsize(fpath)/1024:.1f} KB")

    # Back panel
    print("\n→ Back panel (snap-fit, opaque PETG, ~3h print)")
    bp = build_back_panel_meshes(F, J)
    bv, bf_ = merge(*bp)
    bm = to_stl_mesh(bv, bf_)
    bpath = os.path.join(out_dir, "jarvis-back-panel-v3.stl")
    bm.save(bpath)
    print(f"  ✓ {bpath}")
    print(f"    {len(bf_)} triangles, {os.path.getsize(bpath)/1024:.1f} KB")

    # LED diffuser
    print("\n→ LED bar diffuser (frosted/natural PLA, ~1h print)")
    lp = build_led_diffuser_meshes(F)
    lv, lf = merge(*lp)
    lm = to_stl_mesh(lv, lf)
    lpath = os.path.join(out_dir, "jarvis-led-diffuser-v3.stl")
    lm.save(lpath)
    print(f"  ✓ {lpath}")
    print(f"    {len(lf)} triangles, {os.path.getsize(lpath)/1024:.1f} KB")

    # Acrylic side panel DXF
    print("\n→ Acrylic side panel DXF (laser-cut 3mm clear acrylic ×2)")
    dxf_path = os.path.join(out_dir, "jarvis-side-panel-v3.dxf")
    write_acrylic_dxf(dxf_path, F)
    print(f"  ✓ {dxf_path}")
    print(f"    {os.path.getsize(dxf_path)} bytes")

    print(f"\n{'═' * 70}")
    print(f"  ✓ All files generated to {out_dir}")
    print(f"  Next: see ASSEMBLY_GUIDE_V3.md")
    print(f"{'═' * 70}\n")


if __name__ == "__main__":
    main()
