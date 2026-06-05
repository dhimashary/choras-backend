"""Top-level orchestration: importer -> (convert) -> pre-validate -> stages -> final-validate -> export."""
from __future__ import annotations

from datetime import datetime, timezone
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


def run_validators(
    geom: Geometry,
    validators: list[Validator],
    ctx: Context,
    when: DetectionStage,
    stage_name: str = "",
) -> ValidationSnapshot:
    """Run every validator whose `accepts` includes `geom.kind`.

    Validators are skipped (with a warning) if they do not accept the
    incoming IR variant — this lets a profile carry validators that only
    apply to a subset of stages without forcing every caller to filter.
    """
    issues = []
    for v in validators:
        if geom.kind not in v.accepts:
            ctx.logger.warning(
                "[validators] skipping %s: accepts=%r but geom.kind=%r",
                v.name, v.accepts, geom.kind,
            )
            continue
        out = v.detect(geom, ctx)
        # Re-stamp issues so PRE-detected issues that get re-emitted by a
        # post_validator are correctly attributed to *this* snapshot. We
        # rebuild via Issue.create so ids stay stable.
        from app.geometry.issues import Issue
        for i in out:
            if i.stage is when and i.stage_name == stage_name:
                issues.append(i)
            else:
                issues.append(Issue.create(
                    kind=i.kind,
                    severity=i.severity,
                    stage=when,
                    stage_name=stage_name,
                    payload=i.payload,
                ))
    return ValidationSnapshot(
        when=when,
        stage_name=stage_name,
        issues=issues,
    )


def run_stage(
    geom: Geometry,
    stage: Stage,
    ctx: Context,
    repair_report: RepairReport,
    pre_issues: list,
) -> tuple[Geometry, ValidationSnapshot]:
    """Apply one repair stage, run its post-validators, return new snapshot.

    `pre_issues` is the union of all currently-known issues, used to
    populate `RepairResult.affected_ids` for each repair step.
    """
    # Stash stage_name on ctx.extras so every repair can read it without
    # threading it through the RepairStep protocol.
    prior_stage_name = ctx.extras.get("stage_name")
    ctx.extras["stage_name"] = stage.name

    try:
        for repair in stage.repairs:
            if geom.kind not in repair.accepts:
                ctx.logger.warning(
                    "[stage %s] skipping repair %s: accepts=%r but geom.kind=%r",
                    stage.name, repair.name, repair.accepts, geom.kind,
                )
                continue
            relevant = [i for i in pre_issues if i.kind in repair.handles] if repair.handles else pre_issues
            geom, result = repair.apply(geom, relevant, ctx)
            repair_report.results.append(result)
    finally:
        if prior_stage_name is None:
            ctx.extras.pop("stage_name", None)
        else:
            ctx.extras["stage_name"] = prior_stage_name

    snapshot = run_validators(
        geom, stage.post_validators, ctx,
        when=DetectionStage.POST_STAGE, stage_name=stage.name,
    )

    # Fail-fast handling
    if stage.fail_fast_on:
        offending = [i for i in snapshot.issues if i.kind in stage.fail_fast_on]
        if offending:
            ctx.logger.error(
                "[stage %s] fail_fast_on triggered (%d issues of kinds %s)",
                stage.name, len(offending),
                {i.kind.value for i in offending},
            )
            raise PipelineFailFastError(stage_name=stage.name, issues=offending)

    return geom, snapshot


class PipelineFailFastError(RuntimeError):
    def __init__(self, stage_name: str, issues: list) -> None:
        super().__init__(f"Pipeline aborted at stage {stage_name!r}: {len(issues)} blocking issue(s)")
        self.stage_name = stage_name
        self.issues = issues


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
    logger = ctx.logger
    
    logger.warning("Running pipeline %r on geometry kind %r", profile.name, geom.kind)
    if geom.kind != profile.target_ir.kind:
        raise ValueError(
            f"Profile {profile.name!r} expects IR kind {profile.target_ir.kind!r}, "
            f"got {geom.kind!r}"
        )

    snapshots: list[ValidationSnapshot] = []
    repairs = RepairReport()
    logger.warning("Pipeline %r: starting PRE-validation", profile.name)
    # PRE
    pre = run_validators(
        geom, profile.pre_validators, ctx,
        when=DetectionStage.PRE, stage_name="",
    )
    snapshots.append(pre)
    accumulated_issues = list(pre.issues)
    logger.warning("Pipeline %r: completed PRE-validation with %d issue(s)", profile.name, len(pre.issues))
    # Stages
    for stage in profile.stages:
        geom, snap = run_stage(geom, stage, ctx, repairs, accumulated_issues)
        snapshots.append(snap)
        # Post-stage issues feed into the next stage's affected_ids matching.
        accumulated_issues = list(snap.issues)

    logger.warning("Pipeline %r: completed all stages, starting FINAL validation", profile.name)
    # FINAL
    final = run_validators(
        geom, profile.final_validators, ctx,
        when=DetectionStage.FINAL, stage_name="",
    )
    snapshots.append(final)
    logger.warning("Pipeline %r: completed FINAL validation with %d issue(s)", profile.name, len(final.issues)) 
    # Export
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    for exporter in profile.exporters:
        target = getattr(exporter, "path_for", lambda p: p)(output_path)
        exporter.write(geom, target)
        ctx.logger.info(
            "[pipeline] wrote %s at %s",
            target, datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
    logger.warning("Pipeline %r: completed export to %s", profile.name, output_path)
    return PipelineResult(
        geometry=geom,
        snapshots=snapshots,
        repairs=repairs,
        output_path=str(output_path),
    )

