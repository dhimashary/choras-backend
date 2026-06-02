"""Typed geometry issues produced by validators."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum


class IssueKind(str, Enum):
    DUPLICATE_VERTEX = "duplicate_vertex"
    DEGENERATE_FACE = "degenerate_face"
    NON_PLANAR_FACE = "non_planar_face"
    T_JUNCTION = "t_junction"
    INTERSECTION = "intersection"
    BOUNDARY_EDGE = "boundary_edge"
    POSSIBLE_HOLE = "possible_hole"
    INVERTED_NORMAL = "inverted_normal"


class Severity(str, Enum):
    WARN = "warn"
    FATAL = "fatal"


class DetectionStage(str, Enum):
    """When in the pipeline an issue was observed."""
    PRE = "pre"                    # before any repair
    POST_STAGE = "post_stage"      # after a specific repair stage
    FINAL = "final"                # after all stages


@dataclass(frozen=True)
class Issue:
    """A defect detected by a validator.

    `id` is a stable content hash of (kind, payload) so that the *same*
    physical defect produces the *same* id across snapshots — this is what
    makes before/after diffing possible.
    """
    id: str
    kind: IssueKind
    severity: Severity
    stage: DetectionStage
    stage_name: str = ""           # Stage.name that produced it ("" for PRE/FINAL)
    payload: dict = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        kind: IssueKind,
        severity: Severity,
        stage: DetectionStage,
        stage_name: str = "",
        payload: dict | None = None,
    ) -> "Issue":
        payload = payload or {}
        key = json.dumps([kind.value, payload], sort_keys=True, default=str)
        issue_id = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
        return cls(
            id=issue_id,
            kind=kind,
            severity=severity,
            stage=stage,
            stage_name=stage_name,
            payload=payload,
        )
