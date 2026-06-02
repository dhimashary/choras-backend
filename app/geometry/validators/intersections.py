from __future__ import annotations

from typing import ClassVar

from app.geometry.context import Context
from app.geometry.ir import Mesh
from app.geometry.issues import Issue, IssueKind


class SegmentFacetIntersectionsValidator:
    """PLC violation detector (segment-facet intersections)."""

    name: ClassVar[str] = "segment_facet_intersections"
    accepts: ClassVar[set[str]] = {"mesh"}
    kind: ClassVar[IssueKind] = IssueKind.INTERSECTION

    def detect(self, geom: Mesh, ctx: Context) -> list[Issue]:
        raise NotImplementedError
