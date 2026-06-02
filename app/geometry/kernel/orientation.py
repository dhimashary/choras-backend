"""Face orientation primitives."""
from __future__ import annotations

from app.geometry.ir import Face, Mesh, Vertex


def face_normal(mesh: Mesh, face: Face) -> Vertex:
    raise NotImplementedError


def is_outward_facing(mesh: Mesh, face: Face, room_center: Vertex) -> bool:
    raise NotImplementedError
