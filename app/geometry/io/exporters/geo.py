"""Gmsh .geo exporter."""
from __future__ import annotations

from pathlib import Path

from app.geometry.ir import Mesh


class GmshGeoExporter:
    def __init__(self, volume_name: str = "RoomVolume") -> None:
        self.volume_name = volume_name

    def write(self, geom: Mesh, path: Path) -> None:
        raise NotImplementedError
