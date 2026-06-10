"""Wave-based (FEM/FDTD) simulation profile.

The stage order encodes geometric dependencies:
  1. dedup / degenerate / orient — preconditions for the topology checks below.
  2. fix T-junctions FIRST: an unfixed T-junction looks like a hole AND like
     an intersection, so detecting those before this stage produces noise.
  3. fix intersections (PLC violations).
  4. detect remaining holes / boundary edges only at the end.
"""
from __future__ import annotations

from app.geometry.io.exporters.geo import GmshGeoExporter
from app.geometry.io.exporters.obj import ObjExporter
from app.geometry.io.exporters.three_dm import ThreeDMExporter
from app.geometry.ir import Mesh
from app.geometry.profile import SimulationProfile, Stage
from app.geometry.repairs.deduplicate_vertices import DeduplicateVerticesRepair
from app.geometry.repairs.fix_t_junctions import FixTJunctionsIterativeRepair
from app.geometry.repairs.orient_outward import FlipFacesIfMajorityInwardRepair
from app.geometry.repairs.remove_degenerate_faces import RemoveDegenerateFacesRepair
from app.geometry.repairs.repair_intersections import (
    RepairPlcByOffsetRepair,
    RepairPlcSingleSplitsRepair,
    TrimSegmentFaceIntersectionsRepair,
)
from app.geometry.repairs.sort_vertices import SortVerticesDeterministicallyRepair
from app.geometry.tolerances import Tolerances
from app.geometry.validators.boundary_edges import BoundaryEdgesValidator
from app.geometry.validators.degenerate_faces import DegenerateFacesValidator
from app.geometry.validators.duplicate_vertices import DuplicateVerticesValidator
from app.geometry.validators.intersections import IntersectionsValidator
from app.geometry.validators.non_planar_faces import NonPlanarFacesValidator
from app.geometry.validators.possible_holes import PossibleHolesValidator
from app.geometry.validators.t_junctions import TJunctionsValidator


def _wave_based_pre_validators(tjunc, intersect) -> list:
    return [
        DuplicateVerticesValidator(),
        DegenerateFacesValidator(),
        NonPlanarFacesValidator(),
        tjunc,
        intersect,
        BoundaryEdgesValidator(),
        PossibleHolesValidator(),
    ]


def _wave_based_stages(tjunc, intersect, *, inspect: bool = False) -> list[Stage]:
    """Shared stage list: dedupe → tj → intersect → topology.

    The order is what makes detection meaningful (T-junctions only
    detectable after dedupe; intersections only meaningful after tj fix).
    Both the full and inspect-only profiles consume this same list so
    the diagnostic order can never drift between them.

    ``inspect=True`` reshapes the stage tail for diagnostic-only runs:
      - the ``orient`` stage gains a tjunc post-validator (so the report
        captures the *original* tjunc count, before any fix)
      - the ``t_junctions`` stage drops its tjunc post-validator (the fix
        runs only to denoise the intersection detector — we don't care
        about the residual count)
      - the ``intersections`` stage drops its repairs (detection only)
    """
    return [
        Stage(name="deduplication", repairs=[DeduplicateVerticesRepair()]),
        Stage(name="degenerate", repairs=[RemoveDegenerateFacesRepair()]),
        Stage(name="sort", repairs=[SortVerticesDeterministicallyRepair()]),
        Stage(
            name="orient",
            repairs=[FlipFacesIfMajorityInwardRepair()],
        ),
        Stage(
            name="t_junctions",
            repairs=[] if inspect else [FixTJunctionsIterativeRepair(detector=tjunc)],
            post_validators=[tjunc] if inspect else [],
        ),
        Stage(
            name="intersections",
            repairs=(
                [FixTJunctionsIterativeRepair(detector=tjunc)]
                if inspect
                else [
                    TrimSegmentFaceIntersectionsRepair(detector=intersect),
                    RepairPlcSingleSplitsRepair(detector=intersect),
                    # RepairPlcByOffsetRepair(detector=intersect),
                ]
            ),
            post_validators=[intersect],
        ),
        Stage(
            name="topology",
            post_validators=[BoundaryEdgesValidator(), PossibleHolesValidator()],
        ),
    ]


def _wave_based_final_validators(tjunc, intersect) -> list:
    return [
        NonPlanarFacesValidator(),
        tjunc,
        intersect,
        BoundaryEdgesValidator(),
        PossibleHolesValidator(),
    ]


def wave_based_profile(
    volume_name: str = "RoomVolume",
    *,
    detect_cavities: bool = False,
    cavity_pitch: float = 0.05,
    cavity_closing_iterations: int = 0,
) -> SimulationProfile:
    """Full profile: detect → repair → emit OBJ + GEO.

    When `detect_cavities=True`, the GEO exporter runs the voxel-based cavity
    detector and emits one `Volume` per enclosed region (required by Gmsh
    when the geometry contains nested/attached enclosed objects).
    """
    tjunc = TJunctionsValidator()
    intersect = IntersectionsValidator()
    return SimulationProfile(
        name="wave_based",
        target_ir=Mesh,
        pre_validators=_wave_based_pre_validators(tjunc, intersect),
        stages=_wave_based_stages(tjunc, intersect),
        final_validators=_wave_based_final_validators(tjunc, intersect),
        exporters=[
            ObjExporter(),
            # 3DM exporter consumes the OBJ produced by ObjExporter
            # and converts it to a Rhino 3DM using the existing converter.
            # Placed after ObjExporter so the .obj file is available on disk.
            ThreeDMExporter(),
            GmshGeoExporter(
                volume_name=volume_name,
                detect_cavities=detect_cavities,
                cavity_pitch=cavity_pitch,
                cavity_closing_iterations=cavity_closing_iterations,
            ),
        ],
        tolerances=Tolerances(),
    )


def wave_based_inspect_profile() -> SimulationProfile:
    """Inspect-only profile: same stages run (repairs still happen so each
    detector sees a clean mesh), but no geometry exporters are wired.

    The caller is expected to call ``write_issue_report(result, path)``
    on the returned ``PipelineResult`` to persist the diagnostic JSON.
    """
    tjunc = TJunctionsValidator()
    intersect = IntersectionsValidator()
    return SimulationProfile(
        name="wave_based_inspect",
        target_ir=Mesh,
        pre_validators=_wave_based_pre_validators(tjunc, intersect),
        stages=_wave_based_stages(tjunc, intersect, inspect=True),
        final_validators=_wave_based_final_validators(tjunc, intersect),
        exporters=[],
        tolerances=Tolerances(),
    )
