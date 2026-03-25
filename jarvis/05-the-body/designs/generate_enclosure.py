#!/usr/bin/env python3
"""
Jarvis Voice Assistant Enclosure v2 Generator
Modular design with swappable front panels for screens.

Generates:
1. jarvis-base-v2.stl - Main body (open front/top)
2. jarvis-top-v2.stl - Top plate with mic holes + small screen cutout
3. jarvis-front-blank.stl - Blank front panel (speaker grille)
4. jarvis-front-screen-5in.stl - 5" screen front panel
5. jarvis-front-screen-7in.stl - 7" screen front panel
6. jarvis-grille-v2.stl - Speaker grille insert

Author: JARVIS enclosure team
Date: 2026-03-25
"""

import numpy as np
import math
from dataclasses import dataclass
from typing import List, Tuple
import os

# Try to import stl library
try:
    from stl import mesh
except ImportError:
    print("ERROR: numpy-stl not installed. Run: pip install numpy-stl")
    exit(1)


@dataclass
class Dimensions:
    """Main enclosure dimensions (mm)."""
    width: float = 160  # X axis
    depth: float = 160  # Y axis
    height: float = 85  # Z axis (taller to accommodate front screen)
    wall_thickness: float = 2.5
    snap_tab_thickness: float = 2.0
    snap_tab_width: float = 10.0
    snap_tab_tolerance: float = 0.3
    corner_radius: float = 12  # For squircle shape
    back_tilt_angle: float = 10  # Degrees, tilts back wall so screen tilts forward


@dataclass
class ComponentLocations:
    """Positions of internal components (mm, from bottom-left-front)."""
    # Jetson Orin Nano: 100x79x21mm
    jetson_x: float = 30  # Center X
    jetson_y: float = 40  # Center Y (in from back)
    jetson_z: float = 2.5  # On bottom
    jetson_w: float = 100
    jetson_d: float = 79

    # ReSpeaker 4-Mic Array: 65x65mm circular
    speaker_mic_x: float = 80  # Center of top
    speaker_mic_y: float = 80  # Center of top

    # WS2812B 24-LED ring: 72mm OD
    led_ring_radius: float = 36  # Outer radius

    # 50mm speaker on left side
    speaker_center_x: float = 20  # Left side
    speaker_center_y: float = 80  # Middle height
    speaker_diameter: float = 50


def create_squircle_2d(width: float, height: float, radius: float, segments: int = 64) -> np.ndarray:
    """Create 2D squircle (rounded rectangle) points."""
    points = []
    half_w = width / 2
    half_h = height / 2

    # Use Lamé curve: |x/a|^n + |y/b|^n = 1, n=2.5 for squircle
    n = 2.5
    for i in range(segments):
        angle = 2 * math.pi * i / segments
        # Parameterized squircle
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        x = half_w * np.sign(cos_a) * abs(cos_a) ** (2/n)
        y = half_h * np.sign(sin_a) * abs(sin_a) ** (2/n)
        points.append([x, y])

    return np.array(points)


def extrude_closed_path(path_2d: np.ndarray, height: float, z_offset: float = 0) -> np.ndarray:
    """Extrude a 2D path to create a 3D mesh (walls only, open top/bottom)."""
    n_points = len(path_2d)
    vertices = []
    faces = []

    # Bottom ring of points
    for i in range(n_points):
        vertices.append([path_2d[i][0], path_2d[i][1], z_offset])

    # Top ring of points
    for i in range(n_points):
        vertices.append([path_2d[i][0], path_2d[i][1], z_offset + height])

    # Create side walls
    for i in range(n_points):
        bottom_current = i
        bottom_next = (i + 1) % n_points
        top_current = i + n_points
        top_next = ((i + 1) % n_points) + n_points

        # Two triangles per quad
        faces.append([bottom_current, bottom_next, top_current])
        faces.append([bottom_next, top_next, top_current])

    return np.array(vertices), np.array(faces)


