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

The repository previously experimented with a hybrid coarse→local-refine detector; the global voxelization approach above is now the **fallback** detector. As of ACR 3, the default exported detector is the native multi-scale shell-based C++ tool (`detection_mode="native"`), which automatically falls back to this global voxelizer when the binary is unavailable or fails.

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

ACR 3 — Multi-scale shell-based detection + Python↔C++ subprocess bridge (current native default)

**Status**

Implemented and wired as the **default** detection path. `GmshGeoExporter`
now uses `detection_mode="native"` by default, which calls the compiled
C++ detector and *automatically falls back* to the Python voxel detector
(ACR 1) when the binary is unavailable or fails.

**Motivation — why the previous strategies were not enough**

- The global voxelizer (ACR 1) and the single global grid (ACR 2) both use
  **one cell size for the whole model**: `step = max_dim / target_resolution`.
- A scene with a large room *and* small furniture cavities is multi-scale.
  If `step` is large enough to keep the room cheap, any cavity whose interior
  half-width is below `clearance_factor * step` produces **zero free cells**
  and is never discovered. If `step` is small enough for the furniture, the
  room's grid becomes `O(resolution³)` and explodes in time/memory.
- Increasing probe factors does **not** fix this: probes only change how far
  off a face surface we sample an *already-built* grid; they cannot recover a
  volume that has no free cells.

**Strategy (current implementation)**

Drive detection from **mesh connectivity**, not from a global free-space grid:

1. **Shell extraction** — split the mesh into connected surface shells using
   shared-edge adjacency (`UndirectedEdge` BFS). Furniture that is separate
   geometry from the room walls becomes its own shell automatically.
   (`extract_face_shells`)
2. **Per-shell local grid** — for each shell, build a free-space grid whose
   `step` is relative to **that shell's own bounding box**, then run the
   existing ACR 2 visibility-aware labeling on it. Small shells get a fine
   grid; the big room gets a coarse one. Each shell's cost is bounded by its
   own `target_resolution`, so the room never forces a globally fine grid.
   (`detect_volumes_multiscale`)
3. **Shared AABB tree** — the full-mesh CGAL AABB tree is used for distance
   and visibility queries inside every local grid, so neighbouring geometry
   still blocks leaks correctly.
4. **Boundary = surrounding air** — a local free-space component touching the
   local box boundary is the room air / true exterior and is ignored; a
   component fully enclosed by the shell becomes a bounded volume. Global
   volume ids are allocated lazily, so regions no shell face bounds never
   create spurious empty volumes.
5. **Min-shell-size filter** — shells whose bbox diagonal is below
   `min_shell_diag_frac` (default 1%) of the whole-model diagonal are skipped,
   filtering loose triangles / decorative slivers. Set to 0 to disable.
6. Orientation sign per `(volume, face)` and per-volume manifoldness are
   emitted exactly as in ACR 2.

**Input contract — mesh IR over JSON (not OBJ)**

The C++ tool now reads the Python mesh IR directly via a small strict JSON
reader, in addition to still accepting OBJ for standalone debugging
(dispatched by file extension in `read_mesh`):

```json
{
  "vertices": [[x, y, z], ...],
  "faces":    [[i0, i1, i2, ...], ...]   // 0-based indices into vertices
}
```

Face order equals the Python `faces` list order, so the C++ `face_id` maps
back to the Python face index with no lookup table.

**Python↔C++ connection — subprocess + temp files**

- The bridge (`app/geometry/volume_detector_bridge.py`) serializes the IR to
  a temp `mesh.json`, runs `bin/volume_detector mesh.json volumes.json` via
  `subprocess`, parses the JSON, and converts it to `Cavity` objects.
 - Chosen over pybind11 / ctypes deliberately: the subprocess bridge avoids
   tight ABI coupling and keeps native logic isolated. In earlier drafts the
   binary was optional, but the current production policy requires the native
   binary be built and available; failures should be surfaced rather than
   silently falling back.
- Appropriate because detection runs once per export (not a hot loop) and the
  exchanged data is small.

**Implementation locations**

- Native detector: `volume_detector.cpp` (repo root)
- Build: `native/CMakeLists.txt`, `native/build.sh` → `bin/volume_detector`
- Bridge: `app/geometry/volume_detector_bridge.py`
- Exporter wiring (`detection_mode`): `app/geometry/io/exporters/geo.py`
- Tests (no binary needed): `tests/test_volume_detector_bridge.py`

**Benefits**

- Resolves genuine multi-scale scenes (big room + small furniture) that no
  single-global-grid method can.
- Per-shell cost is bounded by the shell's own resolution, not the model's
  largest dimension.
- Inherits ACR 2 robustness (exact CGAL predicates, visibility-aware
  labeling, manifoldness).
- Optional and self-healing: missing/failed binary degrades to voxel mode.

**Drawbacks & Limitations**

- Total cost scales with the **number of shells** (≈ shells × resolution³
  distance queries). Models with very many separate pieces do more total work
  than one coarse grid; mitigated by `min_shell_diag_frac`.
- Assumes the relevant cavity boundary is a single connected shell. A cavity
  enclosed by *several disconnected* shells (e.g. a lid that is separate
  geometry resting on a box) may be split across shells; this is a known edge
  case not yet handled.
- Still grid-based, not analytically exact — sub-`step` features inside a
  shell can be missed, though the shell-relative `step` makes this far rarer.
- Adds a native build dependency (CGAL + toolchain) for the default path; the
  Python fallback keeps the system runnable without it.

**Current defaults (`MultiScaleParams` in `volume_detector.cpp`)**

- `target_resolution`: 64 (per shell)
- `clearance_factor`: 0.16
- `probe_factors`: {0.18, 0.30, 0.45, 0.60}
- `component_search_radius_cells`: 4
- `bbox_inflate_frac`: 0.06
- `min_shell_diag_frac`: 0.01

> Note: these are compiled-in C++ defaults; the Python bridge cannot yet tune
> them per call (see "Smells / next actions").

**Operational guidance**

- Cavities missed inside a shell: raise `target_resolution` or lower
  `clearance_factor`.
- Stray fragments creating noise volumes: raise `min_shell_diag_frac`.
 - Force the legacy path: construct `GmshGeoExporter(detection_mode="voxel")`.
 - Binary not built: the exporter will raise an error; build with
  `./app/geometry/volume_detection/build.sh` to enable the native path.

**Authors / History**

- Multi-scale shell strategy, mesh-IR JSON input, and subprocess bridge added
  during `engd_project_2026_v2` branch work. Supersedes ACR 2's single global
  grid as the recommended/default native path.

---



