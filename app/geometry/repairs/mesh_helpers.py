"""Mesh-level helpers used by repairs.

Keep this module IR-aware but framework-agnostic: pure functions that
take a `Mesh` and return primitive values. Anything coupling to legacy
`(faces, points)` shims belongs in the individual repair modules.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.geometry.ir import Mesh


def room_center_from_mesh(mesh: "Mesh") -> tuple[float, float, float]:
    """Mean of mesh vertices (matches legacy ``room_center`` formula).

    Several PLC repairs ('which side of the plane do we keep?') need a
    reference point inside the room. Computed from the current vertices
    so it stays in sync after dedup / sort / split repairs.
    """
    if not mesh.vertices:
        return (0.0, 0.0, 0.0)

    n = len(mesh.vertices)
    cx = sum(v.x for v in mesh.vertices) / n
    cy = sum(v.y for v in mesh.vertices) / n
    cz = sum(v.z for v in mesh.vertices) / n
    return (cx, cy, cz)


__all__ = ["room_center_from_mesh"]
