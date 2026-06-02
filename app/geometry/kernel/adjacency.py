"""Face/vertex adjacency utilities."""
from __future__ import annotations

from app.geometry.ir import Mesh


def face_neighbors(mesh: Mesh) -> dict[int, list[int]]:
    raise NotImplementedError


def connected_components(mesh: Mesh) -> list[list[int]]:
    raise NotImplementedError
