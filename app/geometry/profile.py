"""SimulationProfile bundles all per-solver policy in one object."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.geometry.io.exporters.base import Exporter
from app.geometry.ir import Geometry
from app.geometry.issues import IssueKind
from app.geometry.repairs.base import RepairStep
from app.geometry.tolerances import Tolerances
from app.geometry.validators.base import Validator


@dataclass
class Stage:
    """One ordered repair-then-detect stage of the pipeline.

    Stages let a profile express dependencies like *"detect holes only
    AFTER T-junctions are fixed, otherwise T-junctions masquerade as holes."*
    """
    name: str
    repairs: list[RepairStep] = field(default_factory=list)
    post_validators: list[Validator] = field(default_factory=list)
    fail_fast_on: set[IssueKind] = field(default_factory=set)


@dataclass
class SimulationProfile:
    name: str
    target_ir: type[Geometry]
    pre_validators: list[Validator]      # initial detection (everything safe up-front)
    stages: list[Stage]                  # ordered repair + post-detection stages
    final_validators: list[Validator]    # revalidation at the end
    exporters: list[Exporter]
    tolerances: Tolerances

    def __post_init__(self) -> None:
        """Profile-level consistency check.

        Every validator and repair attached to a profile must declare that it
        `accepts` this profile's `target_ir.kind`. Catching this at profile
        construction time turns a runtime ``ValueError`` somewhere deep in
        the pipeline into a clear, immediate one.
        """
        ir_kind = self.target_ir.kind
        bad: list[str] = []

        def _check(component, role: str) -> None:
            accepts = getattr(component, "accepts", None)
            name = getattr(component, "name", type(component).__name__)
            if accepts is None or ir_kind not in accepts:
                bad.append(f"{role} {name!r} accepts={accepts!r} but profile target_ir.kind={ir_kind!r}")

        for v in self.pre_validators:
            _check(v, "pre_validator")
        for v in self.final_validators:
            _check(v, "final_validator")
        for stage in self.stages:
            for r in stage.repairs:
                _check(r, f"stage[{stage.name}].repair")
            for v in stage.post_validators:
                _check(v, f"stage[{stage.name}].post_validator")

        if bad:
            joined = "\n  - ".join(bad)
            raise ValueError(
                f"SimulationProfile {self.name!r} has IR-kind mismatches:\n  - {joined}"
            )
