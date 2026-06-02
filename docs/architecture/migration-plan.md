# Geometry Refactor — Migration Plan

> Companion to `geometry-pipeline-architecture.md`.
> Source-of-truth analysis: `app/services/geometry_*.py` (7,300 lines) +
> `app/utils/geometry_*.py` (330 lines).

## 0. Decisions already taken

| # | Decision |
|---|---|
| 1 | Source-of-truth files: the seven `geometry_*` services + two `geometry_*` utils. |
| 2 | **Clean-up tolerances**: one canonical value per *concept*; not bit-identical to today. |
| 3 | No existing tests are a contract; we add a smoke fixture during PR1. |
| 4 | Output JSON shapes (`*_issues.json`, `*_report.json`) stay **identical** in PR1–3; new types live in-process and are translated back at the boundary. |
| 5 | Three PRs, mergeable independently, behaviour-preserving until PR3. |
| 6 | Iterative repairs call a separate `Validator.detect()` (DI). Convergence is verified per-fixture. |
| 7 | `SimulationProfile.__post_init__` asserts every validator/repair `accepts` the profile's `target_ir.kind`. |
| 8 | Two helpers merge into one kernel function only if signature + behaviour match; otherwise both kept with names that explain the difference. |

## 1. IssueKind reconciliation

The current skeleton (`app/geometry/issues.py`) has 8 kinds. The audit confirms 7 of them map cleanly to existing detectors; 1 has no detector today.

| Skeleton `IssueKind` | Existing detector | Action |
|---|---|---|
| `DUPLICATE_VERTEX` | `detect_duplicate_vertices` | wrap |
| `DEGENERATE_FACE` | `detect_degenerate_faces` | wrap |
| `NON_PLANAR_FACE` | `inspect_face_planarity_issues` | wrap |
| `T_JUNCTION` | `detect_t_junctions_from_facerecords_global_plc` | wrap |
| `INTERSECTION` | `detect_segment_facet_intersections_cdt` | wrap; **sub-kind** carried in `payload["sub_kind"]` ∈ {`segment_face_interior`, `endpoint_face_interior_touch`, `edge_touch`, `vertex_touch`, `multi_point_same_face`} |
| `BOUNDARY_EDGE` | `detect_boundary_edges` | wrap |
| `POSSIBLE_HOLE` | `detect_possible_holes_from_faces` | wrap |
| `INVERTED_NORMAL` | *no validator today* (`flip_all_faces_if_majority_inward` is repair-only, derives orientation per-call) | postpone — add validator only if a profile needs it |

> The existing `detect_faces_with_area_below_threshold` (inspection_service.py:140) is **not** a separate IssueKind — it's a softer threshold variant of `DEGENERATE_FACE`. Modeled as `payload["sub_kind"] = "small_area"`.

## 2. Canonical tolerance table

One numeric per concept. Inconsistencies in the current code are resolved as shown.

```python
# app/geometry/tolerances.py  (final values — to be applied in PR1)

@dataclass(frozen=True)
class Tolerances:
    # Length tolerances (metres)
    vertex_merge:        float = 1e-2     # merge coincident vertices
    planarity_warn:      float = 1e-4     # face planarity, warn-level
    planarity_fatal:     float = 1e-3     # face planarity, fatal-level
    planarity_split:     float = 1e-6     # planarity allowed during repair-time face splits
    t_junction:          float = 1e-8     # vertex-on-edge interior tolerance
    clipping:            float = 1e-9     # plane clipping & vertex reuse
    intersection_eps:    float = 1e-10    # Möller–Trumbore segment-triangle eps
    plc_offset:          float = 0.01     # endpoint offset distance for PLC workaround

    # Area tolerances (m²)
    degenerate_area:     float = 1e-12    # canonical "this face has no area"

    # Iteration caps
    max_t_junction_iters: int = 100
    max_plc_iters:        int = 20
    max_edge_split_passes: int = 10

    # Reporting caps
    max_reports:          int = 2000
```

**Inconsistencies resolved (from audit §D):**

