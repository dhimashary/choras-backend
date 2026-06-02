from __future__ import annotations

from typing import ClassVar

from app.geometry.context import Context
from app.geometry.ir import Mesh
from app.geometry.issues import Issue, IssueKind


class DegenerateFacesValidator:
    name: ClassVar[str] = "degenerate_faces"
    accepts: ClassVar[set[str]] = {"mesh"}
    kind: ClassVar[IssueKind] = IssueKind.DEGENERATE_FACE

    def detect(self, geom: Mesh, ctx: Context) -> list[Issue]:
        raise NotImplementedError
