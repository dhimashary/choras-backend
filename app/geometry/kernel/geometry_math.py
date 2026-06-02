"""Vector / polygon math primitives.

Re-exported from `app.utils.geometry_utils` — see that module for
implementations. Names are kept identical so search tools find both
locations until the implementations physically move (PR2/PR3).

`uedge` is renamed from the legacy `_uedge` (private). The leading
underscore was an accident of single-module life; in the kernel API
it is public.
"""
from __future__ import annotations

from app.utils.geometry_utils import (
    _uedge as uedge,
    area2,
    cross,
    dot,
    newell_normal_from_points,
    orient,
    sub,
)

__all__ = [
    "area2",
    "cross",
    "dot",
    "newell_normal_from_points",
    "orient",
    "sub",
    "uedge",
]
