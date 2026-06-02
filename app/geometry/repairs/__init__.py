"""Public exports for the ten repair-step wrappers."""
from app.geometry.repairs.compact_vertices import CompactVerticesRepair
from app.geometry.repairs.deduplicate_vertices import DeduplicateVerticesRepair
from app.geometry.repairs.fix_t_junctions import FixTJunctionsIterativeRepair
from app.geometry.repairs.orient_consistent import OrientFacesConsistentlyByAdjacencyRepair
from app.geometry.repairs.orient_outward import FlipFacesIfMajorityInwardRepair
from app.geometry.repairs.remove_degenerate_faces import RemoveDegenerateFacesRepair
from app.geometry.repairs.repair_intersections import (
    RepairPlcByOffsetRepair,
    RepairPlcSingleSplitsRepair,
    TrimSegmentFaceIntersectionsRepair,
)
from app.geometry.repairs.sort_vertices import SortVerticesDeterministicallyRepair

__all__ = [
    "CompactVerticesRepair",
    "DeduplicateVerticesRepair",
    "FixTJunctionsIterativeRepair",
    "FlipFacesIfMajorityInwardRepair",
    "OrientFacesConsistentlyByAdjacencyRepair",
    "RemoveDegenerateFacesRepair",
    "RepairPlcByOffsetRepair",
    "RepairPlcSingleSplitsRepair",
    "SortVerticesDeterministicallyRepair",
    "TrimSegmentFaceIntersectionsRepair",
]
