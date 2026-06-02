"""OBJ exporter — writes a `Mesh` IR via the legacy export helper."""
from __future__ import annotations

from pathlib import Path

from app.geometry.ir import Mesh
from app.geometry.kernel import mesh_to_legacy
from app.services.geometry_export_service import (
    export_processed_topology_to_obj,
)


class ObjExporter:
    def path_for(self, base_path: Path) -> Path:
        """Mirror legacy convention: write `<stem>_repaired.obj` next to the .geo."""
        base_path = Path(base_path)
        return base_path.with_name(base_path.stem + "_repaired.obj")

    def write(self, geom: Mesh, path: Path) -> None:
        faces, points = mesh_to_legacy(geom)
        export_processed_topology_to_obj(str(path), points, faces)

