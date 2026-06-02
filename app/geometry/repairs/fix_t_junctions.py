from __future__ import annotations

from typing import ClassVar

from app.geometry.context import Context
from app.geometry.ir import Mesh
from app.geometry.issues import Issue, IssueKind
from app.geometry.report import RepairResult
from app.geometry.validators.base import Validator


class FixTJunctionsIterativeRepair:
    """Detect-and-fix T-junctions iteratively until convergence or max_iters.

    The detector is injected so the repair is testable in isolation and so
    the same loop can later use a faster (e.g. CGAL-backed) detector
    without changing this class.
    """

    name: ClassVar[str] = "fix_t_junctions_iterative"
    accepts: ClassVar[set[str]] = {"mesh"}
    handles: ClassVar[set[IssueKind]] = {IssueKind.T_JUNCTION}

    def __init__(self, detector: Validator, max_iters: int = 100) -> None:
        self.detector = detector
        self.max_iters = max_iters

    def apply(
        self,
        geom: Mesh,
        issues: list[Issue],
        ctx: Context,
    ) -> tuple[Mesh, RepairResult]:
        raise NotImplementedError
