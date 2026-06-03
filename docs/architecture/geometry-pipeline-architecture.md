# Geometry Validation & Repair Pipeline — Architectural Design

> Companion document for the CHORAS backend geometry module.
> Audience: thesis reviewers and future maintainers.

## 1. Context

The CHORAS backend currently exposes an HTTP endpoint that accepts a 3D model
file (today: OBJ; soon: DXF, possibly STEP/IFC), validates and repairs it, and
hands the repaired geometry to a downstream room-acoustics simulation
(initially a wave-based solver). The processing currently lives in a single
service function (`map_to_3dm_and_geo`) which interleaves file I/O, database
persistence, format conversion, validation, repair, and reporting.

This document specifies the target architecture for that module, justifies
each decision against the architectural concerns raised during design review,
and records the trade-offs of each chosen alternative.

## 2. Architectural Concerns

The design must address the following concerns, each derived from a foreseen
extension of the system:

| ID  | Concern                                                                                |
| --- | -------------------------------------------------------------------------------------- |
| C1  | Support new input file formats (e.g. DXF) without rewriting the pipeline.              |
| C2  | Support new simulation methods (ray tracing, BEM, …) with different issue types.       |
| C3  | Allow a simulation backend to contribute its own validation rules.                     |
| C4  | Make it straightforward for a new developer to add a validator without confusion.      |
| C5  | Allow each simulation method to choose its own repair strategy.                        |
| C6  | Choose an implementation language / packaging strategy that is maintainable long-term. |

## 3. Chosen Architecture

The geometry module is structured as a **pipeline of pluggable strategies**
inside a **bounded, in-process module** (`app/geometry/`), accessed by the
Flask layer through a single application service. Concretely it combines:

- **Hexagonal / Ports-and-Adapters** for the outer boundary
  (Flask + DB are adapters; the geometry core is the hexagon).
- **Pipeline (Pipes & Filters)** for the inner processing flow.
- **Strategy + Registry** for importers, exporters, validators, and repair steps.
- **Tagged-union Intermediate Representation (IR)** so different geometry kinds
  (`Mesh`, `BRep`, …) can coexist without `Optional`-fields rot.
- **Profile (Policy Object)** to bundle a simulation method's required validators,
  repair plan, target IR, exporter, and tolerances.

### 3.1 Layered structure

```
app/
  services/
    geometry_service.py            # thin Flask-facing orchestrator (DB + HTTP)
  geometry/                        # bounded module — no Flask / SQLAlchemy imports
    __init__.py                    # public API: run_pipeline, Mesh, BRep, Issue, Profile
    ir.py                          # Mesh, BRep, PointCloud (tagged union)
    io/
      importers/{obj,dxf,rhino}.py
      exporters/{geo,msh}.py
      registry.py
    validators/                    # one file per validator
    repairs/                       # one file per repair step
    profiles/                      # wave_based.py, ray_tracing.py, ...
    converters/                    # IR ↔ IR adapters (e.g. brep_to_mesh)
    pipeline.py                    # run_pipeline(geom, profile)
    report.py
    tolerances.py
tests/geometry/                    # mirrors the package; pure, no Flask
```

### 3.2 Key abstractions

