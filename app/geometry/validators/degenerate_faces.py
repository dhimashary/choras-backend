"""Validator: detects faces with effectively zero area."""
from __future__ import annotations

from typing import ClassVar

from app.geometry.context import Context
from app.geometry.ir import Mesh
from app.geometry.issues import DetectionStage, Issue, IssueKind
from app.geometry.kernel import mesh_to_legacy
from app.geometry.validators._common import cap_and_summarize
from app.services.geometry_inspection_service import detect_degenerate_faces


class DegenerateFacesValidator:
    name: ClassVar[str] = "degenerate_faces"
    accepts: ClassVar[set[str]] = {"mesh"}
    kind: ClassVar[IssueKind] = IssueKind.DEGENERATE_FACE

    def detect(self, geom: Mesh, ctx: Context) -> list[Issue]:
        faces, points = mesh_to_legacy(geom)
        raw = detect_degenerate_faces(
            faces, points,
            fatal_area2_tol=ctx.tolerances.degenerate_area,
        )
        return cap_and_summarize(
            raw,
            kind=self.kind,
            stage=DetectionStage.PRE,
            stage_name="",
            max_reports=ctx.tolerances.max_reports,
        )
