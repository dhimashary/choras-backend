"""Merge vertices that coincide within `tolerances.vertex_merge`.

In the legacy code this is the very first step on the raw OBJ vertex list
(see `parse_obj_file` then `deduplicate_vertices`). In the new pipeline
the importer already produces a `Mesh`; this repair re-runs the same merge
on Mesh vertices so it can also be invoked mid-pipeline if a later step
introduces near-duplicates.
"""
from __future__ import annotations

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

    @staticmethod
    def _remove_consecutive_duplicate_indices(
        indices: list[int],
    ) -> list[int]:
        """Remove consecutive duplicate vertices and repeated closing vertex."""
        if not indices:
            return []

        cleaned = [indices[0]]

        for idx in indices[1:]:
            if idx != cleaned[-1]:
                cleaned.append(idx)

        # Remove explicit closing vertex:
        # [1,2,3,1] -> [1,2,3]
        if len(cleaned) > 1 and cleaned[0] == cleaned[-1]:
            cleaned.pop()

        return cleaned

    def apply(
        self,
        geom: Mesh,
        issues: list[Issue],
        ctx: Context,
    ) -> tuple[Mesh, RepairResult]:
        old_points = [(v.x, v.y, v.z) for v in geom.vertices]

        unique_points, orig_to_unique = deduplicate_vertices(
            old_points,
            tol=ctx.tolerances.vertex_merge,
        )

        new_faces: list[Face] = []
        removed_invalid_face_ids: list[int] = []
        cleaned_duplicate_face_ids: list[int] = []

        for face_idx, face in enumerate(geom.faces):
            remapped_indices = [
                orig_to_unique[vid]
                for vid in face.vertex_indices
            ]

            cleaned_indices = self._remove_consecutive_duplicate_indices(
                remapped_indices
            )

            if cleaned_indices != remapped_indices:
                cleaned_duplicate_face_ids.append(face_idx)

            if len(set(cleaned_indices)) < 3:
                removed_invalid_face_ids.append(face_idx)
                continue

            new_faces.append(
                Face(
                    vertex_indices=cleaned_indices,
                    group=face.group,
                    material=face.material,
                )
            )

        new_mesh = Mesh(
            vertices=[
                Vertex(p[0], p[1], p[2])
                for p in unique_points
            ],
            faces=new_faces,
            materials=dict(geom.materials),
            metadata=dict(geom.metadata),
        )

        affected = [
            issue.id
            for issue in issues
            if issue.kind == IssueKind.DUPLICATE_VERTEX
        ]

        result = RepairResult(
            step_name=self.name,
            stage_name=ctx.extras.get("stage_name", ""),
            affected_ids=affected,
            before_count=len(old_points),
            after_count=len(unique_points),
            details={
                "merged_vertex_count": len(old_points) - len(unique_points),
                "tolerance": ctx.tolerances.vertex_merge,
                "cleaned_duplicate_face_count": len(cleaned_duplicate_face_ids),
                "cleaned_duplicate_face_ids": cleaned_duplicate_face_ids,
                "removed_invalid_face_count": len(removed_invalid_face_ids),
                "removed_invalid_face_ids": removed_invalid_face_ids,
            },
        )

        return new_mesh, result