"""Validator: detects faces whose vertices deviate from a best-fit plane."""
from __future__ import annotations

from typing import ClassVar

from app.geometry.context import Context
from app.geometry.ir import Mesh
from app.geometry.issues import DetectionStage, Issue, IssueKind
from app.geometry.kernel import mesh_to_legacy
from app.geometry.validators._common import cap_and_summarize
from app.services.geometry_inspection_service import inspect_face_planarity_issues


class NonPlanarFacesValidator:
    name: ClassVar[str] = "non_planar_faces"
    accepts: ClassVar[set[str]] = {"mesh"}
    kind: ClassVar[IssueKind] = IssueKind.NON_PLANAR_FACE

    def detect(self, geom: Mesh, ctx: Context) -> list[Issue]:
        faces, points = mesh_to_legacy(geom)
        raw = inspect_face_planarity_issues(
            faces, points,
            warn_planar_tol_m=ctx.tolerances.planarity_warn_m,
            fatal_planar_tol_m=ctx.tolerances.planarity_fatal_m,
        )
        return cap_and_summarize(
            raw,
            kind=self.kind,
            stage=DetectionStage.PRE,
            stage_name="",
            max_reports=ctx.tolerances.max_reports,
        )
