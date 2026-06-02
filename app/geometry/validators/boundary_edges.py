from __future__ import annotations

from typing import ClassVar

from app.geometry.context import Context
from app.geometry.ir import Mesh
from app.geometry.issues import Issue, IssueKind


class BoundaryEdgesValidator:
    name: ClassVar[str] = "boundary_edges"
    accepts: ClassVar[set[str]] = {"mesh"}
    kind: ClassVar[IssueKind] = IssueKind.BOUNDARY_EDGE

    def detect(self, geom: Mesh, ctx: Context) -> list[Issue]:
        raise NotImplementedError
