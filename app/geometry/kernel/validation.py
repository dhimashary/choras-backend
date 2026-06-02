"""Face classification helpers (degeneracy, planarity).

Re-exported from `app.utils.geometry_validation_utils`.
"""
from app.utils.geometry_validation_utils import (
    classify_face_degeneracy,
    classify_face_planarity_m,
    planarity_deviation_m,
)

__all__ = [
    "classify_face_degeneracy",
    "classify_face_planarity_m",
    "planarity_deviation_m",
]