```python
class Geometry(Protocol):
    kind: ClassVar[str]   # discriminator: "mesh" | "brep" | "pointcloud"

@dataclass
class Mesh(Geometry):  kind = "mesh";       vertices: list[Vertex]; faces: list[Face]; ...
@dataclass
class BRep(Geometry):  kind = "brep";       curves: list[Curve];    surfaces: list[Surface]; ...

@dataclass(frozen=True)
class Issue:
    kind: IssueKind          # T_JUNCTION, INTERSECTION, NON_PLANAR, ...
    severity: Severity       # WARN | FATAL
    payload: dict

class Importer(Protocol):
    extensions: ClassVar[tuple[str, ...]]
    def load(self, path: Path) -> Geometry: ...

class Validator(Protocol):
    accepts: ClassVar[set[str]]   # IR kinds it can run on
    kind:    ClassVar[IssueKind]
    def detect(self, geom: Geometry, ctx: Context) -> list[Issue]: ...

class RepairStep(Protocol):
    handles: ClassVar[set[IssueKind]]
    def apply(self, geom: Geometry, issues: list[Issue], ctx: Context) -> RepairResult: ...

@dataclass
class Stage:
    name: str
    repairs: list[RepairStep]            # ordered
    post_validators: list[Validator]     # run after this stage's repairs
    fail_fast_on: set[IssueKind]         # if any kind appears here, abort

@dataclass
class SimulationProfile:
    name: str
    target_ir: type[Geometry]
    pre_validators:   list[Validator]    # run once on the imported geometry
    stages:           list[Stage]        # ordered repair-and-detect stages
    final_validators: list[Validator]    # run once after the last stage
    exporters:        list[Exporter]     # >= 0 outputs (e.g. .obj + .geo)
    tolerances:       Tolerances
```

`SimulationProfile.__post_init__` cross-checks every attached validator and
repair against `target_ir.kind`, so a misconfigured profile fails at construction
time rather than mid-pipeline.

### 3.3 Orchestration

```python
def run_pipeline(
    geom: Geometry,
    profile: SimulationProfile,
    output_path: Path,
    ctx: Context,
) -> PipelineResult:
    if geom.kind != profile.target_ir.kind:
        geom = ConverterRegistry.convert(geom, profile.target_ir)

    snapshots = [run_validators(geom, profile.pre_validators, ctx,
                                when=PRE, stage_name="")]
    repairs = RepairReport()

    for stage in profile.stages:
        geom, snap = run_stage(geom, stage, ctx, repairs, snapshots[-1].issues)
        snapshots.append(snap)
        # Per-stage fail_fast is enforced INSIDE run_stage (raises
        # PipelineFailFastError); the profile decides which kinds qualify.

    snapshots.append(run_validators(geom, profile.final_validators, ctx,
                                    when=FINAL, stage_name=""))

    for exporter in profile.exporters:
        target = getattr(exporter, "path_for", lambda p: p)(output_path)
        exporter.write(geom, target)

    return PipelineResult(geom, snapshots, repairs, str(output_path))
```

`geometry_service.py` is the only place that bridges this pipeline with
SQLAlchemy models and HTTP responses. Snapshot diffing
(`diff.diff_snapshots`) lives outside `run_pipeline` and is invoked by the
service when it builds the persisted report.

## 4. How Each Concern Is Addressed

### C1 — New input formats (e.g. DXF)

**Solution.** Each format has its own `Importer` registered by file extension.
DXF cannot reasonably be coerced into `Mesh`, so it loads into a different IR
variant (`BRep`). A profile that needs a `Mesh` declares it via
`target_ir = Mesh`; the pipeline calls a registered converter (`brep_to_mesh`)
automatically. The simulation code does **not** know DXF exists.

**Trade-off vs alternatives.**

- *Single universal `Mesh` IR with optional curve fields:* simpler at first,
  but every downstream function grows `if geom.curves is not None` checks and
  loses type safety. Rejected — long-term maintenance cost is much higher.
- *One mega-converter `to_mesh(any_format)`:* hides the cost of conversion and
  conflates parsing with tessellation. Rejected — pairwise converters are
  additive, individually testable, and skip-able when not needed.

### C2 — New simulation methods with different issue types

**Solution.** `IssueKind` is an open enum. Each `SimulationProfile` lists only
the validators it needs. A new solver provides a new profile in
`profiles/<name>.py`; nothing in the core pipeline changes.

**Trade-off vs alternatives.**

- *Hard-coded list of issues in the pipeline:* fastest to write, but every
  new solver requires editing the pipeline. Violates the Open/Closed
  Principle. Rejected.
- *Inheritance hierarchy of pipelines (one subclass per solver):* couples
  shared and solver-specific logic, makes mixing-and-matching hard. Rejected
  in favor of composition (profile + registry).

### C3 — Simulation backend contributes its own validation

