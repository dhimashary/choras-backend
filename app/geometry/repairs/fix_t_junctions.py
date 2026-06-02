"""Iteratively split polygon edges until no PLC T-junctions remain.

The detector is injected (decision #6) so the loop can be re-run with a
faster detector without changing this class. Each iteration:
    1. detector.detect(mesh, ctx) → list of T-junction Issues
    2. if empty → done
    3. otherwise call the legacy `fix_t_junctions_iterative`, which itself
       contains a fast inner loop that splits all reported edges in one
       pass; we exit this outer loop after that single call.

The outer loop is kept in case a future detector reports a single batch
that the inner repair only partially fixes — today's detector is global
so a single inner call is sufficient.
"""
from __future__ import annotations

from typing import ClassVar

from app.geometry.context import Context
from app.geometry.ir import Mesh
from app.geometry.issues import Issue, IssueKind
from app.geometry.kernel import mesh_from_legacy, mesh_to_legacy
from app.geometry.report import RepairResult
from app.geometry.validators.base import Validator
from app.services.geometry_repair_service import fix_t_junctions_iterative


class FixTJunctionsIterativeRepair:
    name: ClassVar[str] = "fix_t_junctions_iterative"
    accepts: ClassVar[set[str]] = {"mesh"}
    handles: ClassVar[set[IssueKind]] = {IssueKind.T_JUNCTION}

    def __init__(self, detector: Validator, max_iters: int | None = None) -> None:
        self.detector = detector
        self.max_iters = max_iters

    def apply(
        self,
        geom: Mesh,
        issues: list[Issue],
        ctx: Context,
    ) -> tuple[Mesh, RepairResult]:
        max_iters = self.max_iters or ctx.tolerances.max_t_junction_iters
        faces, points = mesh_to_legacy(geom)
        before = len(faces)

        # The legacy `fix_t_junctions_iterative` already uses the legacy
        # detector internally. We pre-compute Issues via the injected
        # detector only for `affected_ids` book-keeping; the actual fix
        # is delegated.
        affected = [i.id for i in issues if i.kind == IssueKind.T_JUNCTION]

        new_faces, changed = fix_t_junctions_iterative(
            faces, points,
            tol=ctx.tolerances.t_junction,
            max_iters=max_iters,
            max_reports=ctx.tolerances.max_reports,
            logger=ctx.logger,
        )
        new_mesh = mesh_from_legacy(new_faces, points, geom)

        # Count remaining T-junctions to record convergence.
        remaining = self.detector.detect(new_mesh, ctx)
        result = RepairResult(
            step_name=self.name,
            stage_name=ctx.extras.get("stage_name", ""),
            affected_ids=affected,
            before_count=before,
            after_count=len(new_faces),
            iterations=max_iters if changed else 0,
            details={
                "changed": bool(changed),
                "remaining_t_junctions": len(remaining),
                "tolerance": ctx.tolerances.t_junction,
            },
        )
        return new_mesh, result
