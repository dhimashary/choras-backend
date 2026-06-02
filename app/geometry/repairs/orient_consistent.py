"""Make polygon winding globally consistent across shared edges.

For every manifold shared edge (used by exactly two faces), ensure the
edge direction is opposite in the two faces. This is required for a
valid PLC topology and for correct outward-normal computation downstream.
"""
from __future__ import annotations

from typing import ClassVar

from app.geometry.context import Context
from app.geometry.ir import Mesh
from app.geometry.issues import Issue, IssueKind
from app.geometry.kernel import mesh_from_legacy, mesh_to_legacy
from app.geometry.report import RepairResult
from app.services.geometry_repair_service import orient_faces_consistently_by_adjacency


class OrientFacesConsistentlyByAdjacencyRepair:
    name: ClassVar[str] = "orient_faces_consistently_by_adjacency"
    accepts: ClassVar[set[str]] = {"mesh"}
    handles: ClassVar[set[IssueKind]] = {IssueKind.INVERTED_NORMAL}

    def apply(
        self,
        geom: Mesh,
        issues: list[Issue],
        ctx: Context,
    ) -> tuple[Mesh, RepairResult]:
        faces, points = mesh_to_legacy(geom)
        diag = orient_faces_consistently_by_adjacency(faces, logger=ctx.logger)
        new_mesh = mesh_from_legacy(faces, points, geom)
        result = RepairResult(
            step_name=self.name,
            stage_name=ctx.extras.get("stage_name", ""),
            affected_ids=[i.id for i in issues if i.kind == IssueKind.INVERTED_NORMAL],
            before_count=len(faces),
            after_count=len(faces),
            details=dict(diag),
        )
        return new_mesh, result
