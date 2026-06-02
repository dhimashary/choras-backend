"""Validator: detects vertices that coincide within `tolerances.vertex_merge`."""
from __future__ import annotations

from typing import ClassVar

from app.geometry.context import Context
from app.geometry.ir import Mesh
from app.geometry.issues import DetectionStage, Issue, IssueKind
from app.geometry.kernel import mesh_to_legacy
from app.geometry.validators._common import cap_and_summarize
from app.services.geometry_inspection_service import detect_duplicate_vertices


class DuplicateVerticesValidator:
    name: ClassVar[str] = "duplicate_vertices"
    accepts: ClassVar[set[str]] = {"mesh"}
    kind: ClassVar[IssueKind] = IssueKind.DUPLICATE_VERTEX

    def detect(self, geom: Mesh, ctx: Context) -> list[Issue]:
        _, points = mesh_to_legacy(geom)
        raw = detect_duplicate_vertices(points, tol=ctx.tolerances.vertex_merge)
        return cap_and_summarize(
            raw,
            kind=self.kind,
            stage=DetectionStage.PRE,
            stage_name="",
            max_reports=ctx.tolerances.max_reports,
        )