def create_cylinder_mesh(radius: float, height: float, z_offset: float = 0, segments: int = 32) -> Tuple[np.ndarray, np.ndarray]:
    """Create a cylinder mesh (walls only)."""
    vertices = []
    faces = []

    # Bottom circle
    for i in range(segments):
        angle = 2 * math.pi * i / segments
        x = radius * math.cos(angle)
        y = radius * math.sin(angle)
        vertices.append([x, y, z_offset])

    # Top circle
    for i in range(segments):
        angle = 2 * math.pi * i / segments
        x = radius * math.cos(angle)
        y = radius * math.sin(angle)
        vertices.append([x, y, z_offset + height])

    # Side walls
    for i in range(segments):
        bottom_current = i
        bottom_next = (i + 1) % segments
        top_current = i + segments
        top_next = ((i + 1) % segments) + segments

        faces.append([bottom_current, bottom_next, top_current])
        faces.append([bottom_next, top_next, top_current])

    return np.array(vertices), np.array(faces)


def create_rectangular_hole(width: float, height: float, x_center: float, y_center: float,
                           path_2d: np.ndarray, segments_per_side: int = 8) -> np.ndarray:
    """Add a rectangular hole to a 2D path by cutting out corners."""
    half_w = width / 2
    half_h = height / 2

    hole_points = [
        [x_center - half_w, y_center - half_h],
        [x_center + half_w, y_center - half_h],
        [x_center + half_w, y_center + half_h],
        [x_center - half_w, y_center + half_h],
    ]

    return np.array(hole_points)


def create_circular_holes(center_x: float, center_y: float, radius: float,
                         hole_radius: float, num_holes: int = 4,
                         start_angle: float = 0) -> List[Tuple[float, float, float]]:
    """Create positions for circular holes (e.g., mic mounting)."""
    holes = []
    for i in range(num_holes):
        angle = start_angle + (2 * math.pi * i / num_holes)
        x = center_x + radius * math.cos(angle)
        y = center_y + radius * math.sin(angle)
        holes.append((x, y, hole_radius))
    return holes


def create_snap_tabs(width: float, num_tabs: int = 2, z_height: float = 0,
                    tab_thickness: float = 2.0, tab_width: float = 10.0) -> Tuple[np.ndarray, np.ndarray]:
    """Create snap-fit tabs along an edge."""
    tab_spacing = width / (num_tabs + 1)
    vertices = []
    faces = []

    for tab_idx in range(num_tabs):
        x_pos = -width/2 + tab_spacing * (tab_idx + 1)

        # Four corners of tab
        v0 = [x_pos - tab_width/2, 0, z_height]
        v1 = [x_pos + tab_width/2, 0, z_height]
        v2 = [x_pos + tab_width/2, tab_thickness, z_height]
        v3 = [x_pos - tab_width/2, tab_thickness, z_height]

        start_idx = len(vertices)
        vertices.extend([v0, v1, v2, v3])
        faces.extend([
            [start_idx, start_idx+1, start_idx+2],
            [start_idx, start_idx+2, start_idx+3]
        ])

    return np.array(vertices), np.array(faces)


def create_mounting_posts(locations: List[Tuple[float, float]], post_diameter: float = 3.5,
                         post_height: float = 5, z_offset: float = 0) -> Tuple[np.ndarray, np.ndarray]:
    """Create cylindrical mounting posts at specific locations."""
    all_vertices = []
    all_faces = []

    for x, y in locations:
        verts, faces = create_cylinder_mesh(post_diameter/2, post_height, z_offset=z_offset, segments=16)
        offset = len(all_vertices)
        verts[:, 0] += x
        verts[:, 1] += y
        all_vertices.extend(verts)
        all_faces.extend(faces + offset)

    return np.array(all_vertices), np.array(all_faces)


