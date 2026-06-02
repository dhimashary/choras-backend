"""Merge vertices that coincide within `tolerances.vertex_merge`.

In the legacy code this is the very first step on the raw OBJ vertex list
(see `parse_obj_file` then `deduplicate_vertices`). In the new pipeline
the importer already produces a `Mesh`; this repair re-runs the same merge
on Mesh vertices so it can also be invoked mid-pipeline if a later step
introduces near-duplicates.
"""
from __future__ import annotations

import logging
from typing import ClassVar

from app.geometry.context import Context
from app.geometry.ir import Face, Mesh, Vertex
from app.geometry.issues import Issue, IssueKind
from app.geometry.report import RepairResult
from app.services.geometry_parsing_service import deduplicate_vertices


class DeduplicateVerticesRepair:
    name: ClassVar[str] = "deduplicate_vertices"
    accepts: ClassVar[set[str]] = {"mesh"}
    handles: ClassVar[set[IssueKind]] = {IssueKind.DUPLICATE_VERTEX}

    def apply(
        self,
        geom: Mesh,
        issues: list[Issue],
        ctx: Context,
    ) -> tuple[Mesh, RepairResult]:
        old_points = [(v.x, v.y, v.z) for v in geom.vertices]
        unique_points, orig_to_unique = deduplicate_vertices(
            old_points, tol=ctx.tolerances.vertex_merge,
        )

        new_faces = [
            Face(
                vertex_indices=[orig_to_unique[vid] for vid in f.vertex_indices],
                group=f.group,
                material=f.material,
            )
            for f in geom.faces
        ]
        new_mesh = Mesh(
            vertices=[Vertex(p[0], p[1], p[2]) for p in unique_points],
            faces=new_faces,
            materials=dict(geom.materials),
            metadata=dict(geom.metadata),
        )

        affected = [i.id for i in issues if i.kind == IssueKind.DUPLICATE_VERTEX]
        result = RepairResult(
            step_name=self.name,
            stage_name=ctx.extras.get("stage_name", ""),
            affected_ids=affected,
            before_count=len(old_points),
            after_count=len(unique_points),
            details={
                "merged_vertex_count": len(old_points) - len(unique_points),
                "tolerance": ctx.tolerances.vertex_merge,
            },
        )
        return new_mesh, result