**Solution.** A `Validator` is a Protocol; the simulation team can ship one
in their own module (or as a remote validator that calls their service) and
add it to their profile. The contract is `Geometry → list[Issue]`.

**Trade-off vs alternatives.**

- *Simulation does its own validation post-hoc, after the file is shipped:*
  duplicates work and forces the user to wait for a remote round-trip to
  learn about geometric problems. Rejected.
- *Tight integration via shared library imports:* couples release cadences.
  The Protocol-based seam keeps both sides loosely coupled.

### C4 — Adding a new validator without confusion

**Solution.** A validator is a single file in `validators/` that implements
`Validator`. Onboarding rule: *"copy an existing validator, change the
detection logic."* The discoverability is structural, not documented in
prose.

**Trade-off vs alternatives.**

- *Ad-hoc functions imported wherever needed (status quo):* fast to write,
  but call sites multiply across services and the order of operations
  becomes implicit. This is exactly the situation we are leaving.
- *Plugin discovery via entry points / decorators:* more magical, harder to
  trace in a debugger. Explicit registration in a profile is preferred for
  a single-team project.

### C5 — Different repair strategies per simulation

**Solution.** Each profile has its own ordered `repair_plan: list[RepairStep]`.
A repair step does not know which simulation invoked it. Iteration loops
(detect → repair → re-detect) live inside the step that owns them, so the
top-level pipeline stays linear.

**Trade-off vs alternatives.**

- *One global repair sequence:* simplest, but a wave-based solver and a ray
  tracer have genuinely different needs (e.g. T-junctions are fatal for FEM
  but irrelevant for ray tracing). Rejected.
- *Repair logic embedded inside validators:* couples detection and fix,
  making either reusable in isolation impossible. Rejected.

### C6 — Implementation language and packaging

**Solution.** Implement the geometry module in **Python**, in the **same
repository** as the backend, as a **bounded in-repo package** (`app/geometry/`)
with an enforced import boundary (no `app.*` imports inside it). When a
specific algorithm becomes a measured bottleneck, expose it as an in-process
C++ extension via `pybind11`. Defer extraction into a standalone pip package
until a second consumer appears or the API stabilises.

**Trade-off vs alternative 1: Rewrite in C++ as a separate REST service.**

| Dimension              | In-repo Python                | Separate C++/REST service     |
| ---------------------- | ----------------------------- | ----------------------------- |
| Integration cost       | None — direct function call   | HTTP, serialization, auth     |
| Failure modes          | Exceptions only               | Exceptions + timeouts + retries |
| Local debugging        | Single stack trace            | Logs across services          |
| Deployment             | One container                 | ≥ two containers + orchestration |
| Raw performance        | Slower (mitigated by NumPy / pybind11 hotspots) | Faster end-to-end |
| Access to CGAL         | Via `CGAL-swig-bindings`, `pygalmesh` | Native |
| Iteration speed        | High                          | Low (two repos, two CIs)      |
| Team fit (single team) | Good                          | Overhead not justified        |

The C++/REST option is rejected **for now** because none of its triggers
apply: there is one consumer, no measured performance bottleneck, and one
team. The architecture leaves this option open by isolating the geometry
core behind a stable API; a future migration would be mechanical.

**Trade-off vs alternative 2: Extract to a separate pip package immediately.**

| Dimension              | In-repo package            | Separate pip package         |
| ---------------------- | -------------------------- | ---------------------------- |
| Boundary enforcement   | Lint rule / convention     | Hard, enforced by packaging  |
| Iteration speed        | Single PR                  | Two PRs + version bump per change |
| Native dep management  | One place                  | Two places                   |
| Reusability            | Low (one repo)             | High (any consumer can `pip install`) |
| Release tooling needed | None                       | `pyproject.toml`, index, changelog |
| Cost of cross-cutting refactor | Single commit      | Coordinated release          |

A pip package is rejected **for now** because the geometry API is still
evolving and there is only one consumer. The in-repo package gives ≈ 90 % of
the maintainability benefit at ≈ 10 % of the cost. Phase 2 (lift into a real
package) becomes mechanical once the seam is in place.

