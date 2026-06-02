# Tech-debt log captured during PR1–PR3 refactor

Bugs, smells and surprising behaviour we noticed but **did not fix** to keep
the structural PRs minimal. Each entry: *where*, *what*, *suggested fix*.

---

## 1. `remove_degenerate_faces` never removes anything

* **Where:** [`app/services/geometry_repair_service.py`](../../app/services/geometry_repair_service.py) lines ~50–60.
* **What:** the function does
  ```python
  status = classify_face_degeneracy(f.verts, ...)
  if status == "fatal":
      ...
  ```
  but `classify_face_degeneracy` returns the **tuple** `(status, area2)`. The
  comparison `status == "fatal"` is therefore always False, so no face is
  ever removed despite `fatal_removed` being incremented in dead code.
* **Effect:** the live OBJ → `.geo` pipeline does *not* drop degenerate
  faces. Downstream Newell / planarity checks silently absorb them.
* **Suggested fix:** `status, _area2 = classify_face_degeneracy(...)`.
  Add a fixture test that injects a zero-area triangle and asserts removal.

## 2. `flip_all_faces_if_majority_inward` rule is geometrically inverted

* **Where:** [`app/services/geometry_repair_service.py`](../../app/services/geometry_repair_service.py) lines ~280–315.
* **What:** the comment says "outward if dotp < 0", but for a Newell normal
  pointing outward the vector from the face centroid *to the room centre*
  has a **negative** dot product with the normal → that already counts as
  outward, which is correct. **However**: `to_center` is computed as
  `room_center - centroid` (points *into* the room). For an outward-facing
  face the normal points *away* from the room, so `dot(n, to_center)` is
  negative. Code labels that as "outward" — that part is fine. The smell
  is the comment "Your rule:" which makes the invariant unclear, plus the
  decision uses a strict majority and leaves the `inward == outward` tie
  resolved as "kept" without explanation. Add unit tests around 50/50
  cases (e.g. a Möbius-like input) before refactoring.
* **Effect:** subtle — works for closed convex rooms; behaviour on
  non-convex rooms or rooms where the centroid sits outside is undefined.

## 3. Tolerance default for `degenerate_area` was 1e-18 in old `Tolerances`, ≠ legacy detector default 1e-16 ≠ Newell-area² scale

* **Where:** [`app/geometry/tolerances.py`](../../app/geometry/tolerances.py) (now 1e-12, canonical) vs `geometry_inspection_service.detect_degenerate_faces` default `fatal_area2_tol=1e-16`.
* **What:** four different "degenerate area" tolerances existed across the
  codebase (1e-12, 1e-16, 1e-18, 1e-22). Now unified to **1e-12** in
  `Tolerances`, but the legacy detector signature still defaults to 1e-16
  when called directly (i.e. *not* through the new validator).
* **Effect:** if any code path bypasses `Context.tolerances`, it sees a
  different threshold. No production path does today, but be alert.

## 4. T-junction "outer loop" in `FixTJunctionsIterativeRepair` is a no-op

* **Where:** [`app/geometry/repairs/fix_t_junctions.py`](../../app/geometry/repairs/fix_t_junctions.py).
* **What:** PR2 wraps `fix_t_junctions_iterative` (which already loops up
  to `max_iters` internally and returns a `changed_any` flag). The
  wrapper's own outer loop would only re-enter if the inner returned
  partial progress, but the inner already converges. Kept the wrapper
  loop for future detector swaps but it currently never iterates.
* **Suggested fix:** drop the `iterations=max_iters if changed else 0`
  pseudo-counter once the inner function exposes a real iteration count.

## 5. `repair_plc_single_splits_iterative` and `repair_plc_by_offset_iterative` return-tuple shape

* **Where:** [`app/services/geometry_repair_service.py`](../../app/services/geometry_repair_service.py) lines ~939, ~2880.
* **What:** docstrings imply they return `(faces, points, changed, diag)`,
  but actual code paths in some branches return only `(faces, points)`.
  PR2 wrappers defensively unpack; should be normalised.
* **Suggested fix:** make every return path emit the 4-tuple.

## 6. Coordinate-axis flips live deep inside parsing/export, not the IR

* **Where:** [`app/services/geometry_parsing_service.py`](../../app/services/geometry_parsing_service.py) `parse_obj_file` does
  `vertices.append((x, -z, y))` (SketchUp Y-up → Gmsh Z-up). Mirror flip in
  `export_processed_topology_to_obj`.
* **What:** the IR is supposed to be Z-up (migration plan §7). The flip
  is correctly contained in the importer/exporter but the *new*
  `ObjImporter` must replicate it; otherwise round-tripping through the
  new pipeline produces a Y/Z-swapped `.geo`.
* **Suggested fix:** add a single helper `app/geometry/io/_axis.py` with
  `obj_to_ir(p)` / `ir_to_obj(p)` and use it from every importer/exporter.

## 7. `Issue.create` payload includes raw 3-tuples that may be `numpy` floats

* **Where:** [`app/geometry/issues.py`](../../app/geometry/issues.py) `Issue.create` does `json.dumps(..., default=str)`.
* **What:** if a payload value is a `numpy.float64`, sha1-stable hashing
  works (str() converts), but the Issue's `payload` itself still holds
  numpy types. `RepairResult.details` then leak into JSON output where
  `default=str` *also* runs, but downstream consumers may choke on
  `"np.float64(0.1)"` strings.