| Concept | Current values | Canonical |
|---|---|---|
| Degenerate area | `1e-12` (area), `1e-16` (area²), `1e-18`, `1e-22` | **`1e-12` on area**; the `1e-16` site was using `area²`, will be converted at the call site. The 1e-18/1e-22 sites were defensive paranoia — collapsed to `1e-12`. |
| Vertex merge | `1e-2` (parsing), unspecified elsewhere | **`1e-2`** everywhere; expose as profile knob. |
| Max iters (PLC) | `20` in 3 places | one constant: `max_plc_iters = 20`. |
| Max reports | `200` (geometry_service), `2000` (inspection_service) | **`2000` core**; the 200-cap was a UI courtesy and lives in the boundary translator (§5), not in detection. |
| `conformize_tol = max(1e-7, tol)` | hardcoded fallback | dropped; T-junction tol is exactly `tolerances.t_junction`. |
| `tol_m=0.01` in collinear classifier | unchanged | **`0.01`** kept; tested at this value, no evidence it's wrong. Documented in `kernel/validation.py` so a future reader knows it is loose by design. |

> Acknowledged behaviour delta: the degenerate-area unification (`1e-12 / 1e-16 / 1e-18 / 1e-22 → 1e-12 m²` on area) may produce small numerical differences on near-degenerate edge cases. PR1 ships a smoke fixture (`example_models/MeasurementRoom.obj`) that exercises this path; any differences are recorded in the PR description.

## 3. Validator inventory (new `app/geometry/validators/`)

| File | Class | Wraps | `accepts` | `kind` |
|---|---|---|---|---|
| `duplicate_vertices.py` | `DuplicateVerticesValidator` | `detect_duplicate_vertices` | {"mesh"} | `DUPLICATE_VERTEX` |
| `degenerate_faces.py` | `DegenerateFacesValidator` | `detect_degenerate_faces` (+ small-area variant) | {"mesh"} | `DEGENERATE_FACE` |
| `non_planar_faces.py` | `NonPlanarFacesValidator` | `inspect_face_planarity_issues` | {"mesh"} | `NON_PLANAR_FACE` |
| `t_junctions.py` | `TJunctionsValidator` | `detect_t_junctions_from_facerecords_global_plc` | {"mesh"} | `T_JUNCTION` |
| `intersections.py` | `SegmentFacetIntersectionsValidator` | `detect_segment_facet_intersections_cdt` | {"mesh"} | `INTERSECTION` |
| `boundary_edges.py` | `BoundaryEdgesValidator` | `detect_boundary_edges` | {"mesh"} | `BOUNDARY_EDGE` |
| `possible_holes.py` | `PossibleHolesValidator` | `detect_possible_holes_from_faces` | {"mesh"} | `POSSIBLE_HOLE` |

PR1 strategy: each `Validator.detect()` calls the existing function unchanged, then converts its output via `Issue.create(...)`. **No detection logic is re-implemented.**

## 4. RepairStep inventory (new `app/geometry/repairs/`)

| File | Class | Wraps | Iterative | Detector injected |
|---|---|---|---|---|
| `deduplicate_vertices.py` | `DeduplicateVerticesRepair` | `deduplicate_vertices` | no | — |
| `remove_degenerate_faces.py` | `RemoveDegenerateFacesRepair` | `remove_degenerate_faces` | no | — |
| `sort_vertices.py` | `SortVerticesDeterministicallyRepair` | `sort_vertices_deterministically` | no | — |
| `orient_outward.py` | `FlipFacesIfMajorityInwardRepair` | `flip_all_faces_if_majority_inward` | no | — |
| `orient_consistent.py` | `OrientFacesConsistentlyByAdjacencyRepair` | `orient_faces_consistently_by_adjacency` | no | — |
| `fix_t_junctions.py` | `FixTJunctionsIterativeRepair` | `fix_t_junctions_iterative` | **yes** | `TJunctionsValidator` |
| `repair_intersections.py` | `TrimSegmentFaceIntersectionsRepair` | `trim_segment_face_intersections_iterative` | **yes** | `SegmentFacetIntersectionsValidator` |
| `repair_intersections.py` | `RepairPlcSingleSplitsRepair` | `repair_plc_single_splits_iterative` | **yes** | `SegmentFacetIntersectionsValidator` |
| `repair_intersections.py` | `RepairPlcByOffsetRepair` | `repair_plc_by_offset_iterative` | **yes** | `SegmentFacetIntersectionsValidator` |
| `compact_vertices.py` | `CompactVerticesRepair` | `compact_vertices_and_remove_unused` | no | — |

