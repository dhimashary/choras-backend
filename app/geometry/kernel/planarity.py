"""Planarity primitives (no Issue, no Context — pure math)."""
from __future__ import annotations

from app.geometry.ir import Face, Mesh, Vertex


def face_plane(mesh: Mesh, face: Face) -> tuple[Vertex, Vertex]:
    """Return (centroid, unit_normal) for a face."""
    raise NotImplementedError


def planarity_deviation(mesh: Mesh, face: Face) -> float:
    """Return max distance from any face vertex to its best-fit plane."""
    raise NotImplementedError
