"""Wiring smoke test: the new validator wrappers run on a small Mesh.

This is *not* a behaviour-preservation regression test (that comes with
the PR1 baseline-fixture run on `obj_to_gmsh_geo_precise_with_repair_pipeline`).
It only proves the wiring is sound: kernel re-exports load, the seven
validator wrappers instantiate, ``SimulationProfile.__post_init__`` accepts
their accepts-set, and ``detect()`` returns ``list[Issue]``.
"""
from __future__ import annotations

import logging

from app.geometry.context import Context
from app.geometry.ir import Face, Mesh, Vertex
from app.geometry.issues import Issue, IssueKind
from app.geometry.repairs import (
    CompactVerticesRepair,
    DeduplicateVerticesRepair,
    OrientFacesConsistentlyByAdjacencyRepair,
    RemoveDegenerateFacesRepair,
    SortVerticesDeterministicallyRepair,
)
from app.geometry.report import RepairResult
from app.geometry.tolerances import Tolerances
from app.geometry.validators import (
    BoundaryEdgesValidator,
    DegenerateFacesValidator,
    DuplicateVerticesValidator,
    IntersectionsValidator,
    NonPlanarFacesValidator,
    PossibleHolesValidator,
    TJunctionsValidator,
)


def _unit_quad() -> Mesh:
    """A single non-closed quad — enough to exercise every validator."""
    return Mesh(
        vertices=[
            Vertex(0.0, 0.0, 0.0),
            Vertex(1.0, 0.0, 0.0),
            Vertex(1.0, 1.0, 0.0),
            Vertex(0.0, 1.0, 0.0),
        ],
        faces=[Face(vertex_indices=[1, 2, 3, 4], group="g0", material=None)],
    )


def _ctx() -> Context:
    return Context(
        tolerances=Tolerances(),
        logger=logging.getLogger("test_smoke"),
        profile_name="smoke",
    )


def test_kernel_reexports_load() -> None:
    from app.geometry.kernel import (
        FaceRecord,
        classify_face_degeneracy,
        classify_face_planarity_m,
        mesh_from_legacy,
        mesh_to_legacy,
        newell_normal_from_points,
        triangulate_face_cdt_shapely,
    )
    assert FaceRecord is not None
    assert all(callable(f) for f in (
        classify_face_degeneracy,
        classify_face_planarity_m,
        mesh_from_legacy,
        mesh_to_legacy,
        newell_normal_from_points,
        triangulate_face_cdt_shapely,
    ))


def test_all_validators_return_issue_lists() -> None:
    mesh = _unit_quad()
    ctx = _ctx()
    validators = [
        DuplicateVerticesValidator(),
        DegenerateFacesValidator(),
        NonPlanarFacesValidator(),
        TJunctionsValidator(),
        IntersectionsValidator(),
        BoundaryEdgesValidator(),
        PossibleHolesValidator(),
    ]
    for v in validators:
        out = v.detect(mesh, ctx)
        assert isinstance(out, list)
        assert all(isinstance(i, Issue) for i in out)


def test_boundary_edges_finds_four_for_open_quad() -> None:
    mesh = _unit_quad()
    out = BoundaryEdgesValidator().detect(mesh, _ctx())
    # An isolated quad has exactly 4 boundary edges.
    assert len(out) == 4


# ---- Repair wiring ----------------------------------------------------------

def _quad_with_duplicate() -> Mesh:
    """Same quad, but vertex #5 is a near-duplicate of vertex #1."""
    return Mesh(
        vertices=[
            Vertex(0.0, 0.0, 0.0),
            Vertex(1.0, 0.0, 0.0),
            Vertex(1.0, 1.0, 0.0),
            Vertex(0.0, 1.0, 0.0),
            Vertex(1e-4, 1e-4, 0.0),   # duplicate of #1 within vertex_merge=1e-2
        ],
        faces=[Face(vertex_indices=[1, 2, 3, 4], group="g0", material=None)],
    )


def test_non_iterative_repairs_return_repair_results() -> None:
    """Each non-iterative repair must return (Mesh, RepairResult)."""
    ctx = _ctx()
    repairs = [
        DeduplicateVerticesRepair(),
        RemoveDegenerateFacesRepair(),
        SortVerticesDeterministicallyRepair(),
        CompactVerticesRepair(),
        OrientFacesConsistentlyByAdjacencyRepair(),
    ]
    mesh = _unit_quad()
    for r in repairs:
        out_mesh, res = r.apply(mesh, [], ctx)
        assert isinstance(out_mesh, Mesh)
        assert isinstance(res, RepairResult)
        assert res.step_name == r.name


def test_deduplicate_merges_near_duplicate() -> None:
    mesh = _quad_with_duplicate()
    issues = DuplicateVerticesValidator().detect(mesh, _ctx())
    assert len(issues) >= 1
    out_mesh, res = DeduplicateVerticesRepair().apply(mesh, issues, _ctx())
    assert len(out_mesh.vertices) == 4
    assert res.before_count == 5
    assert res.after_count == 4
    # All Issue.id values from PRE detection should be reported as affected.
    assert set(res.affected_ids) >= {i.id for i in issues if i.kind == IssueKind.DUPLICATE_VERTEX}


def test_compact_vertices_drops_unused() -> None:
    """Vertex #5 is unused; CompactVerticesRepair must drop it."""
    mesh = Mesh(
        vertices=[
            Vertex(0.0, 0.0, 0.0),
            Vertex(1.0, 0.0, 0.0),
            Vertex(1.0, 1.0, 0.0),
            Vertex(0.0, 1.0, 0.0),
            Vertex(5.0, 5.0, 5.0),    # not referenced by any face
        ],
        faces=[Face(vertex_indices=[1, 2, 3, 4], group="g0", material=None)],
    )
    out_mesh, res = CompactVerticesRepair().apply(mesh, [], _ctx())
    assert len(out_mesh.vertices) == 4
    assert res.details["removed_unused_vertices"] == 1


def test_wave_based_profile_constructs() -> None:
    """SimulationProfile.__post_init__ must accept the wave_based wiring."""
    from app.geometry.profiles.wave_based import wave_based_profile
    profile = wave_based_profile()
    assert profile.name == "wave_based"
    assert profile.target_ir.kind == "mesh"