The three iterative classes already accept `detector: Validator` in their `__init__` (skeleton change applied earlier).

## 5. Boundary translator: `PipelineResult` → legacy JSON

The new `PipelineResult` carries `snapshots: list[ValidationSnapshot]` + `repairs: RepairReport`. The legacy outputs (`*_issues.json`, `*_report.json`) keep their exact shape (audit §E). Translation lives in **`app/services/geometry_service.py`** (the only place allowed to know both worlds).

| Legacy field | Source in `PipelineResult` |
|---|---|
| `issue_detection_report.<kind>` | `result.initial.issues` filtered by `IssueKind` |
| `topology_before_repair` | computed from input geometry (kept as-is via `geometry_diagnostic_log_service`) |
| `repair_report[i]` | `result.repairs.results[i]` — fields `repair_type`/`affected_count`/`details` map directly to `step_name`/`len(affected_ids)`/`details` |
| `revalidation_report.remaining_*` | `result.final.issues` filtered by `IssueKind` |
| `topology_after_repair` | computed from `result.geometry` |

The 200-sample UI cap is applied in this translator, not in detectors.

## 6. Diagnostic log service — verdict: **wrap, don't replace** (yet)

`geometry_diagnostic_log_service.py` does two distinct jobs:

1. **Topology counting** (`build_topology_report`, `find_free_edge_loops`) → moves into `app/geometry/kernel/topology.py`.
2. **JSON serialization in the legacy format** (`build_issue_detection_report`, `convert_*_to_standard_format`, `write_geometry_processing_report`) → stays as-is, called from the boundary translator (§5).

This preserves decision #4 (legacy shape) without polluting the core.

## 7. Parsing / Export → Importer / Exporter mapping

| Existing function | New class | File |
|---|---|---|
| `parse_obj_file` + `process_and_instantiate_faces` + `deduplicate_vertices` | `ObjImporter` | `app/geometry/io/importers/obj.py` |
| `extract_rhino_materials` | helper used by `Rhino3dmImporter` | `app/geometry/io/importers/rhino.py` |
| `export_processed_topology_to_gmsh_geo` | `GmshGeoExporter` | `app/geometry/io/exporters/geo.py` |
| `export_processed_topology_to_obj` | `ObjExporter` | `app/geometry/io/exporters/obj.py` |
| `export_geometry_issues_to_json` | stays in `geometry_service.py` (boundary, §5) | — |

Coordinate-axis flip (Y↔Z) lives in the importer/exporter, not in the IR. **The IR is always Z-up.**

## 8. Kernel inventory (final)

```
app/geometry/kernel/
├── data_types.py          # FaceRecord (moved from geometry_utils.py)
├── geometry_math.py       # _uedge, dot/cross/sub, area2, orient,
│                          # newell_normal_from_points, project_face_to_2d,
│                          # project_point_by_dropped_axis, clean_face_loop
├── validation.py          # classify_face_degeneracy,
│                          # classify_face_planarity_m,
│                          # planarity_deviation_m
├── triangulation.py       # triangulate_face_cdt_shapely
├── edges.py               # build_unique_edges, edge_face_map, half_edges
├── adjacency.py           # face_neighbors, connected_components
├── orientation.py         # face_normal, is_outward_facing
├── topology.py            # boundary_edges, is_manifold,
│                          # build_topology_report (from diagnostic log)
└── tolerances_math.py     # approx_equal, snap
```

Per decision #8, helpers merge only when signature + behaviour match. Sites where two near-duplicate helpers existed (audit §C) are flagged in the PR.

## 9. The three PRs

### PR1 — kernel + validators (no behaviour change)

**Adds.** `app/geometry/kernel/*`, `app/geometry/validators/*`, `app/geometry/issues.py` (already done), `app/geometry/tolerances.py` (already stub; add canonical defaults), `app/geometry/diff.py` (already done), `tests/geometry/test_smoke.py` (golden-file run on `MeasurementRoom.geo`).

**Changes.** `app/services/geometry_inspection_service.py`: each detector becomes a one-liner that delegates to the kernel function it formerly inlined. Old function signatures preserved.

**Doesn't change.** `geometry_service.py`, `geometry_repair_service.py`, all routes, all JSON output shapes.

