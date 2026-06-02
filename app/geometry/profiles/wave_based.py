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
from app.geometry.ir import Mesh
from app.geometry.profile import SimulationProfile, Stage
from app.geometry.repairs.deduplicate_vertices import DeduplicateVerticesRepair
from app.geometry.repairs.fix_t_junctions import FixTJunctionsIterativeRepair
from app.geometry.repairs.orient_outward import FlipFacesIfMajorityInwardRepair
from app.geometry.repairs.remove_degenerate_faces import RemoveDegenerateFacesRepair
from app.geometry.repairs.repair_intersections import (
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


def wave_based_profile(volume_name: str = "RoomVolume") -> SimulationProfile:
    tjunc_validator = TJunctionsValidator()
    intersect_validator = IntersectionsValidator()

    return SimulationProfile(
        name="wave_based",
        target_ir=Mesh,
        pre_validators=[
            DuplicateVerticesValidator(),
            DegenerateFacesValidator(),
            NonPlanarFacesValidator(),
            tjunc_validator,
            intersect_validator,
            BoundaryEdgesValidator(),
            PossibleHolesValidator(),
        ],
        stages=[
            Stage(
                name="dedup",
                repairs=[DeduplicateVerticesRepair()],
            ),
            Stage(
                name="degenerate",
                repairs=[RemoveDegenerateFacesRepair()],
            ),
            Stage(
                name="sort",
                repairs=[SortVerticesDeterministicallyRepair()],
            ),
            Stage(
                name="orient",
                repairs=[FlipFacesIfMajorityInwardRepair()],
            ),
            Stage(
                name="t_junctions",
                repairs=[FixTJunctionsIterativeRepair(detector=tjunc_validator)],
                post_validators=[tjunc_validator],
            ),
            Stage(
                name="intersections",
                repairs=[
                    TrimSegmentFaceIntersectionsRepair(detector=intersect_validator),
                    RepairPlcSingleSplitsRepair(detector=intersect_validator),
                ],
                post_validators=[intersect_validator],
            ),
            Stage(
                name="topology",
                post_validators=[BoundaryEdgesValidator(), PossibleHolesValidator()],
            ),
        ],
        final_validators=[
            NonPlanarFacesValidator(),
            tjunc_validator,
            intersect_validator,
            BoundaryEdgesValidator(),
            PossibleHolesValidator(),
        ],
        exporters=[
            ObjExporter(),
            GmshGeoExporter(volume_name=volume_name),
        ],
        tolerances=Tolerances(),
    )
