"""Integration test: GmshGeoExporter with auto-cavity-detection.

Modules are loaded directly from source paths so we bypass `app/__init__.py`
(which boots the full Flask app and is not test-safe in this environment).
"""
from __future__ import annotations

import importlib.util
import sys
import types
from dataclasses import dataclass
from pathlib import Path

import pytest

pytest.importorskip("trimesh")
pytest.importorskip("scipy")
pytest.importorskip("shapely")

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load(module_name: str, rel_path: str):
    spec = importlib.util.spec_from_file_location(module_name, str(REPO_ROOT / rel_path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


# Bypass the real `app` package initialization
for pkg in ("app", "app.utils", "app.geometry", "app.geometry.kernel",
            "app.geometry.io", "app.geometry.io.exporters", "app.services"):
    if pkg not in sys.modules or not getattr(sys.modules[pkg], "__path__", None):
        m = types.ModuleType(pkg)
        m.__path__ = []
        sys.modules[pkg] = m


@dataclass
class StubFaceRecord:
    fid: int
    verts: list
    group: str = "default"
    group_material: str = "default_group_material"
    material: str = "unknown"


def _uedge(u, v):
    return (u, v) if u < v else (v, u)


stub_geom_utils = types.ModuleType("app.utils.geometry_utils")
stub_geom_utils.FaceRecord = StubFaceRecord
stub_geom_utils._uedge = _uedge
sys.modules["app.utils.geometry_utils"] = stub_geom_utils


ir = _load("app.geometry.ir", "app/geometry/ir.py")
data_types = _load("app.geometry.kernel.data_types", "app/geometry/kernel/data_types.py")

# Expose mesh_to_legacy on the kernel package (real __init__ pulls in too much)
kernel_pkg = sys.modules["app.geometry.kernel"]
kernel_pkg.mesh_to_legacy = data_types.mesh_to_legacy

geom_export = _load("app.services.geometry_export_service", "app/services/geometry_export_service.py")
cavity_detector = _load("app.geometry.cavity_detector", "app/geometry/cavity_detector.py")
geo_exporter_mod = _load("app.geometry.io.exporters.geo", "app/geometry/io/exporters/geo.py")

GmshGeoExporter = geo_exporter_mod.GmshGeoExporter
Mesh = ir.Mesh
Face = ir.Face
Vertex = ir.Vertex


def _cube(origin, size, vid_offset=0):
    ox, oy, oz = origin
    sx, sy, sz = size
    pts = [
        Vertex(ox,        oy,        oz),
        Vertex(ox + sx,   oy,        oz),
        Vertex(ox + sx,   oy + sy,   oz),
        Vertex(ox,        oy + sy,   oz),
        Vertex(ox,        oy,        oz + sz),
        Vertex(ox + sx,   oy,        oz + sz),
        Vertex(ox + sx,   oy + sy,   oz + sz),
        Vertex(ox,        oy + sy,   oz + sz),
    ]
    quads = [
        [0, 3, 2, 1],
        [4, 5, 6, 7],
        [0, 1, 5, 4],
        [2, 3, 7, 6],
        [1, 2, 6, 5],
        [3, 0, 4, 7],
    ]
    faces = [
        Face(
            vertex_indices=[v + 1 + vid_offset for v in q],
            group="g",
            material="mat",
        )
        for q in quads
    ]
    return pts, faces


def test_exporter_emits_multiple_volumes_when_detection_enabled(tmp_path: Path):
    outer_pts, outer_faces = _cube((0, 0, 0), (2, 2, 2), vid_offset=0)
    inner_pts, inner_faces = _cube(
        (0.7, 0.7, 0.7), (0.5, 0.5, 0.5), vid_offset=len(outer_pts)
    )
    mesh = Mesh(vertices=outer_pts + inner_pts, faces=outer_faces + inner_faces)

    geo_path = tmp_path / "out.geo"
    GmshGeoExporter(
        detect_cavities=True, detection_mode="voxel", cavity_pitch=0.05
    ).write(mesh, geo_path)
    text = geo_path.read_text()

    assert "Volume(1) = { 1 };" in text
    assert "Volume(2) = { 2 };" in text
    assert 'Physical Volume("Room")' in text
    assert 'Physical Volume("Cavity_2")' in text
    assert "Surface Loop(1)" in text
    assert "Surface Loop(2)" in text


def test_exporter_falls_back_to_single_volume_when_detection_disabled(tmp_path: Path):
    pts, faces = _cube((0, 0, 0), (1, 1, 1))
    mesh = Mesh(vertices=pts, faces=faces)

    geo_path = tmp_path / "out.geo"
    GmshGeoExporter(volume_name="LegacyRoom", detect_cavities=False).write(mesh, geo_path)
    text = geo_path.read_text()

    assert "Volume(1) = { 1 };" in text
    assert "Volume(2)" not in text
    assert 'Physical Volume("LegacyRoom") = { 1 };' in text
