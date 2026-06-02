"""Validator: detects open boundary edges (edges adjacent to one face only)."""
from __future__ import annotations

from typing import ClassVar

from app.geometry.context import Context
from app.geometry.ir import Mesh
from app.geometry.issues import DetectionStage, Issue, IssueKind
from app.geometry.kernel import mesh_to_legacy
from app.geometry.validators._common import cap_and_summarize
from app.services.geometry_inspection_service import detect_boundary_edges


class BoundaryEdgesValidator:
    name: ClassVar[str] = "boundary_edges"
    accepts: ClassVar[set[str]] = {"mesh"}
    kind: ClassVar[IssueKind] = IssueKind.BOUNDARY_EDGE

    def detect(self, geom: Mesh, ctx: Context) -> list[Issue]:
        faces, points = mesh_to_legacy(geom)
        raw = detect_boundary_edges(faces, points)
        return cap_and_summarize(
            raw,
            kind=self.kind,
            stage=DetectionStage.PRE,
            stage_name="",
            max_reports=ctx.tolerances.max_reports,
        )
