"""Edge / half-edge utilities shared by validators and repairs."""
from __future__ import annotations

from app.geometry.ir import Mesh


def build_unique_edges(mesh: Mesh) -> dict:
    """Return a mapping (min,max)-vertex-pair -> edge id."""
    raise NotImplementedError


def edge_face_map(mesh: Mesh) -> dict:
    """Return edge -> list of face indices that reference it."""
    raise NotImplementedError


def half_edges(mesh: Mesh) -> list:
    raise NotImplementedError