def create_base_shell(dims: Dimensions, components: ComponentLocations) -> mesh.Mesh:
    """Create the main base shell (open front and top)."""

    # Create outer squircle
    outer_path = create_squircle_2d(dims.width, dims.depth, dims.corner_radius, segments=64)

    # Create inner squircle (wall thickness)
    inner_shrink = dims.width - 2 * dims.wall_thickness
    inner_path = create_squircle_2d(inner_shrink, dims.depth - 2 * dims.wall_thickness,
                                    dims.corner_radius - dims.wall_thickness, segments=64)

    # Extrude outer wall
    outer_verts, outer_faces = extrude_closed_path(outer_path, dims.height - dims.wall_thickness, z_offset=0)

    # Extrude inner wall (reverse winding for inside)
    inner_verts, inner_faces = extrude_closed_path(inner_path, dims.height - dims.wall_thickness, z_offset=0)
    inner_faces = inner_faces[:, ::-1]  # Reverse winding

    # Combine vertices and offset inner
    all_verts = outer_verts.tolist()
    all_faces = outer_faces.tolist()
    offset = len(all_verts)
    for v in inner_verts:
        all_verts.append(v)
    for f in inner_faces:
        all_faces.append(f + offset)

    # Create bottom plate
    outer_bottom = outer_path.copy()
    inner_bottom = inner_path.copy()

    bottom_offset = len(all_verts)
    for v in outer_bottom:
        all_verts.append([v[0], v[1], 0])
    for v in inner_bottom:
        all_verts.append([v[0], v[1], 0])

    n_outer = len(outer_path)
    n_inner = len(inner_path)

    for i in range(n_outer):
        next_i = (i + 1) % n_outer
        # Outer ring
        all_faces.append([bottom_offset + i, bottom_offset + next_i, bottom_offset + n_outer + (i+1)%n_inner])
        all_faces.append([bottom_offset + i, bottom_offset + n_outer + (i+1)%n_inner, bottom_offset + n_outer + i])

    # Add mounting posts for Jetson
    jetson_posts = [
        (components.jetson_x - 50, components.jetson_y - 39.5),
        (components.jetson_x + 50, components.jetson_y - 39.5),
        (components.jetson_x - 50, components.jetson_y + 39.5),
        (components.jetson_x + 50, components.jetson_y + 39.5),
    ]
    post_verts, post_faces = create_mounting_posts(jetson_posts, post_diameter=3.5, post_height=5)
    offset = len(all_verts)
    for v in post_verts:
        all_verts.append(v)
    for f in post_faces:
        all_faces.append(f + offset)

    # Create mesh
    result_mesh = mesh.Mesh(np.zeros(len(all_faces), dtype=mesh.Mesh.dtype))
    for i, face in enumerate(all_faces):
        for j in range(3):
            result_mesh.vectors[i][j] = all_verts[face[j]]

    return result_mesh


def create_top_plate(dims: Dimensions, components: ComponentLocations) -> mesh.Mesh:
    """Create top plate with mic holes and small screen cutout."""

    # Top squircle shape
    top_path = create_squircle_2d(dims.width - 2*dims.wall_thickness,
                                  dims.depth - 2*dims.wall_thickness,
                                  dims.corner_radius - dims.wall_thickness, segments=64)

    # Extrude top plate (thin, ~3mm)
    plate_thickness = 3.0
    all_verts = []
    all_faces = []

    # Bottom surface of plate
    for pt in top_path:
        all_verts.append([pt[0], pt[1], dims.height - dims.wall_thickness])

    # Top surface of plate
    for pt in top_path:
        all_verts.append([pt[0], pt[1], dims.height - dims.wall_thickness + plate_thickness])

    n_points = len(top_path)

    # Side walls
    for i in range(n_points):
        next_i = (i + 1) % n_points
        all_faces.append([i, next_i, i + n_points])
        all_faces.append([next_i, next_i + n_points, i + n_points])

    # Mic holes (4 positions, ~3mm each)
    mic_holes = create_circular_holes(
        components.speaker_mic_x, components.speaker_mic_y,
        radius=20, hole_radius=2, num_holes=4, start_angle=math.pi/4
    )

    # Small screen cutout (1.3-2" OLED): 50x30mm
    screen_cutout_w = 50
    screen_cutout_h = 30
    screen_x = 0  # Center X
    screen_y = -30  # Offset back a bit

    # Add cylindrical holes for mics
    for mx, my, mr in mic_holes:
        mic_verts, mic_faces = create_cylinder_mesh(mr, plate_thickness,
                                                    z_offset=dims.height - dims.wall_thickness, segments=16)
        offset = len(all_verts)
        mic_verts[:, 0] += mx
        mic_verts[:, 1] += my
        for v in mic_verts:
            all_verts.append(v)
        for f in mic_faces:
            all_faces.append(f + offset)

    result_mesh = mesh.Mesh(np.zeros(len(all_faces), dtype=mesh.Mesh.dtype))
    for i, face in enumerate(all_faces):
        for j in range(3):
            result_mesh.vectors[i][j] = all_verts[face[j]]

    return result_mesh


