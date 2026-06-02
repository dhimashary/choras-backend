"""Gmsh `.geo` exporter — writes a `Mesh` IR via the legacy export helper."""
from __future__ import annotations

from pathlib import Path

from app.geometry.ir import Mesh
from app.geometry.kernel import mesh_to_legacy
from app.services.geometry_export_service import (
    export_processed_topology_to_gmsh_geo,
)


class GmshGeoExporter:
    def __init__(self, volume_name: str = "RoomVolume") -> None:
        self.volume_name = volume_name

    def write(self, geom: Mesh, path: Path) -> None:
        faces, points = mesh_to_legacy(geom)
        export_processed_topology_to_gmsh_geo(
            faces, points, str(path), volume_name=self.volume_name,
        )