**Contract at end of PR1.**
- `python -m compileall app/geometry` clean.
- Import-boundary test: `app/geometry/**.py` does not `import flask`, `app.db`, or `app.models`.
- Smoke: running `obj_to_gmsh_geo_precise_with_repair_pipeline` on `MeasurementRoom.obj` produces a `_report.json` byte-identical (modulo timestamps) to the pre-PR baseline checked in as a fixture.

### PR2 — repairs

**Adds.** `app/geometry/repairs/*` (11 classes, see §4). Iterative repairs receive `detector` via constructor.

**Changes.** `geometry_repair_service.py` is reduced to a thin shim importing the new classes (kept temporarily so external callers don't break mid-PR). Tolerance literals removed; values come from `Tolerances`.

**Doesn't change.** `geometry_service.py` orchestration, profile usage (no profile yet), JSON shapes, smoke fixture output.

**Contract at end of PR2.**
- Same smoke fixture passes.
- Convergence sanity: each iterative repair logs `iterations` and `affected_ids[]`; each terminates < `max_iters` on the fixture (we record the per-stage iteration counts for the thesis).
- `geometry_repair_service.py` is < 200 lines (just import re-exports).

### PR3 — pipeline + profile

**Adds.** `app/geometry/profiles/wave_based.py` (already drafted), `app/geometry/pipeline.py` implementations, `SimulationProfile.__post_init__` consistency check (decision #7).

**Changes.** `geometry_service.py`: replaces `obj_to_gmsh_geo_precise_with_repair_pipeline`'s body with `run_pipeline(mesh, wave_based_profile(), output_path, ctx)` + the legacy-JSON translator (§5).

**Removes.** `geometry_inspection_service.py` shim, `geometry_repair_service.py` shim, both `geometry_diagnostic_log_service.py` topology helpers (now in `kernel/topology.py`). Detector/repair *implementations* are gone from `app/services/`; only the boundary translator and JSON serializers remain.

**Contract at end of PR3.**
- Same smoke fixture passes.
- `wave_based_profile().__post_init__` rejects (with a clear error) any deliberately-broken profile in the test suite that lists a `BRep`-only validator with `target_ir=Mesh`.
- `geometry_service.py` < 400 lines, no detection or repair logic, only orchestration + DB + legacy JSON.

## 10. Resolved decisions (locked 2026-06-02)

1. **Wave-based stage order.** ✅ Keep current order (dedup → remove-degenerate → orient-by-majority → orient-by-adjacency → fix-T-junctions → trim/PLC repair → revalidate).
2. **Non-convex room assumption.** ⏭ Deferred. PR1–PR3 keep today's behaviour silently. Revisit if a fixture trips it.
3. **`plc_offset` absolute vs relative.** ✅ Keep absolute at **`0.01 m`**. Documented as "assumes typical room scale (≥ 1 m); not appropriate for sub-metre meshes." No behaviour change.
4. **`max_reports = 2000` cap.** ✅ When a validator hits the cap, every emitted Issue gets `payload["capped"] = True`, and one extra summary Issue carries `payload["actual_count_lower_bound"] = N` so downstream consumers can detect truncation.

## 11. Risk register (carried from audit §I)

Tracked in this doc rather than scattered as code TODOs:

- conformize_tol fallback (resolved in §2).
- collinear classifier 0.01 m (resolved in §2 — flagged as behaviour delta).
- `conformize_tol` fallback (resolved in §2).
- collinear classifier `0.01 m` (kept; not a behaviour change — noted in code comment).
- segment-triangle barycentric eps drift on near-vertex hits (no change in PR1; revisit if smoke shows flips).
- non-convex room assumption (deferred per §10 Q2).
- ordering coupling between trim / multi-hit-split / single-hit-split inside `repair_plc_single_splits_iterative` (preserve current order; documented in `repair_intersections.py`).
- `plc_offset` absolute (kept per §10 Q3; documented assumption).
- `max_reports` cap (resolved per §10 Q4).
- non-manifold edges silently skipped by `orient_faces_consistently_by_adjacency` (PR2 adds a `details["non_manifold_edges_skipped"]` to that step's `RepairResult`).
- `find_free_edge_loops` normalisation on near-collinear loops (no change; flagged for future test).

---

**End of plan.** Decisions are locked; PR1 can begin