def create_front_blank_panel(dims: Dimensions, components: ComponentLocations) -> mesh.Mesh:
    """Create blank front panel with speaker grille."""

    # Panel dimensions: spans width, mounted on front
    panel_width = dims.width - 2 * dims.wall_thickness
    panel_height = 40  # Height of panel
    panel_thickness = dims.wall_thickness

    all_verts = []
    all_faces = []

    # Create rectangular panel shape
    v0 = [-panel_width/2, -panel_height/2, 0]
    v1 = [panel_width/2, -panel_height/2, 0]
    v2 = [panel_width/2, panel_height/2, 0]
    v3 = [-panel_width/2, panel_height/2, 0]

    v4 = [-panel_width/2, -panel_height/2, panel_thickness]
    v5 = [panel_width/2, -panel_height/2, panel_thickness]
    v6 = [panel_width/2, panel_height/2, panel_thickness]
    v7 = [-panel_width/2, panel_height/2, panel_thickness]

    all_verts = [v0, v1, v2, v3, v4, v5, v6, v7]

    # Panel faces (front, back, sides)
    all_faces = [
        # Front
        [0, 1, 2], [0, 2, 3],
        # Back
        [4, 6, 5], [4, 7, 6],
        # Sides
        [0, 4, 5], [0, 5, 1],
        [1, 5, 6], [1, 6, 2],
        [2, 6, 7], [2, 7, 3],
        [3, 7, 4], [3, 4, 0],
    ]

    # Speaker grille holes (circular pattern, 50mm speaker)
    grille_x = components.speaker_center_x - dims.width/2
    grille_y = 0
    num_grille_holes = 12
    grille_outer_radius = 20
    grille_hole_radius = 2

    for i in range(num_grille_holes):
        angle = 2 * math.pi * i / num_grille_holes
        hx = grille_x + grille_outer_radius * math.cos(angle)
        hy = grille_y + grille_outer_radius * math.sin(angle)

        hole_verts, hole_faces = create_cylinder_mesh(grille_hole_radius, panel_thickness,
                                                      z_offset=0, segments=12)
        offset = len(all_verts)
        hole_verts[:, 0] += hx
        hole_verts[:, 1] += hy
        for v in hole_verts:
            all_verts.append(v)
        for f in hole_faces:
            all_faces.append(f + offset)

    # Add snap-fit tabs (2 tabs, top and bottom)
    tab_verts, tab_faces = create_snap_tabs(panel_width, num_tabs=2, z_height=0,
                                           tab_thickness=dims.snap_tab_thickness,
                                           tab_width=dims.snap_tab_width)
    offset = len(all_verts)
    for v in tab_verts:
        all_verts.append(v)
    for f in tab_faces:
        all_faces.append(f + offset)

    result_mesh = mesh.Mesh(np.zeros(len(all_faces), dtype=mesh.Mesh.dtype))
    for i, face in enumerate(all_faces):
        for j in range(3):
            result_mesh.vectors[i][j] = all_verts[face[j]]

    return result_mesh


