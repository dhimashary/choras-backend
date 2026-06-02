from __future__ import annotations

from typing import ClassVar

from app.geometry.context import Context
from app.geometry.ir import Mesh
from app.geometry.issues import Issue, IssueKind
from app.geometry.report import RepairResult
from app.geometry.validators.base import Validator


class TrimSegmentFaceIntersectionsRepair:
    name: ClassVar[str] = "trim_segment_face_intersections_iterative"
    accepts: ClassVar[set[str]] = {"mesh"}
    handles: ClassVar[set[IssueKind]] = {IssueKind.INTERSECTION}

    def __init__(self, detector: Validator, max_iters: int = 20) -> None:
        self.detector = detector
        self.max_iters = max_iters

    def apply(
        self,
        geom: Mesh,
        issues: list[Issue],
        ctx: Context,
    ) -> tuple[Mesh, RepairResult]:
        raise NotImplementedError


class RepairPlcSingleSplitsRepair:
    name: ClassVar[str] = "repair_plc_single_splits_iterative"
    accepts: ClassVar[set[str]] = {"mesh"}
    handles: ClassVar[set[IssueKind]] = {IssueKind.INTERSECTION}

    def __init__(self, detector: Validator, max_iters: int = 20) -> None:
        self.detector = detector
        self.max_iters = max_iters

    def apply(
        self,
        geom: Mesh,
        issues: list[Issue],
        ctx: Context,
    ) -> tuple[Mesh, RepairResult]:
        raise NotImplementedError
