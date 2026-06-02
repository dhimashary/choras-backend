"""Canonical tolerance bundle attached to a SimulationProfile.

Values reconcile inconsistencies found in the legacy code; see
docs/architecture/migration-plan.md §2 for the audit table.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Tolerances:
    # ---- Length tolerances (metres)
    vertex_merge: float = 1e-2          # merge coincident vertices
    planarity_warn_m: float = 1e-4      # face planarity, warn-level
    planarity_fatal_m: float = 1e-3     # face planarity, fatal-level
    planarity_split: float = 1e-6       # planarity allowed during repair-time face splits
    t_junction: float = 1e-2            # vertex-on-edge interior tolerance
                                        # (matches legacy `conformize_tol = max(1e-7, tol)` with tol=1e-2)
    clipping: float = 1e-9              # plane clipping & vertex reuse
    intersection_eps: float = 1e-10     # Möller–Trumbore segment-triangle eps
    bbox_pad: float = 1e-9              # AABB overlap padding
    plc_offset: float = 0.01            # endpoint offset for PLC workaround
                                        # (absolute; assumes room scale ≥ 1 m)
    small_face_max_dim: float = 0.10    # flag faces whose bbox max-dim < this (10 cm)

    # ---- Area tolerances (m²)
    degenerate_area: float = 1e-12      # canonical "this face has no area"

    # ---- Iteration caps
    max_t_junction_iters: int = 100
    max_plc_iters: int = 20
    max_edge_split_passes: int = 10

    # ---- Reporting caps
    max_reports: int = 2000