## 5. Patterns Used (Catalogue)

| Concern                                  | Pattern                                          |
| ---------------------------------------- | ------------------------------------------------ |
| Internal data model decoupled from files | Intermediate Representation / Canonical Model    |
| Multiple IR variants                     | Algebraic Data Type (Tagged / Discriminated Union) |
| Pluggable importers / exporters          | Strategy + Registry (Plugin)                     |
| Pluggable validators / repair steps      | Strategy + Pipes-and-Filters                     |
| Ordered processing                       | Pipeline                                         |
| Per-simulation configuration             | Profile / Policy Object                          |
| Converting between IRs                   | Adapter + double-dispatch via converter registry |
| Web/DB layer kept out of core            | Hexagonal Architecture (Ports & Adapters)        |
| Bounded module                           | Modular Monolith / DDD Bounded Context           |
| Issues as first-class objects            | Notification pattern (Fowler)                    |
| Open to extension, closed to modification | Open/Closed Principle (SOLID)                  |

Concise umbrella name: **a hexagonal modular monolith with a strategy-based
pipeline over a tagged-union intermediate representation**.

## 6. Architecture-Level Alternatives Considered

Section 4 already justifies the chosen architecture against fine-grained
alternatives per concern. This section evaluates the **whole-system**
alternatives that were rejected, so the choice is auditable end-to-end.

### 6.1 Candidates

- **A1 — Status quo (chosen baseline to leave).**
  Procedural Python functions in `geometry_*_service.py`, called directly
  from a Flask service that also performs DB writes and file I/O.

- **A2 — In-repo Python module with pipeline + strategies (CHOSEN).**
  `app/geometry/` package, hexagonal boundary, IR + Profile + Strategy +
  Registry, in-process. Native hotspots optionally exposed via `pybind11`.

- **A3 — Separate Python pip package (same process).**
  Same architecture as A2, but lifted into its own repository / `pyproject.toml`
  and installed as a dependency.

- **A4 — In-process C++ extension (pybind11) under the same Python pipeline.**
  Pipeline orchestration stays in Python; algorithmic kernels (CGAL-backed)
  are compiled C++ exposed as a Python module.

- **A5 — Standalone C++ microservice with REST/gRPC API.**
  Geometry validation/repair runs in a separate container written in C++,
  using CGAL natively. CHORAS calls it over the network.

- **A6 — Standalone C++ microservice + message queue (async worker).**
  Same as A5, but invocations are queued (e.g. RabbitMQ/Redis) and the
  geometry worker is horizontally scalable.

- **A7 — Embedded third-party tool invocation (CLI shell-out).**
  Use an existing tool (e.g. MeshLab, gmsh, OpenSCAD) via subprocess for the
  whole pipeline; CHORAS only orchestrates.

### 6.2 Qualitative comparison

| Criterion                         | A1 status quo | A2 in-repo Py (chosen) | A3 pip pkg | A4 C++ in-process | A5 C++ REST | A6 C++ + queue | A7 CLI shell-out |
| --------------------------------- | ------------- | ---------------------- | ---------- | ----------------- | ----------- | -------------- | ---------------- |
| Iteration speed                   | High          | High                   | Medium     | Medium            | Low         | Low            | Medium           |
| Boundary enforcement              | None          | Convention + lint      | Hard       | Convention + lint | Hard        | Hard           | Hard             |
| Onboarding cost                   | Low           | Low                    | Low–Med    | Medium            | High        | High           | Low              |
| Performance (typical room model)  | OK            | OK                     | OK         | High              | High        | High           | Variable         |
| Access to CGAL                    | Indirect      | Indirect (bindings)    | Indirect   | Native            | Native      | Native         | Depends on tool  |
| Operational complexity            | Low           | Low                    | Low        | Low               | High        | Very high      | Low              |
| Failure modes                     | Exceptions    | Exceptions             | Exceptions | Exceptions + segfault | + network + timeouts | + queue + retries + DLQ | + non-zero exit + parsing |
| Reusability outside CHORAS        | None          | None                   | High       | None (yet)        | Any HTTP client | Any client | Any shell        |
| Fit for current team size (1)     | Bad (entropy) | Good                   | Acceptable | Acceptable        | Bad         | Bad            | Acceptable       |
| Path forward without rewrite      | —             | A3 → A4 → A5/A6        | A4 → A5/A6 | A5/A6             | —           | —              | Hard to evolve   |

