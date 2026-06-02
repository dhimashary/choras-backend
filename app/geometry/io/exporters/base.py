"""Exporter Protocol: Geometry IR -> file."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from app.geometry.ir import Geometry


class Exporter(Protocol):
    def write(self, geom: Geometry, path: Path) -> None: ...
