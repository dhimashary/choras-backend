"""Unit tests for the native volume-detector bridge.

These tests do NOT require the compiled C++ binary or CGAL. They validate the
pure-Python pieces of the bridge: mesh-IR JSON serialization and
JSON -> Cavity parsing. Heavy optional dependencies (shapely via
app.utils.geometry_utils) are stubbed.
"""
import importlib.util
import json
import sys
from dataclasses import dataclass
from types import ModuleType
from pathlib import Path


def load_module_from_repo(module_name: str, rel_path: str):
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / rel_path
    spec = importlib.util.spec_from_file_location(module_name, str(module_path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


# --- Stub heavy deps so we never import shapely / the app package ------------
stub_geom = ModuleType("app.utils.geometry_utils")


@dataclass
class StubFaceRecord:
    fid: int
    verts: list
    group: str = "default"
    group_material: str = "default_group_material"
    material: str = "unknown"


def _uedge(u, v):
    return (u, v) if u < v else (v, u)


stub_geom.FaceRecord = StubFaceRecord
stub_geom._uedge = _uedge
sys.modules["app.utils.geometry_utils"] = stub_geom

# Register the real geometry_export_service (provides Cavity) under its dotted
# name so the bridge's `from app.services... import Cavity` resolves without
# triggering app/__init__.py.
geometry_export = load_module_from_repo(
    "app.services.geometry_export_service",
    "app/services/geometry_export_service.py",
)
Cavity = geometry_export.Cavity

bridge = load_module_from_repo(
    "app.geometry.volume_detector_bridge",
    "app/geometry/volume_detector_bridge.py",
)
FaceRecord = stub_geom.FaceRecord


def test_write_mesh_json_face_order_matches_face_index(tmp_path):
    verts = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)]
    faces = [
        FaceRecord(fid=0, verts=[1, 2, 3]),
        FaceRecord(fid=1, verts=[1, 3, 4]),
    ]
    json_path = tmp_path / "mesh.json"
    bridge._write_mesh_json(faces, verts, json_path)

    payload = json.loads(json_path.read_text())

    assert len(payload["vertices"]) == 4
    assert payload["vertices"][1] == [1.0, 0.0, 0.0]
    # 1-based FaceRecord.verts -> 0-based JSON indices, face order preserved
    # so C++ face_id == Python face index.
    assert payload["faces"] == [[0, 1, 2], [0, 2, 3]]


def test_cavities_from_json_maps_faces_and_signs():
    payload = {
        "bounded_volume_count": 1,
        "volumes": [
            {
                "volume_id": 0,
                "is_manifold": True,
                "faces": [
                    {"face_id": 0, "sign": -1},
                    {"face_id": 1, "sign": 1},
                    {"face_id": 2, "sign": 1},
                ],
            }
        ],
    }
    cavities = bridge._cavities_from_json(payload)
    assert len(cavities) == 1
    cav = cavities[0]
    assert isinstance(cav, Cavity)
    assert cav.oriented_faces == [(0, -1), (1, 1), (2, 1)]


def test_cavities_from_json_skips_empty_volumes():
    payload = {"volumes": [{"volume_id": 3, "faces": []}]}
    assert bridge._cavities_from_json(payload) == []


def test_cavities_from_json_handles_multiple_volumes():
    payload = {
        "volumes": [
            {"volume_id": 0, "faces": [{"face_id": 0, "sign": 1}]},
            {"volume_id": 1, "faces": [{"face_id": 1, "sign": -1}]},
        ]
    }
    cavities = bridge._cavities_from_json(payload)
    assert [c.id for c in cavities] == [0, 1]
    assert cavities[1].oriented_faces == [(1, -1)]
