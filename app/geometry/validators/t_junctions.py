"""Validator: detects PLC-level T-junctions (vertex on another face's edge)."""
from __future__ import annotations

from typing import ClassVar

from app.geometry.context import Context
from app.geometry.ir import Mesh
from app.geometry.issues import DetectionStage, Issue, IssueKind, Severity
from app.geometry.kernel import mesh_to_legacy
from app.geometry.validators._common import cap_and_summarize
from app.services.geometry_inspection_service import (
    detect_t_junctions_from_facerecords_global_plc,
)


class TJunctionsValidator:
    name: ClassVar[str] = "t_junctions"
    accepts: ClassVar[set[str]] = {"mesh"}
    kind: ClassVar[IssueKind] = IssueKind.T_JUNCTION

    def detect(self, geom: Mesh, ctx: Context) -> list[Issue]:
        faces, points = mesh_to_legacy(geom)
        raw = detect_t_junctions_from_facerecords_global_plc(
            faces, points,
            tol=ctx.tolerances.t_junction,
            max_reports=ctx.tolerances.max_reports,
        )
        # T-junctions are always fatal (PLC violation); the legacy detector
        # does not emit a "severity" key.
        return cap_and_summarize(
            raw,
            kind=self.kind,
            stage=DetectionStage.PRE,
            stage_name="",
            max_reports=ctx.tolerances.max_reports,
            severity_of=lambda d: Severity.FATAL,
            payload_of=lambda d: dict(d),
        )
