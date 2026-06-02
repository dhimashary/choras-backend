"""End-to-end pipeline test on a synthetic closed cube.

A closed unit cube is the smallest input that exercises:
  * the validators (most return empty for a clean cube),
  * the repair stages (no-ops on a clean cube — stages still execute),
  * the GmshGeoExporter (writes a real .geo file).

This test is *not* a behaviour-preservation regression against
geometry_service.py — that requires a baseline-fixture compare (deferred).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from app.geometry.context import Context
from app.geometry.ir import Face, Mesh, Vertex
from app.geometry.issues import DetectionStage
from app.geometry.pipeline import run_pipeline
from app.geometry.profiles.wave_based import wave_based_profile
from app.geometry.report import PipelineResult
from app.services.geometry_pipeline_translator import (
    issue_detection_report_from_snapshot,
    repair_report_from_pipeline,
    revalidation_report_from_snapshot,
    to_legacy_processing_report,
)


def _unit_cube() -> Mesh:
    """A closed, watertight unit cube. 8 vertices, 6 quad faces."""
    v = [
        Vertex(0.0, 0.0, 0.0),  # 1
        Vertex(1.0, 0.0, 0.0),  # 2
        Vertex(1.0, 1.0, 0.0),  # 3
        Vertex(0.0, 1.0, 0.0),  # 4
        Vertex(0.0, 0.0, 1.0),  # 5
        Vertex(1.0, 0.0, 1.0),  # 6
        Vertex(1.0, 1.0, 1.0),  # 7
        Vertex(0.0, 1.0, 1.0),  # 8
    ]
    # All face windings are CCW from outside (outward-pointing normals).
    faces = [
        Face([1, 4, 3, 2], group="bottom", material="floor"),  # z=0
        Face([5, 6, 7, 8], group="top",    material="ceiling"),  # z=1
        Face([1, 2, 6, 5], group="front",  material="wall"),     # y=0
        Face([2, 3, 7, 6], group="right",  material="wall"),     # x=1
        Face([3, 4, 8, 7], group="back",   material="wall"),     # y=1
        Face([4, 1, 5, 8], group="left",   material="wall"),     # x=0
    ]
    return Mesh(
        vertices=v,
        faces=faces,
        metadata={"room_center": (0.5, 0.5, 0.5)},
    )


def _ctx() -> Context:
    from app.geometry.tolerances import Tolerances
    return Context(
        tolerances=Tolerances(),
        logger=logging.getLogger("test_pipeline"),
        profile_name="wave_based",
    )


def test_pipeline_runs_on_unit_cube(tmp_path: Path) -> None:
    profile = wave_based_profile()
    out = tmp_path / "cube.geo"
    result = run_pipeline(_unit_cube(), profile, out, _ctx())

    assert isinstance(result, PipelineResult)
    assert out.exists()
    assert out.stat().st_size > 0

    # Snapshots: PRE + 1 per stage + FINAL.
    expected_snapshots = 1 + len(profile.stages) + 1
    assert len(result.snapshots) == expected_snapshots
    assert result.snapshots[0].when is DetectionStage.PRE
    assert result.snapshots[-1].when is DetectionStage.FINAL


def test_pipeline_clean_cube_finds_no_issues_at_final(tmp_path: Path) -> None:
    profile = wave_based_profile()
    result = run_pipeline(_unit_cube(), profile, tmp_path / "cube.geo", _ctx())
    final = result.final
    assert final is not None
    # A closed unit cube should have no T-junctions, no intersections,
    # no boundary edges, no possible holes after the pipeline.
    from app.geometry.issues import IssueKind
    fatal_kinds = {
        IssueKind.T_JUNCTION,
        IssueKind.INTERSECTION,
        IssueKind.BOUNDARY_EDGE,
        IssueKind.POSSIBLE_HOLE,
    }
    fatal = [i for i in final.issues if i.kind in fatal_kinds]
    assert fatal == [], f"Unexpected final-stage issues on clean cube: {fatal}"


def test_translator_produces_legacy_shape(tmp_path: Path) -> None:
    profile = wave_based_profile()
    result = run_pipeline(_unit_cube(), profile, tmp_path / "cube.geo", _ctx())

    issue_report = issue_detection_report_from_snapshot(result.initial)
    # Each kind is a flat list (no count/wrapper).
    expected_keys = {"duplicate_vertices", "non_coplanar_faces", "T-junctions",
                     "possible_holes", "boundary_edges", "degenerate_faces",
                     "intersections"}
    assert set(issue_report.keys()) == expected_keys
    for k, v in issue_report.items():
        assert isinstance(v, list), f"{k} must be a list"
        for entry in v:
            assert set(entry.keys()) >= {"elements", "severity", "id"}
            assert isinstance(entry["elements"], list)
            for el in entry["elements"]:
                assert el["type"] in {"vertex", "edge", "face"}
                assert "points" in el
            assert entry["severity"] in {"high", "medium", "low"}
            assert isinstance(entry["id"], str) and entry["id"]

    revalidation = revalidation_report_from_snapshot(result.final)
    assert set(revalidation.keys()) == expected_keys

    repair_legacy = repair_report_from_pipeline(result)
    assert isinstance(repair_legacy, list)
    for entry in repair_legacy:
        for key in ("repair_type", "affected_count", "before", "after", "details"):
            assert key in entry

    full = to_legacy_processing_report(
        result,
        input_path="synthetic://cube",
        output_path=str(tmp_path / "cube.geo"),
        topology_before={"vertex_count": 8, "face_count": 6},
        topology_after={"vertex_count": len(result.geometry.vertices),
                        "face_count": len(result.geometry.faces)},
    )
    for key in ("input_obj", "output_repaired_obj", "topology_before_repair",
                "issue_detection_report", "repair_report", "revalidation_report"):
        assert key in full
    assert json.dumps(full, default=str)
