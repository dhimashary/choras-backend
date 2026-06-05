# Architecture Concern Report: Volume Detection (ACR)

ACR 1 — Volume detection

**Scope**

This ACR describes the repository's current approach for detecting enclosed
volumes (cavities) and producing face→volume (SurfaceLoop/Volume) mappings
for Gmsh `.geo` export. It summarizes the implementation, benefits,
drawbacks, defaults, and operational guidance for engineers and reviewers.

**Strategy (current implementation)**

- Global voxelization + labeling pipeline (implemented in `app/geometry/cavity_detector.py`).

- Steps:
  1. Triangulate each input polygon (prefer CDT via `app.utils.geometry_utils.triangulate_face_cdt_shapely`, fallback to fan-triangulation).
  2. Build a `trimesh.Trimesh` from the triangles and voxelize the entire surface at a single `pitch`.
  3. Invert occupancy to obtain empty voxels, pad the volume, and run a connected-component labeling (flood-fill).
  4. Treat the label touching the padded corner as `outside`; every other label is an enclosed cavity candidate.
  5. For each original face, probe `centroid ± normal * offset` to find which labeled region lies on each side and emit oriented `(face_index, sign)` lists for Gmsh SurfaceLoop orientation.
  6. Compute cavity volumes from voxel counts, sort by volume, and return `Cavity` objects with oriented face lists.

**Implementation locations**

- Detector logic: `app/geometry/cavity_detector.py`
- Exporter wiring & heuristics: `app/geometry/io/exporters/geo.py`
- Cavity dataclass & GEO exporter consumer: `app/services/geometry_export_service.py`

**Benefits**

- Robust to non-watertight / non-manifold input because detection operates on voxelized free-space rather than requiring a watertight solid.
- Simple and predictable: single global voxelization has fewer moving parts than multi-stage hybrids and simpler failure modes.
- Produces oriented face lists required by Gmsh (SurfaceLoop → Volume mapping) via centroid-normal probes.
- Tunable: `pitch` and `closing_iterations` let operators trade precision vs performance.
- CDT triangulation remains optional to improve triangulation quality when available.

**Drawbacks & Limitations**

- Voxel approximation: spatial resolution is limited by `pitch`; thin walls or narrow channels smaller than the pitch may leak or be lost.
- Face-to-cavity mapping uses centroid ± normal probing — a heuristic that can fail for non-planar, large, or concave faces.
- `trimesh` voxelization can still fail or be slow for very high-resolution (`pitch`) settings or pathological meshes (observed `max_iter exceeded` in remeshing steps).
- Morphological closing (`closing_iterations`) can alter topology (false merges) if overused.
- Not mathematically exact: for CAD-exact requirements consider CGAL Nef polyhedra or tetrahedralization-based methods (higher integration effort).
- Sensitivity to tuning: good defaults help, but some models require per-model adjustments.

**Current defaults**

- `cavity_pitch`: 0.05 (model units)
- `closing_iterations`: 0

The repository previously experimented with a hybrid coarse→local-refine detector; however the current checked-in code uses the global voxelization approach above. `GmshGeoExporter` computes diagonal-based tuning heuristics for hybrid/advanced modes when present, but the primary exported detector remains the global voxelizer unless explicitly changed.

**Operational guidance**

- If many small cavities are missed: decrease `cavity_pitch` (finer voxels) at the cost of memory/time.
- If voxelization errors or extreme runtimes occur: increase `cavity_pitch`, simplify or scale the mesh, or pre-process (repair/simplify) problematic geometry.
- To reduce false merges: set `closing_iterations=0` or smaller values.
- For exact topological correctness or CAD-grade results: integrate heavier kernels (CGAL Nef polyhedra or robust tetrahedralization + inside/outside labeling).


**Next actions / Improvements**

- Add unit tests targeting global-voxel edge cases (thin walls, tiny cavities, T-junctions).
- Optionally re-introduce a hybrid/local-refine mode behind an explicit flag and test its behavior; keep global voxelization as the default.
- Provide a small tuning guide and a CLI/utility to compute per-model heuristics automatically (exporter already computes diagonal-based heuristics).

**Authors / History**

- Implemented and documented by the engineering agent during `engd_project_2026_v2` branch work.

---

ACR 2 — Grid + CGAL-based volume mapping (reference C++ implementation)

**Summary / where it comes from**

The repository contains a C++ reference implementation `volume_detector.cpp` that
implements a more robust face→volume mapping using CGAL primitives, an AABB
tree, per-face constrained-Delaunay triangulation (CDT) in the face plane,
and a visibility-aware free-space grid. This section summarizes that approach
and how it contrasts with the global Python voxelizer.

**High-level steps (reference implementation)**

1. Read OBJ vertices and polygonal faces.
2. For each face: remove duplicate consecutive indices, compute a best-fit
   plane, project to 2D, run a constrained Delaunay triangulation (CDT), lift
   interior triangles back to 3D and collect interior probe/barycenter points.
3. Build a triangle list and an AABB tree for exact intersection and distance
   queries.
4. Build a free-space `Grid` covering the bbox padded by a margin; grid step
   = max_dim / target_resolution. Mark grid cells as free if their squared
   distance to the triangle mesh exceeds `clearance^2` (clearance = factor * step).
5. Label connected free-space components with BFS. During traversal, use
   AABB tree segment intersection tests so components are split by obstructions
   (visibility-aware labeling). Mark components touching the grid boundary as
   exterior.
6. Map faces to bounded volumes: for each face's interior probe points and a
   set of probe distance factors, probe along ±normal and find the nearest
   visible free-space component within a search radius. Components that are
   not marked exterior map to bounded volumes; assemble `volume -> faces` and
   `face -> volumes` mappings.
7. Detect per-volume manifoldness by counting undirected edges (edges should
   appear exactly twice for manifold volumes).
8. Export results to JSON and optionally write per-volume OBJ files.

**Benefits**

- More deterministic and robust: uses exact predicates (CGAL) and an AABB
  tree for reliable intersection and distance queries.
- Visibility-aware labeling (segment intersection) reduces false merges and
  better separates narrow passages compared to naive voxel-only flood-fill.
- Per-face CDT triangulation with best-fit planes yields reliable interior
  probe points for faces of arbitrary polygonal shape.
- Produces explicit `volume -> faces` and `face -> volumes` mappings and can
  detect manifoldness precisely.

**Drawbacks & Integration Cost**

- Heavy native dependency: requires CGAL and a C++ build toolchain (CMake,
  compiler) and introduces cross-platform packaging complexity.
- Higher implementation complexity and maintenance burden compared to the
  pure-Python voxelizer.
- Grid tuning still matters (resolution, clearance_factor, probe_factors,
  search radius) and affects runtime / memory; very large scenes can be
  expensive but the grid can be tuned coarser than pure-voxel approaches.
- Integration options: call the compiled binary from Python as a preprocessing
  step, or reimplement key ideas in Python (using CGAL bindings or alternate
  exact kernels) — both have trade-offs.

**When to use**

- Use the CGAL-based approach when you need higher robustness and correctness
  (CAD-grade), reliable manifoldness detection, or you have pathological
  geometries where voxelization fails. Keep the Python global voxelizer as a
  lightweight default for faster iterations.

**Integration recommendation**

- Provide the C++ tool as an optional, installable binary (e.g., `obj_volume_mapper`).
- Export the `volume -> faces` mapping as JSON and have the Python exporter
  consume it when present; fall back to in-Python voxel detection otherwise.

---



