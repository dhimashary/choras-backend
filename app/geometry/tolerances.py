"""Tolerance bundle attached to a SimulationProfile."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Tolerances:
    vertex_merge: float = 1e-2
    conformize: float = 1e-7
    planarity_warn_m: float = 1e-4
    planarity_fatal_m: float = 1e-3
    degenerate_area: float = 1e-18
    intersection_eps: float = 1e-10
    bbox_pad: float = 1e-9
    max_reports: int = 200
