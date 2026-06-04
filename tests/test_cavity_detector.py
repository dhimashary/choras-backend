"""Unit test for the voxel-based cavity detector.

Builds:
  - One large outer closed cube (the "room").
  - One small closed cube fully inside the large cube (a "drawer").

Expects the detector to find two cavities: the room (between outer & inner
shells) and the drawer interior.
"""
from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

import pytest

# ---- Shared stub loader (mirrors test_geo_exporter_cavities.py) -------------

def _load_module(module_name: str, rel_path: str):
    repo_root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(module_name, str(repo_root / rel_path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


@dataclass
class StubFaceRecord:
    fid: int
    verts: list
    group: str = "default"
    group_material: str = "default_group_material"
    material: str = "unknown"


def _uedge(u, v):
    return (u, v) if u < v else (v, u)


# Stub heavy app.utils.geometry_utils (avoids shapely import during tests)
stub_geom = ModuleType("app.utils.geometry_utils")
stub_geom.FaceRecord = StubFaceRecord
stub_geom._uedge = _uedge
sys.modules["app.utils.geometry_utils"] = stub_geom

# Load geometry_export_service (provides Cavity); cavity_detector imports from it.
_geom_export = _load_module("app.services.geometry_export_service", "app/services/geometry_export_service.py")

# Skip cleanly if optional voxel deps are missing
trimesh = pytest.importorskip("trimesh")
scipy = pytest.importorskip("scipy")

_cavity_detector = _load_module("app.geometry.cavity_detector", "app/geometry/cavity_detector.py")
detect_cavities = _cavity_detector.detect_cavities
Cavity = _geom_export.Cavity


# ---- Helpers ----------------------------------------------------------------

def _cube_faces_and_verts(origin, size, fid_start=0, vid_offset=0):
    """Return (faces, verts) for an axis-aligned cube with outward normals.

    verts: 8 (x,y,z) tuples, faces: 6 quads (1-based vertex ids in `verts`,
    offset by `vid_offset` so they remain unique when concatenated).
    """
    ox, oy, oz = origin
    sx, sy, sz = size
    p = [
        (ox,        oy,        oz),         # 0
        (ox + sx,   oy,        oz),         # 1
        (ox + sx,   oy + sy,   oz),         # 2
        (ox,        oy + sy,   oz),         # 3
        (ox,        oy,        oz + sz),    # 4
        (ox + sx,   oy,        oz + sz),    # 5
        (ox + sx,   oy + sy,   oz + sz),    # 6
        (ox,        oy + sy,   oz + sz),    # 7
    ]
    # quads with outward-CCW winding when viewed from outside
    quads = [
        [0, 3, 2, 1],   # bottom (-z), normal -z
        [4, 5, 6, 7],   # top    (+z), normal +z
        [0, 1, 5, 4],   # front  (-y)
        [2, 3, 7, 6],   # back   (+y)
        [1, 2, 6, 5],   # right  (+x)
        [3, 0, 4, 7],   # left   (-x)
    ]
    faces = [
        StubFaceRecord(
            fid=fid_start + i,
            verts=[v + 1 + vid_offset for v in q],
        )
        for i, q in enumerate(quads)
    ]
    return faces, p


# ---- Tests ------------------------------------------------------------------

def test_single_cube_detects_one_cavity():
    faces, verts = _cube_faces_and_verts((0, 0, 0), (1, 1, 1))
    cavities = detect_cavities(faces, verts, pitch=0.1)

    assert len(cavities) == 1, f"expected 1 cavity, got {len(cavities)}"
    cav = cavities[0]
    assert cav.name == "Room"
    # All 6 faces should be assigned
    assigned = {fi for fi, _ in cav.oriented_faces}
    assert assigned == set(range(6))
    # Volume ~ 1.0 (within voxelization tolerance)
    assert 0.5 < cav.volume < 1.2


def test_nested_cubes_detect_two_cavities():
    # Outer cube
    outer_faces, outer_verts = _cube_faces_and_verts(
        (0, 0, 0), (2, 2, 2),
        fid_start=0, vid_offset=0,
    )
    # Inner cube fully inside
    inner_faces, inner_verts = _cube_faces_and_verts(
        (0.7, 0.7, 0.7), (0.5, 0.5, 0.5),
        fid_start=len(outer_faces), vid_offset=len(outer_verts),
    )

    faces = list(outer_faces) + list(inner_faces)
    verts = list(outer_verts) + list(inner_verts)

    cavities = detect_cavities(faces, verts, pitch=0.05)

    assert len(cavities) == 2, f"expected 2 cavities, got {len(cavities)}"
    room, drawer = cavities[0], cavities[1]
    assert room.name == "Room"
    assert room.volume > drawer.volume

    # Outer 6 faces should bound Room; inner 6 faces should bound Drawer
    room_face_set = {fi for fi, _ in room.oriented_faces}
    drawer_face_set = {fi for fi, _ in drawer.oriented_faces}
    outer_idx = set(range(6))
    inner_idx = set(range(6, 12))
    assert outer_idx.issubset(room_face_set)
    assert inner_idx.issubset(drawer_face_set)

    # Drawer volume ≈ 0.125 (0.5^3); Room volume ≈ 8 - 0.125 ≈ 7.875
    assert 0.05 < drawer.volume < 0.25
    assert 6.5 < room.volume < 8.5
