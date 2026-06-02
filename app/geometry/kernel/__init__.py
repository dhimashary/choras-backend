"""Pure-geometry primitives shared by validators and repairs.

PR1 strategy: this sub-package is a curated re-export of the helpers that
already live in `app.utils.geometry_utils` and `app.utils.geometry_validation_utils`.
Behaviour is identical to today; only the import path is new.

Later PRs may move the implementations physically into this folder; doing
the rename here keeps PR1 a structural-only change.

Rule: nothing in `kernel/` imports from `app.models`, `app.db`, `flask*`,
or any `app.geometry.{validators,repairs,profiles}` module.
"""
from app.geometry.kernel.data_types import FaceRecord, mesh_from_legacy, mesh_to_legacy
from app.geometry.kernel.geometry_math import (
    area2,
    cross,
    dot,
    newell_normal_from_points,
    orient,
    sub,
    uedge,
)
from app.geometry.kernel.triangulation import triangulate_face_cdt_shapely
from app.geometry.kernel.validation import (
    classify_face_degeneracy,
    classify_face_planarity_m,
    planarity_deviation_m,
)

__all__ = [
    # data_types
    "FaceRecord",
    "mesh_from_legacy",
    "mesh_to_legacy",
    # geometry_math
    "area2",
    "cross",
    "dot",
    "newell_normal_from_points",
    "orient",
    "sub",
    "uedge",
    # triangulation
    "triangulate_face_cdt_shapely",
    # validation
    "classify_face_degeneracy",
    "classify_face_planarity_m",
    "planarity_deviation_m",
]
