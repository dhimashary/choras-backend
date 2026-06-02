"""Validator: detects closed boundary loops (candidate holes in the surface)."""
from __future__ import annotations

from typing import ClassVar

from app.geometry.context import Context
from app.geometry.ir import Mesh
from app.geometry.issues import DetectionStage, Issue, IssueKind
from app.geometry.kernel import mesh_to_legacy
from app.geometry.validators._common import cap_and_summarize
from app.services.geometry_inspection_service import detect_possible_holes_from_faces


class PossibleHolesValidator:
    name: ClassVar[str] = "possible_holes"
    accepts: ClassVar[set[str]] = {"mesh"}
    kind: ClassVar[IssueKind] = IssueKind.POSSIBLE_HOLE

    def detect(self, geom: Mesh, ctx: Context) -> list[Issue]:
        faces, points = mesh_to_legacy(geom)
        raw = detect_possible_holes_from_faces(faces, points)
        return cap_and_summarize(
            raw,
            kind=self.kind,
            stage=DetectionStage.PRE,
            stage_name="",
            max_reports=ctx.tolerances.max_reports,
        )
