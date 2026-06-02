from __future__ import annotations

from typing import ClassVar

from app.geometry.context import Context
from app.geometry.ir import Mesh
from app.geometry.issues import Issue, IssueKind
from app.geometry.report import RepairResult


class FlipFacesIfMajorityInwardRepair:
    name: ClassVar[str] = "flip_all_faces_if_majority_inward"
    accepts: ClassVar[set[str]] = {"mesh"}
    handles: ClassVar[set[IssueKind]] = {IssueKind.INVERTED_NORMAL}

    def apply(
        self,
        geom: Mesh,
        issues: list[Issue],
        ctx: Context,
    ) -> tuple[Mesh, RepairResult]:
        raise NotImplementedError