### 6.3 Why a C++ rewrite (A4 / A5 / A6) is *not* chosen now

- **No measured bottleneck.** The current OBJ pipeline finishes in seconds for
  realistic room models. Rewriting for performance you don't need is a
  textbook premature optimization.
- **CGAL access does not require C++.** `CGAL-swig-bindings`, `pygalmesh`,
  `trimesh`, and `igl` cover the algorithms the design needs (segment–facet
  intersection, AABB queries, connected components, mesh repair primitives).
- **Operational tax is real.** A5/A6 add a second deploy unit, a contract,
  authentication, retries, observability across services, and integration
  tests that need both processes running. None of that buys CHORAS a
  capability it lacks today.
- **Reversibility.** A2 leaves the door open. The hexagonal seam means that
  swapping the Python core for a C++ extension (A4) or an out-of-process
  service (A5/A6) is a *replacement of the adapter*, not a rewrite of the
  callers. So choosing A2 now does **not** preclude A4/A5/A6 later.

The architecture-level decision is therefore: **adopt A2, with A4 reserved
for measured hotspots and A5/A6 reserved for the triggers in §8**.

### 6.4 Weighted decision matrix

The criteria and weights below reflect the **current** state of CHORAS:
single team, single consumer, evolving feature set, no measured performance
bottleneck. Re-running the matrix with different weights (see §6.5) shows
when the chosen option would change.

Scoring: **1 = poor, 3 = adequate, 5 = excellent.** Weights sum to 100.

| Criterion (weight)               | A1 | A2 | A3 | A4 | A5 | A6 | A7 |
| -------------------------------- | -- | -- | -- | -- | -- | -- | -- |
| Iteration speed (20)             | 4  | 5  | 3  | 3  | 2  | 2  | 3  |
| Maintainability / clarity (20)   | 1  | 5  | 5  | 4  | 3  | 3  | 2  |
| Extensibility (new format / solver) (15) | 1 | 5 | 5 | 5 | 4 | 4 | 1 |
| Operational simplicity (15)      | 5  | 5  | 5  | 4  | 2  | 1  | 4  |
| Performance headroom (10)        | 3  | 3  | 3  | 5  | 5  | 5  | 3  |
| Team / single-developer fit (10) | 2  | 5  | 4  | 3  | 1  | 1  | 3  |
| Risk of vendor / rewrite lock-in (5) | 2 | 5 | 5 | 4 | 3 | 3 | 2 |
| Reusability outside CHORAS (5)   | 1  | 2  | 5  | 2  | 5  | 5  | 4  |
| **Weighted total (out of 500)**  | **245** | **460** | **425** | **390** | **300** | **285** | **265** |

Computation, for transparency (weight × score, summed):

- **A1**: 4·20 + 1·20 + 1·15 + 5·15 + 3·10 + 2·10 + 2·5 + 1·5 = **245**
- **A2 (chosen)**: 5·20 + 5·20 + 5·15 + 5·15 + 3·10 + 5·10 + 5·5 + 2·5 = **460**
- **A3**: 3·20 + 5·20 + 5·15 + 5·15 + 3·10 + 4·10 + 5·5 + 5·5 = **425**
- **A4**: 3·20 + 4·20 + 5·15 + 4·15 + 5·10 + 3·10 + 4·5 + 2·5 = **390**
- **A5**: 2·20 + 3·20 + 4·15 + 2·15 + 5·10 + 1·10 + 3·5 + 5·5 = **300**
- **A6**: 2·20 + 3·20 + 4·15 + 1·15 + 5·10 + 1·10 + 3·5 + 5·5 = **285**
- **A7**: 3·20 + 2·20 + 1·15 + 4·15 + 3·10 + 3·10 + 2·5 + 4·5 = **265**

