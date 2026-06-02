"""RepairStep Protocol."""
from __future__ import annotations

from typing import ClassVar, Protocol

from app.geometry.context import Context
from app.geometry.ir import Geometry
from app.geometry.issues import Issue, IssueKind
from app.geometry.report import RepairResult


class RepairStep(Protocol):
    name: ClassVar[str]
    accepts: ClassVar[set[str]]            # IR kinds it can run on
    handles: ClassVar[set[IssueKind]]      # IssueKinds this step addresses

    def apply(
        self,
        geom: Geometry,
        issues: list[Issue],
        ctx: Context,
    ) -> tuple[Geometry, RepairResult]: ...
