#!/usr/bin/env python3
"""
mesh_union.py — convert a list of generator primitives into a single
watertight manifold STL via real CSG (manifold3d backend).

## Why this exists

The v3/v4/v4-solid generator helpers `box()` / `cyl_z()` / `cyl_y()`
emit primitives with **inward-pointing face normals** (a long-standing
winding bug — the docstrings claim CCW-from-outside but the index
arrays produce CW-from-outside). On top of that, `merge()` just
concatenates triangle lists without doing any boolean union.

PrusaSlicer 2.x silently auto-fixes both problems at slice time:
it computes face normals from solid orientation and unions overlapping
geometry. **Bambu Studio refuses both fixes** and shows the result as
N disconnected, inward-facing bodies — which renders in the slicer as
multiple separate parts with visible gaps. That's exactly what the
print shop reported.

## The fix

This module fixes both problems in the mesh layer, so the exported
STL is a single watertight closed solid that *every* slicer accepts:

  1. Flip the winding of every primitive (so normals point outward).
  2. Build a manifold3d Manifold from each (now-valid) primitive.
  3. Boolean-union them all.
  4. Export back as a trimesh.Trimesh.

Manifold3d's CSG kernel handles the abutting / face-coincident /
overlapping-volume cases correctly *as long as each input is a valid
closed solid with outward normals* — which is exactly what step 1
guarantees.

## Usage

Simple union (legacy, all positive geometry):

  pieces = build_frame_meshes(...)                   # generator output
  mesh   = pieces_to_watertight_mesh(pieces)          # one closed solid
  mesh.export("frame.stl")

Union + subtract (new, for face-with-cutouts geometry):

  positives = [box(W, H, t), ...standoffs..., ...feet...]
  negatives = [box(slit_w, slit_h, slit_d, ...), ...]   # cutouts
  mesh = pieces_to_watertight_mesh(positives, negatives)

The CSG difference correctly produces a single watertight body even
when slit-shaped cutouts would otherwise split the geometry into
disconnected strips (the original bug).

## Dependencies

    pip install trimesh manifold3d numpy
"""
from __future__ import annotations

from typing import List, Tuple

import numpy as np
import trimesh
import manifold3d as m3d


def _flip_winding(faces: np.ndarray) -> np.ndarray:
    """Reverse the vertex order of every triangle (flip outward → inward
    or vice versa)."""
    return faces[:, [0, 2, 1]]


def _piece_to_outward_manifold(
    verts: np.ndarray, faces: np.ndarray
) -> m3d.Manifold:
    """Build a manifold3d solid from a primitive piece, ensuring its
    normals point OUTWARD (positive volume).

    The v3 generator's box/cyl helpers produce inward-facing windings;
    we flip every piece's faces to fix that. If for some reason the
    piece is already correctly oriented, the flip will produce a
    negative-volume manifold and we'll flip back.
    """
    v = np.ascontiguousarray(verts, dtype=np.float32)
    # First try: flip generator's winding
    f_flipped = np.ascontiguousarray(_flip_winding(faces), dtype=np.uint32)
    mgl = m3d.Mesh(vert_properties=v, tri_verts=f_flipped)
    man = m3d.Manifold(mgl)

    if man.volume() < 0:
        # Was already correct — flip back.
        f = np.ascontiguousarray(faces, dtype=np.uint32)
        mgl = m3d.Mesh(vert_properties=v, tri_verts=f)
        man = m3d.Manifold(mgl)

    return man


def _pieces_to_manifolds(
    pieces: List[Tuple[np.ndarray, np.ndarray]],
) -> List[m3d.Manifold]:
    """Convert a list of primitive (verts, faces) pieces into a list of
    properly-oriented Manifold solids, skipping zero-volume entries."""
    out: List[m3d.Manifold] = []
    for v, f in pieces:
        bb = np.ptp(np.asarray(v), axis=0)
        if (bb < 1e-6).any():
            continue
        try:
            man = _piece_to_outward_manifold(v, f)
            if man.volume() > 0:
                out.append(man)
        except RuntimeError:
            continue
    return out


def pieces_to_watertight_mesh(
    pieces: List[Tuple[np.ndarray, np.ndarray]],
    negatives: List[Tuple[np.ndarray, np.ndarray]] | None = None,
    snap_digits: int = 4,
) -> trimesh.Trimesh:
    """
    Boolean-union a list of positive primitives, optionally subtract a
    list of negative primitives (cutouts), and return one watertight
    single-body mesh.

    Each entry in `pieces` and `negatives` must be (verts, faces) — a
    closed primitive solid, as produced by the generator's `box(...)`
    / `cyl_*(...)` helpers.

    The subtractive path is the correct way to model "face with
    rectangular slits" or "face with circular cutout" — the prior
    "decompose into strips around the cutout" approach produced
    face-coincident geometry that manifold3d treats as separate
    bodies. Use positive-then-negate instead.
    """
    if not pieces:
        raise ValueError("pieces is empty")

    # 1. Build oriented manifolds for positives and negatives.
    pos = _pieces_to_manifolds(pieces)
    if not pos:
        raise RuntimeError("no valid positive primitives")
    neg = _pieces_to_manifolds(negatives or [])

    # 2. Union positives.
    union = pos[0]
    for m in pos[1:]:
        union = union + m

    # 3. Subtract negatives.
    for m in neg:
        union = union - m

    # 4. Convert back to trimesh, snap-and-merge to absorb float32→64
    # rounding artifacts, fix winding for sanity.
    out = union.to_mesh()
    verts = np.asarray(out.vert_properties[:, :3], dtype=np.float64)
    verts = np.round(verts, snap_digits)

    mesh = trimesh.Trimesh(
        vertices=verts,
        faces=np.asarray(out.tri_verts, dtype=np.int64),
        process=False,
    )
    mesh.merge_vertices(digits_vertex=snap_digits)
    mesh.update_faces(mesh.unique_faces())
    mesh.remove_unreferenced_vertices()
    mesh.fix_normals()
    return mesh