A2 wins clearly under the current weights. A3 is the closest contender and
becomes the natural successor once a second consumer appears (§8).

### 6.5 Sensitivity analysis (when would the answer flip?)

| If this weight changes…                                 | Then the winner becomes…                  | Triggering condition                          |
| ------------------------------------------------------- | ----------------------------------------- | --------------------------------------------- |
| Performance headroom rises from 10 → 30                 | **A4** (in-process C++ extension)         | Profiling shows a single function dominates request latency. |
| Reusability outside CHORAS rises from 5 → 20            | **A3** (pip package)                      | A second consumer (CLI, notebook, second service) materialises. |
| Operational simplicity drops from 15 → 5 *and* performance rises to 25 | **A5/A6** | Geometry workloads need GPU workers, batching, or independent scaling. |
| Iteration speed drops from 20 → 5                       | **A4** or **A5**                          | The module's API stabilises and changes become rare. |

The decision is therefore not "Python forever" — it is "Python now, because
under today's weights it dominates; the chosen architecture preserves the
option to migrate later without rewriting callers."

### 6.6 Why C++ in CHORAS specifically is awkward today

A common counter-question is *"why not write the geometry layer in C++ from
the start, since acoustics is performance-sensitive?"* Three concrete
reasons specific to CHORAS:

1. **The host application is Python (Flask).** Any C++ component must cross
   the language boundary either via FFI (A4) or the network (A5/A6). The
   first adds build complexity; the second adds an entire distributed-system
   surface to debug.
2. **The simulation backends themselves are not all C++.** Some are Python,
   some are external binaries. Centralising geometry in C++ does not remove
   Python from the request path; it only adds a language to maintain.
3. **The validation/repair logic is still under research.** It is being
   tuned (tolerances, repair order, report format) on a weekly cadence.
   Iterating on a Python implementation is significantly faster than on a
   C++ one, and the architecture lets the Python implementation be
   replaced *function by function* by C++ once each function stabilises.

## 7. Migration Strategy (Incremental, Low-Risk)

1. Define `Geometry`, `Mesh`, `Issue`, `RepairResult` dataclasses in
   `app/geometry/ir.py`. Derive them from current return shapes of
   `parse_obj_file` and `process_and_instantiate_faces`.
2. Wrap each detector in `geometry_inspection_service` as a `Validator`
   class — keep the existing function as the implementation.
3. Wrap each function in `geometry_repair_service` as a `RepairStep` class.
4. Replace `obj_to_gmsh_geo_precise_with_repair_pipeline` with
   `run_pipeline(mesh, WaveBasedProfile)`.
5. Move report aggregation out of repair functions; each step now returns a
   `RepairResult` that the pipeline aggregates.
6. Keep `geometry_service.py` thin: it only orchestrates DB rows + invokes
   the pipeline + persists the report.
7. Add an import-boundary test: `app.geometry.*` must not import from
   `app.models`, `app.db`, or `flask*`.
8. Move tolerances and magic numbers (`1e-4`, `1e-3`, `1e-9`, `200`, …) into
   `Tolerances` on the profile.

## 8. When to Revisit This Decision

Re-evaluate the language / packaging choice when **any** of the following
becomes true:

- A second consumer (CLI, notebook, another service) imports the geometry
  module → extract to a pip package.
- A specific algorithm is measured to dominate request latency, and Python /
  NumPy / CGAL bindings cannot close the gap → introduce a `pybind11`
  extension *for that function only*.
- A separate team takes ownership, or the module needs an independent release
  cadence → consider a separate repository.
- Geometry workloads need a fundamentally different scaling profile (e.g.
  GPU workers, long-running batch) → consider a separate service.

Until one of these triggers fires, the in-repo, in-process Python module is
the lowest-cost configuration that satisfies all six concerns.