def create_front_screen_panel(dims: Dimensions, screen_size: str = "5in") -> mesh.Mesh:
    """Create front panel with screen cutout (5" or 7")."""

    # Panel dimensions
    panel_width = dims.width - 2 * dims.wall_thickness
    panel_height = 40
    panel_thickness = dims.wall_thickness

    # Screen cutout dimensions (approximate active area + bezel)
    if screen_size == "5in":
        cutout_w = 121  # 5" active area
        cutout_h = 76
    else:  # 7in
        cutout_w = 170
        cutout_h = 105

    all_verts = []
    all_faces = []

    # Create rectangular panel
    v0 = [-panel_width/2, -panel_height/2, 0]
    v1 = [panel_width/2, -panel_height/2, 0]
    v2 = [panel_width/2, panel_height/2, 0]
    v3 = [-panel_width/2, panel_height/2, 0]

    v4 = [-panel_width/2, -panel_height/2, panel_thickness]
    v5 = [panel_width/2, -panel_height/2, panel_thickness]
    v6 = [panel_width/2, panel_height/2, panel_thickness]
    v7 = [-panel_width/2, panel_height/2, panel_thickness]

    all_verts = [v0, v1, v2, v3, v4, v5, v6, v7]

    # Panel faces
    all_faces = [
        [0, 1, 2], [0, 2, 3],
        [4, 6, 5], [4, 7, 6],
        [0, 4, 5], [0, 5, 1],
        [1, 5, 6], [1, 6, 2],
        [2, 6, 7], [2, 7, 3],
        [3, 7, 4], [3, 4, 0],
    ]

    # Screen cutout (rectangular hole in center)
    # Create a rectangular frame around the cutout
    cutout_x = 0
    cutout_y = 0
    cx0 = cutout_x - cutout_w/2
    cx1 = cutout_x + cutout_w/2
    cy0 = cutout_y - cutout_h/2
    cy1 = cutout_y + cutout_h/2

    # Inner rectangle vertices (lip around cutout)
    inner_lip = 3  # 3mm lip
    ix0 = cx0 + inner_lip
    ix1 = cx1 - inner_lip
    iy0 = cy0 + inner_lip
    iy1 = cy1 - inner_lip

    # Cutout edge vertices
    cutout_verts = [
        # Outer edge of cutout (on front face)
        [cx0, cy0, 0], [cx1, cy0, 0], [cx1, cy1, 0], [cx0, cy1, 0],
        # Inner lip (on back face, slightly inset)
        [ix0, iy0, panel_thickness], [ix1, iy0, panel_thickness],
        [ix1, iy1, panel_thickness], [ix0, iy1, panel_thickness],
    ]

    offset = len(all_verts)
    for v in cutout_verts:
        all_verts.append(v)

    # Add cutout faces (frame around the hole)
    base = offset
    all_faces.extend([
        # Front edge of frame
        [base, base+1, base+5], [base, base+5, base+4],
        [base+1, base+2, base+6], [base+1, base+6, base+5],
        [base+2, base+3, base+7], [base+2, base+7, base+6],
        [base+3, base, base+4], [base+3, base+4, base+7],
    ])

    # Screen mounting tabs (4 corners, M3 screw holes)
    tab_offset = 8
    tab_positions = [
        (cx0 + tab_offset, cy0 + tab_offset),
        (cx1 - tab_offset, cy0 + tab_offset),
        (cx1 - tab_offset, cy1 - tab_offset),
        (cx0 + tab_offset, cy1 - tab_offset),
    ]

    for tx, ty in tab_positions:
        # Small mounting tab (10x10mm, M3 hole)
        tab_hole_verts, tab_hole_faces = create_cylinder_mesh(1.5, panel_thickness,
                                                               z_offset=0, segments=12)
        offset = len(all_verts)
        tab_hole_verts[:, 0] += tx
        tab_hole_verts[:, 1] += ty
        for v in tab_hole_verts:
            all_verts.append(v)
        for f in tab_hole_faces:
            all_faces.append(f + offset)

    # Snap-fit tabs (same as blank panel)
    tab_verts, tab_faces = create_snap_tabs(panel_width, num_tabs=2, z_height=0,
                                           tab_thickness=dims.snap_tab_thickness,
                                           tab_width=dims.snap_tab_width)
    offset = len(all_verts)
    for v in tab_verts:
        all_verts.append(v)
    for f in tab_faces:
        all_faces.append(f + offset)

    result_mesh = mesh.Mesh(np.zeros(len(all_faces), dtype=mesh.Mesh.dtype))
    for i, face in enumerate(all_faces):
        for j in range(3):
            result_mesh.vectors[i][j] = all_verts[face[j]]

    return result_mesh


