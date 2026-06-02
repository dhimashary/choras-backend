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
    exporter: Exporter
    tolerances: Tolerances
