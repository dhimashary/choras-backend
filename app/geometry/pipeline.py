"""Top-level orchestration: importer -> (convert) -> pre-validate -> stages -> final-validate -> export."""
from __future__ import annotations

from pathlib import Path

from app.geometry.context import Context
from app.geometry.ir import Geometry
from app.geometry.issues import DetectionStage
from app.geometry.profile import SimulationProfile, Stage
from app.geometry.report import (
    PipelineResult,
    RepairReport,
    ValidationSnapshot,
)
from app.geometry.validators.base import Validator


def run_pipeline(
    geom: Geometry,
    profile: SimulationProfile,
    output_path: Path,
    ctx: Context,
) -> PipelineResult:
    """Run the full pipeline for `geom` under `profile`.

    Produces a `PipelineResult` with one `ValidationSnapshot` for PRE,
    one per executed Stage, and one for FINAL — enabling stage-by-stage
    diffing via `app.geometry.diff.diff_snapshots`.
    """
    raise NotImplementedError


def run_validators(
    geom: Geometry,
    validators: list[Validator],
    ctx: Context,
    when: DetectionStage,
    stage_name: str = "",
) -> ValidationSnapshot:
    """Run every validator whose `accepts` includes `geom.kind`.

    Each Issue produced is tagged with `when` / `stage_name` automatically
    (validators should construct issues via `Issue.create(...)` so ids are
    stable across snapshots).
    """
    raise NotImplementedError


def run_stage(
    geom: Geometry,
    stage: Stage,
    ctx: Context,
    repair_report: RepairReport,
) -> tuple[Geometry, ValidationSnapshot]:
    """Apply one repair stage, run its post-validators, return new snapshot.

    The orchestrator appends the returned snapshot to `PipelineResult.snapshots`
    and records each repair's `RepairResult` (with `affected_ids`) into
    `repair_report`.
    """
    raise NotImplementedError
