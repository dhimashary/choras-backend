"""Three intersection repairs sharing the same injected detector.

* ``TrimSegmentFaceIntersectionsRepair`` — for "edge cuts through face
  interior" cases. Trims one component at a time against the offending
  face's plane until no `segment_face_interior_intersection` remains.
* ``RepairPlcSingleSplitsRepair`` — for `endpoint_face_interior_touch`
  cases where the touching endpoint lies inside a face: split the face
  at that endpoint via triangulation.
* ``RepairPlcByOffsetRepair`` — last-resort fallback: nudge a touching
  endpoint along the touched face's normal by ``tolerances.plc_offset``.
"""
from __future__ import annotations

from typing import ClassVar

from app.geometry.context import Context
from app.geometry.ir import Mesh
from app.geometry.issues import Issue, IssueKind
from app.geometry.kernel import mesh_from_legacy, mesh_to_legacy
from app.geometry.report import RepairResult
from app.geometry.repairs.mesh_helpers import room_center_from_mesh
from app.geometry.validators.base import Validator
from app.services.geometry_repair_service import (
    repair_plc_by_offset_iterative,
    repair_plc_single_splits_iterative,
    trim_segment_face_intersections_iterative,
)


def _affected(issues: list[Issue]) -> list[str]:
    return [i.id for i in issues if i.kind == IssueKind.INTERSECTION]


class TrimSegmentFaceIntersectionsRepair:
    name: ClassVar[str] = "trim_segment_face_intersections_iterative"
    accepts: ClassVar[set[str]] = {"mesh"}
    handles: ClassVar[set[IssueKind]] = {IssueKind.INTERSECTION}

    def __init__(self, detector: Validator, max_iters: int | None = None) -> None:
        self.detector = detector
        self.max_iters = max_iters

    def apply(
        self,
        geom: Mesh,
        issues: list[Issue],
        ctx: Context,
    ) -> tuple[Mesh, RepairResult]:
        max_iters = self.max_iters or ctx.tolerances.max_plc_iters
        faces, points = mesh_to_legacy(geom)
        before_faces = len(faces)
        before_points = len(points)

        new_faces, new_points, changed_any, diag = trim_segment_face_intersections_iterative(
            faces, points,
            room_center_from_mesh(geom),
            max_iters=max_iters,
            tol=ctx.tolerances.clipping,
            logger=ctx.logger,
        )
        new_mesh = mesh_from_legacy(new_faces, new_points, geom)
        remaining = self.detector.detect(new_mesh, ctx)

        result = RepairResult(
            step_name=self.name,
            stage_name=ctx.extras.get("stage_name", ""),
            affected_ids=_affected(issues),
            before_count=before_faces,
            after_count=len(new_faces),
            iterations=int(diag.get("iterations", max_iters if changed_any else 0)),
            details={
                **diag,
                "changed": bool(changed_any),
                "vertices_before": before_points,
                "vertices_after": len(new_points),
                "remaining_intersections": len(remaining),
            },
        )
        return new_mesh, result


class RepairPlcSingleSplitsRepair:
    name: ClassVar[str] = "repair_plc_single_splits_iterative"
    accepts: ClassVar[set[str]] = {"mesh"}
    handles: ClassVar[set[IssueKind]] = {IssueKind.INTERSECTION}

    def __init__(self, detector: Validator, max_iters: int | None = None) -> None:
        self.detector = detector
        self.max_iters = max_iters

    def apply(
        self,
        geom: Mesh,
        issues: list[Issue],
        ctx: Context,
    ) -> tuple[Mesh, RepairResult]:
        max_iters = self.max_iters or ctx.tolerances.max_plc_iters
        faces, points = mesh_to_legacy(geom)
        before = len(faces)

        result_tuple = repair_plc_single_splits_iterative(
            faces, points,
            room_center_from_mesh(geom),
            logger=ctx.logger,
            max_iters=max_iters,
            planarity_tol_m=ctx.tolerances.planarity_split,
        )
        # The legacy function returns (faces, points, changed, diag) — but
        # historically some variants return only (faces, points). Be defensive.
        if len(result_tuple) >= 4:
            new_faces, new_points, changed_any, diag = result_tuple[:4]
        else:
            new_faces, new_points = result_tuple[:2]
            changed_any, diag = False, {}

        new_mesh = mesh_from_legacy(new_faces, new_points, geom)
        remaining = self.detector.detect(new_mesh, ctx)

        return new_mesh, RepairResult(
            step_name=self.name,
            stage_name=ctx.extras.get("stage_name", ""),
            affected_ids=_affected(issues),
            before_count=before,
            after_count=len(new_faces),
            iterations=int(diag.get("iterations", max_iters if changed_any else 0)),
            details={
                **diag,
                "changed": bool(changed_any),
                "remaining_intersections": len(remaining),
                "planarity_tol_m": ctx.tolerances.planarity_split,
            },
        )


class RepairPlcByOffsetRepair:
    name: ClassVar[str] = "repair_plc_by_offset_iterative"
    accepts: ClassVar[set[str]] = {"mesh"}
    handles: ClassVar[set[IssueKind]] = {IssueKind.INTERSECTION}

    def __init__(self, detector: Validator, max_iters: int | None = None) -> None:
        self.detector = detector
        self.max_iters = max_iters

    def apply(
        self,
        geom: Mesh,
        issues: list[Issue],
        ctx: Context,
    ) -> tuple[Mesh, RepairResult]:
        max_iters = self.max_iters or ctx.tolerances.max_plc_iters
        faces, points = mesh_to_legacy(geom)
        before = len(faces)

        result_tuple = repair_plc_by_offset_iterative(
            faces, points,
            logger=ctx.logger,
            max_iters=max_iters,
            offset_m=ctx.tolerances.plc_offset,
        )
        if len(result_tuple) >= 4:
            new_faces, new_points, changed_any, diag = result_tuple[:4]
        else:
            new_faces, new_points = result_tuple[:2]
            changed_any, diag = False, {}

        new_mesh = mesh_from_legacy(new_faces, new_points, geom)
        remaining = self.detector.detect(new_mesh, ctx)

        return new_mesh, RepairResult(
            step_name=self.name,
            stage_name=ctx.extras.get("stage_name", ""),
            affected_ids=_affected(issues),
            before_count=before,
            after_count=len(new_faces),
            iterations=int(diag.get("iterations", max_iters if changed_any else 0)),
            details={
                **diag,
                "changed": bool(changed_any),
                "remaining_intersections": len(remaining),
                "offset_m": ctx.tolerances.plc_offset,
            },
        )
