"""Topology-level queries on a mesh."""
from __future__ import annotations

from app.geometry.ir import Mesh


def boundary_edges(mesh: Mesh) -> list[tuple[int, int]]:
    """Edges referenced by exactly one face."""
    raise NotImplementedError


def is_manifold(mesh: Mesh) -> bool:
    raise NotImplementedError
