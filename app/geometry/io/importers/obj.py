"""OBJ importer -> Mesh."""
from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from app.geometry.ir import Mesh


class ObjImporter:
    extensions: ClassVar[tuple[str, ...]] = (".obj",)

    def load(self, path: Path) -> Mesh:
        raise NotImplementedError
