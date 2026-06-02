"""Drop faces classified as fatally degenerate (effectively zero area)."""
from __future__ import annotations

import logging
from typing import ClassVar

from app.geometry.context import Context
from app.geometry.ir import Mesh
from app.geometry.issues import Issue, IssueKind
from app.geometry.kernel import mesh_from_legacy, mesh_to_legacy
from app.geometry.report import RepairResult
from app.services.geometry_repair_service import remove_degenerate_faces


class RemoveDegenerateFacesRepair:
    name: ClassVar[str] = "remove_degenerate_faces"
    accepts: ClassVar[set[str]] = {"mesh"}
    handles: ClassVar[set[IssueKind]] = {IssueKind.DEGENERATE_FACE}

    def apply(
        self,
        geom: Mesh,
        issues: list[Issue],
        ctx: Context,
    ) -> tuple[Mesh, RepairResult]:
        faces, points = mesh_to_legacy(geom)
        before = len(faces)
        clean_faces, fatal_removed = remove_degenerate_faces(
            faces, points,
            fatal_area_tol=ctx.tolerances.degenerate_area,
            logger=ctx.logger,
        )
        new_mesh = mesh_from_legacy(clean_faces, points, geom)

        affected = [i.id for i in issues if i.kind == IssueKind.DEGENERATE_FACE]
        result = RepairResult(
            step_name=self.name,
            stage_name=ctx.extras.get("stage_name", ""),
            affected_ids=affected,
            before_count=before,
            after_count=len(clean_faces),
            details={
                "fatal_removed": fatal_removed,
                "fatal_area_tol": ctx.tolerances.degenerate_area,
            },
        )
        return new_mesh, result
