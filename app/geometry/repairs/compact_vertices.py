"""Compact vertices: drop any not referenced by a face and remap indices."""
from __future__ import annotations

from typing import ClassVar

from app.geometry.context import Context
from app.geometry.ir import Mesh
from app.geometry.issues import Issue, IssueKind
from app.geometry.kernel import mesh_from_legacy, mesh_to_legacy
from app.geometry.report import RepairResult
from app.services.geometry_repair_service import compact_vertices_and_remove_unused


class CompactVerticesRepair:
    name: ClassVar[str] = "compact_vertices_and_remove_unused"
    accepts: ClassVar[set[str]] = {"mesh"}
    handles: ClassVar[set[IssueKind]] = set()

    def apply(
        self,
        geom: Mesh,
        issues: list[Issue],
        ctx: Context,
    ) -> tuple[Mesh, RepairResult]:
        faces, points = mesh_to_legacy(geom)
        new_faces, new_points, _changed, diag = compact_vertices_and_remove_unused(faces, points)
        new_mesh = mesh_from_legacy(new_faces, new_points, geom)
        result = RepairResult(
            step_name=self.name,
            stage_name=ctx.extras.get("stage_name", ""),
            affected_ids=[],
            before_count=len(points),
            after_count=len(new_points),
            details=dict(diag),
        )
        return new_mesh, result