* **Suggested fix:** coerce numpy → builtin floats in detector wrappers
  before payload construction.

## 10. Translator hardcodes per-kind logic — adding a validator means three edits

* **Where:** [`app/services/geometry_pipeline_translator.py`](../../app/services/geometry_pipeline_translator.py)
  `_normalise_elements` and `_kind_dict`.
* **What:** today, introducing a new `IssueKind` (e.g. `SELF_INTERSECTING_LOOP`)
  requires:
  1. adding the `IssueKind` enum value,
  2. writing a new validator that fills `payload`,
  3. **editing `_normalise_elements`** with another `if i.kind is …:` branch
     to translate that payload into `[{type, points}, ...]`,
  4. **editing `_kind_dict`** to add the new top-level key.
  Steps 3 and 4 break the open/closed principle — every new kind
  forces a change in a module that should be generic.
* **Effect:** translator drift. Easy to forget step 3, in which case
  the new kind shows up in JSON with empty `elements`.
* **Suggested fix:** push the shape concern *into the validator*.
  Each validator already builds a payload; let it also build the
  `elements` list directly via `cap_and_summarize(..., payload_of=...)`.
  Then the translator becomes a single loop:
  ```python
  def _kind_dict(issues):
      out = {kind_to_legacy_key(k): [] for k in IssueKind}
      for i in issues:
          if i.payload.get("summary"): continue
          out[kind_to_legacy_key(i.kind)].append({
              "elements": i.payload["elements"],
              "severity": _legacy_severity(i),
              "id": i.id,
          })
      return out
  ```
  with a small `kind_to_legacy_key: dict[IssueKind, str]` mapping
  (the only place that knows the frontend's exact JSON keys).
  T-junctions and intersections then build their `elements` list
  inside `t_junctions.py` / `intersections.py` instead of inside
  the translator. Adding a new validator no longer touches this file.

## 9. `_report.json` issue lists are uncapped — can be huge

* **Where:** [`app/services/geometry_service.py`](../../app/services/geometry_service.py) `obj_to_gmsh_geo_precise_with_repair_pipeline`
  (lines ~810–1158) and the new translator
  [`app/services/geometry_pipeline_translator.py`](../../app/services/geometry_pipeline_translator.py).
* **What:** the frontend-facing shape (per `MODEL_DATA_EXAMPLE.json`)
  is a flat dict keyed by issue kind, each value a list of
  `{elements, severity, id}` entries — no count/truncation marker.
  Today both the legacy path and the new translator emit **every**
  detected issue. For a very broken mesh (thousands of T-junctions or
  PLC violations) `_report.json` can balloon into multi-MB territory.
  Detector-level `max_reports=200` exists but is not applied
  consistently across all kinds.
* **Suggested fix:** cap each kind at e.g. **100 entries** inside
  `_kind_dict` and surface the truncation. Two compatible options:
  1. add a sibling top-level key, e.g. `_truncation: {"T-junctions":
     {total: 1234, shown: 100}, ...}` — frontend ignores until it
     learns about it; or
  2. tail-append a single `{summary: true, total: N}` entry inside
     each capped list — frontend can filter by `summary`.
  Also ensure the cap is consistent with `Tolerances.max_reports`
  rather than a hardcoded constant.

## 11. `SmallFacesValidator` exists but is not wired into any profile

* **Where:** [`app/geometry/validators/small_faces.py`](../../app/geometry/validators/small_faces.py),
  new `IssueKind.SMALL_FACE`, new `Tolerances.small_face_max_dim` (0.10 m).
* **What:** acoustic wave-based solvers degrade when the mesh contains
  faces much smaller than the wavelength of interest. Faces with
  bounding-box max-dimension < 10 cm are almost always modelling
  artefacts or unintended slivers and should be flagged. The validator
  is implemented but **not** added to `wave_based_profile.pre_validators`
  / `final_validators` because:
  1. the translator (tech-debt #10) hardcodes per-kind keys in
     `_kind_dict`, so adding `SMALL_FACE` would silently drop the
     issues from `_report.json`;
  2. there is no repair step yet — flagged faces would just be reported.
* **Suggested fix:**
  1. resolve tech-debt #10 first (push elements-shaping into validators
     so `_kind_dict` is generic), then
  2. add `SmallFacesValidator()` to `wave_based_profile.pre_validators`
     and `final_validators`,
  3. decide on a repair policy: drop the face, merge with neighbour, or
     just warn. For now WARN-only is sensible.
* **Effect:** today these faces silently survive into the `.geo` and
  trigger CFL / dispersion issues at simulation time.

## 8. `clean_face_loop` swallows degenerate loops silently

* **Where:** [`app/services/geometry_parsing_service.py`](../../app/services/geometry_parsing_service.py) `process_and_instantiate_faces` calls
  `clean_face_loop(mapped)` and accepts whatever comes back, even an
  empty list. There's an `if not sub_faces:` log but the result is still
  appended downstream.
* **Effect:** an OBJ with a duplicate-vertex face produces a `FaceRecord`
  with `verts=[]` which then crashes the kernel triangulation.
* **Suggested fix:** drop empty face loops in the importer.