def create_speaker_grille(components: ComponentLocations) -> mesh.Mesh:
    """Create speaker grille insert (press-fit for blank panel)."""

    # Circular grille, 50mm speaker
    outer_radius = 26  # Slightly larger than speaker
    inner_radius = 20
    thickness = 2

    all_verts = []
    all_faces = []

    segments = 32

    # Outer ring (bottom)
    for i in range(segments):
        angle = 2 * math.pi * i / segments
        x = outer_radius * math.cos(angle)
        y = outer_radius * math.sin(angle)
        all_verts.append([x, y, 0])

    # Outer ring (top)
    for i in range(segments):
        angle = 2 * math.pi * i / segments
        x = outer_radius * math.cos(angle)
        y = outer_radius * math.sin(angle)
        all_verts.append([x, y, thickness])

    # Inner ring (bottom)
    for i in range(segments):
        angle = 2 * math.pi * i / segments
        x = inner_radius * math.cos(angle)
        y = inner_radius * math.sin(angle)
        all_verts.append([x, y, 0])

    # Inner ring (top)
    for i in range(segments):
        angle = 2 * math.pi * i / segments
        x = inner_radius * math.cos(angle)
        y = inner_radius * math.sin(angle)
        all_verts.append([x, y, thickness])

    # Outer wall
    for i in range(segments):
        next_i = (i + 1) % segments
        all_faces.append([i, next_i, i + segments])
        all_faces.append([next_i, next_i + segments, i + segments])

    # Inner wall (reversed)
    for i in range(segments):
        next_i = (i + 1) % segments
        all_faces.append([i + 2*segments, i + 3*segments, next_i + 2*segments])
        all_faces.append([i + 3*segments, next_i + 3*segments, next_i + 2*segments])

    # Top surface (radial bars for grille pattern)
    num_bars = 12
    for bar_idx in range(num_bars):
        angle = 2 * math.pi * bar_idx / num_bars

        # Bar from inner to outer radius
        bar_width = 1.5

        # Create bar as thin rectangle
        x1 = inner_radius * math.cos(angle)
        y1 = inner_radius * math.sin(angle)
        x2 = outer_radius * math.cos(angle)
        y2 = outer_radius * math.sin(angle)

        # Perpendicular direction for width
        angle_perp = angle + math.pi / 2
        dx = bar_width/2 * math.cos(angle_perp)
        dy = bar_width/2 * math.sin(angle_perp)

        # Four corners of bar
        v0 = [x1 + dx, y1 + dy, thickness]
        v1 = [x1 - dx, y1 - dy, thickness]
        v2 = [x2 - dx, y2 - dy, thickness]
        v3 = [x2 + dx, y2 + dy, thickness]

        offset = len(all_verts)
        all_verts.extend([v0, v1, v2, v3])
        all_faces.append([offset, offset+1, offset+2])
        all_faces.append([offset, offset+2, offset+3])

    result_mesh = mesh.Mesh(np.zeros(len(all_faces), dtype=mesh.Mesh.dtype))
    for i, face in enumerate(all_faces):
        for j in range(3):
            result_mesh.vectors[i][j] = all_verts[face[j]]

    return result_mesh


def get_mesh_bounds(m: mesh.Mesh) -> Tuple[float, float, float, float, float, float]:
    """Get min/max bounds of mesh."""
    min_x = min_y = min_z = float('inf')
    max_x = max_y = max_z = float('-inf')

    for vector in m.vectors:
        for vertex in vector:
            min_x = min(min_x, vertex[0])
            max_x = max(max_x, vertex[0])
            min_y = min(min_y, vertex[1])
            max_y = max(max_y, vertex[1])
            min_z = min(min_z, vertex[2])
            max_z = max(max_z, vertex[2])

    return min_x, max_x, min_y, max_y, min_z, max_z


def main():
    """Generate all enclosure components."""

    dims = Dimensions()
    components = ComponentLocations()

    output_dir = "/sessions/festive-jolly-turing/mnt/project-gulmugli/jarvis/05-the-body/designs/stl"

    print("=" * 70)
    print("JARVIS Enclosure Generator")
    print("=" * 70)
    print(f"Output directory: {output_dir}\n")

    # Create meshes
    components_to_generate = [
        ("jarvis-base.stl", create_base_shell(dims, components), "Main body shell"),
        ("jarvis-top.stl", create_top_plate(dims, components), "Top plate with mic holes"),
        ("jarvis-front-blank.stl", create_front_blank_panel(dims, components), "Blank front panel"),
        ("jarvis-front-screen-5in.stl", create_front_screen_panel(dims, "5in"), "5\" screen front panel"),
        ("jarvis-front-screen-7in.stl", create_front_screen_panel(dims, "7in"), "7\" screen front panel"),
        ("jarvis-grille.stl", create_speaker_grille(components), "Speaker grille insert"),
    ]

    print("Generating components:\n")

    for filename, m, description in components_to_generate:
        filepath = os.path.join(output_dir, filename)
        m.save(filepath)

        # Get file size
        file_size = os.path.getsize(filepath)
        file_size_kb = file_size / 1024

        # Get mesh bounds
        min_x, max_x, min_y, max_y, min_z, max_z = get_mesh_bounds(m)
        width = max_x - min_x
        depth = max_y - min_y
        height = max_z - min_z

        print(f"✓ {filename}")
        print(f"  Description: {description}")
        print(f"  Dimensions: {width:.1f} × {depth:.1f} × {height:.1f} mm")
        print(f"  File size: {file_size_kb:.1f} KB ({file_size} bytes)")
        print(f"  Vertices: {len(m.vectors) * 3}")
        print()

    print("=" * 70)
    print("✓ All components generated successfully!")
    print("=" * 70)


if __name__ == "__main__":
    main()
