import importlib.util
import sys
import tempfile
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


# Provide a lightweight stub of `app.utils.geometry_utils` to avoid importing
# heavy optional dependencies (shapely) during test collection.
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

# Now load the geometry_export_service module (it will import the stub above)
geometry_export = load_module_from_repo("app.services.geometry_export_service", "app/services/geometry_export_service.py")

FaceRecord = stub_geom.FaceRecord
export_processed_topology_to_gmsh_geo = geometry_export.export_processed_topology_to_gmsh_geo
Cavity = geometry_export.Cavity


def test_export_multiple_cavities_creates_surface_loops_and_physical_volumes():
    # Simple vertex set (1-based indices used in FaceRecord)
    unique_vertices = [
        (0.0, 0.0, 0.0),  # 1
        (1.0, 0.0, 0.0),  # 2
        (0.0, 1.0, 0.0),  # 3
        (0.0, 0.0, 1.0),  # 4
    ]

    # Two triangular faces
    f0 = FaceRecord(fid=0, verts=[1, 2, 3], group="g", group_material="m", material="mat")
    f1 = FaceRecord(fid=1, verts=[1, 3, 4], group="g", group_material="m", material="mat")
    faces = [f0, f1]

    # Create two cavities: one for face 0, one for face 1
    cav0 = Cavity(id=1, name="CavA", volume=1.0, oriented_faces=[(0, 1)])
    cav1 = Cavity(id=2, name="CavB", volume=2.0, oriented_faces=[(1, 1)])

    with tempfile.TemporaryDirectory() as td:
        geo_path = Path(td) / "out.geo"
        export_processed_topology_to_gmsh_geo(faces, unique_vertices, str(geo_path), volume_name="Room", cavities=[cav0, cav1])

        text = geo_path.read_text()

        # Expect plane surfaces for two faces
        assert "Plane Surface(1)" in text
        assert "Plane Surface(2)" in text

        # Expect two surface loops and two volumes/physical volumes
        assert "Surface Loop(1)" in text
        assert "Surface Loop(2)" in text
        assert "Volume(1) = { 1 };" in text
        assert "Volume(2) = { 2 };" in text
        assert 'Physical Volume("CavA") = { 1 };' in text
        assert 'Physical Volume("CavB") = { 2 };' in text
