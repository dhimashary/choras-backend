"""Validator Protocol."""
from __future__ import annotations

from typing import ClassVar, Protocol

from app.geometry.context import Context
from app.geometry.ir import Geometry
from app.geometry.issues import Issue, IssueKind


class Validator(Protocol):
    name: ClassVar[str]
    accepts: ClassVar[set[str]]      # IR kinds, e.g. {"mesh"}
    kind: ClassVar[IssueKind]

    def detect(self, geom: Geometry, ctx: Context) -> list[Issue]: ...
