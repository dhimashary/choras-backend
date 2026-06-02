from __future__ import annotations

from typing import ClassVar

from app.geometry.context import Context
from app.geometry.ir import Mesh
from app.geometry.issues import Issue, IssueKind
from app.geometry.report import RepairResult


class SortVerticesDeterministicallyRepair:
    """Re-index vertices in a stable order to make output reproducible."""

    name: ClassVar[str] = "sort_vertices_deterministically"
    accepts: ClassVar[set[str]] = {"mesh"}
    handles: ClassVar[set[IssueKind]] = set()

    def apply(
        self,
        geom: Mesh,
        issues: list[Issue],
        ctx: Context,
    ) -> tuple[Mesh, RepairResult]:
        raise NotImplementedError
