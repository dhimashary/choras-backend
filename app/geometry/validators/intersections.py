"""Validator: detects segment-facet intersections (CDT-based)."""
from __future__ import annotations

from typing import ClassVar

from app.geometry.context import Context
from app.geometry.ir import Mesh
from app.geometry.issues import DetectionStage, Issue, IssueKind, Severity
from app.geometry.kernel import mesh_to_legacy
from app.geometry.validators._common import cap_and_summarize
from app.services.geometry_inspection_service import (
    detect_segment_facet_intersections_cdt,
)


class IntersectionsValidator:
    name: ClassVar[str] = "intersections"
    accepts: ClassVar[set[str]] = {"mesh"}
    kind: ClassVar[IssueKind] = IssueKind.INTERSECTION

    def detect(self, geom: Mesh, ctx: Context) -> list[Issue]:
        faces, points = mesh_to_legacy(geom)
        raw = detect_segment_facet_intersections_cdt(
            faces, points,
            warn_planar_tol_m=ctx.tolerances.planarity_warn_m,
            fatal_planar_tol_m=ctx.tolerances.planarity_fatal_m,
            eps=ctx.tolerances.intersection_eps,
            bbox_pad=ctx.tolerances.bbox_pad,
            max_reports=ctx.tolerances.max_reports,
        )
        # Detector returns a `hit_type` discriminator; surface it as
        # payload["sub_kind"] so downstream code can route on it without
        # widening IssueKind.
        def _payload_of(d: dict) -> dict:
            p = dict(d)
            p["sub_kind"] = d.get("hit_type", "interior")
            return p
        return cap_and_summarize(
            raw,
            kind=self.kind,
            stage=DetectionStage.PRE,
            stage_name="",
            max_reports=ctx.tolerances.max_reports,
            severity_of=lambda d: Severity.FATAL,
            payload_of=_payload_of,
        )
