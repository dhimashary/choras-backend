"""OBJ exporter (for processed/repaired meshes)."""
from __future__ import annotations

from pathlib import Path

from app.geometry.ir import Mesh


class ObjExporter:
    def write(self, geom: Mesh, path: Path) -> None:
        raise NotImplementedError
