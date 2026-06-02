from __future__ import annotations

from typing import ClassVar

from app.geometry.context import Context
from app.geometry.ir import Mesh
from app.geometry.issues import Issue, IssueKind
from app.geometry.report import RepairResult


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
        raise NotImplementedError
