"""Public API of the geometry module.

Importers, validators, repair steps, and exporters live in their own
sub-packages. The Flask layer should only import names re-exported here.
"""
from __future__ import annotations

from app.geometry.ir import (
    Geometry,
    Mesh,
    BRep,
    PointCloud,
    Vertex,
    Face,
    Curve,
    Surface,
    MaterialInfo,
    LayerInfo,
)
from app.geometry.issues import DetectionStage, Issue, IssueKind, Severity
from app.geometry.context import Context
from app.geometry.tolerances import Tolerances
from app.geometry.profile import SimulationProfile, Stage
from app.geometry.report import (
    PipelineResult,
    RepairResult,
    RepairReport,
    ValidationSnapshot,
)
from app.geometry.diff import SnapshotDiff, diff_snapshots
from app.geometry.pipeline import run_pipeline

__all__ = [
    "Geometry",
    "Mesh",
    "BRep",
    "PointCloud",
    "Vertex",
    "Face",
    "Curve",
    "Surface",
    "MaterialInfo",
    "LayerInfo",
    "Issue",
    "IssueKind",
    "Severity",
    "DetectionStage",
    "Context",
    "Tolerances",
    "SimulationProfile",
    "Stage",
    "PipelineResult",
    "RepairResult",
    "ValidationSnapshot",
    "RepairReport",
    "SnapshotDiff",
    "diff_snapshots",
    "run_pipeline",
]
