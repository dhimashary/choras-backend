from __future__ import annotations

from typing import ClassVar

from app.geometry.context import Context
from app.geometry.ir import Mesh
from app.geometry.issues import Issue, IssueKind


class DuplicateVerticesValidator:
    name: ClassVar[str] = "duplicate_vertices"
    accepts: ClassVar[set[str]] = {"mesh"}
    kind: ClassVar[IssueKind] = IssueKind.DUPLICATE_VERTEX

    def detect(self, geom: Mesh, ctx: Context) -> list[Issue]:
        raise NotImplementedError
