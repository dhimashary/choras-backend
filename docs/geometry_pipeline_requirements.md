# Geometry Validation & Repair Pipeline – Requirements

Derived from the architectural concerns around the current monolithic geometry
pipeline in CHORAS:

1. Support for additional input formats beyond OBJ (e.g. DXF, IFC).
2. Different simulation methods having different geometry requirements.
3. External simulation methods owning their own validation rules.
4. Ease of adding new validators without confusing the next developer.
5. Different simulation methods needing different repair strategies.
6. Technology choice (Python vs C++/CGAL) and integration cost.

These concerns surface **both** Functional Requirements (what the system must
do) and Non-Functional Requirements (how well the system must do it). NFRs
dominate, because most concerns are about extensibility, maintainability, and
interoperability rather than new user-visible features.

---

## Functional Requirements (FR)

| ID    | Stakeholder Needs                                                                                       | Priority | Description                                                                                                                                                                |
| ----- | ------------------------------------------------------------------------------------------------------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| FR-01 | Acoustic engineer wants to upload geometry in multiple formats.                                          | High     | The system shall accept geometry input in OBJ, DXF, and 3DM formats and convert each to a single canonical internal geometry representation before validation.            |
| FR-02 | Researcher wants to run the same model through different simulation methods.                             | High     | The system shall select a simulation-specific *validation/repair profile* at runtime based on the chosen simulation method (e.g. wave-based, geometric acoustics).        |
| FR-03 | Developer wants to add a new validator without rewriting the pipeline.                                   | High     | The system shall expose a validator plugin interface so a new validator can be registered by ID and attached to one or more profiles without modifying orchestrator code. |
| FR-04 | Developer wants to add a new repair strategy without rewriting the pipeline.                             | High     | The system shall expose a repair plugin interface so a new repair operation can be registered and selectively enabled per profile.                                        |
| FR-05 | Acoustic engineer wants a clear list of issues found in their model.                                     | High     | The system shall produce a normalized issue report with stable schema fields: `id`, `type`, `severity`, `elements`, `details`, `detector`, `tolerance`.                   |
| FR-06 | Acoustic engineer wants to know what was automatically fixed.                                            | High     | The system shall produce a normalized repair report listing each applied repair, affected element count, and before/after metrics.                                        |
| FR-07 | External simulation engine owner wants CHORAS to invoke their validator.                                 | Medium   | The system shall allow validators to be implemented as out-of-process services (e.g. REST/gRPC), invoked through the same plugin interface as in-process validators.      |
| FR-08 | Acoustic engineer wants inspection-only runs (no auto-repair).                                           | High     | The system shall support an inspect-only mode that runs detectors but skips all repair steps, returning only the issue report.                                            |
| FR-09 | Developer wants reproducible iterative repair (e.g. T-junction, PLC).                                    | Medium   | The system shall support iterative repair steps that re-run their corresponding detector until convergence or a configurable iteration cap.                               |
| FR-10 | Simulation method requires a specific output mesh format.                                                | High     | The system shall produce simulation-ready artifacts (`.geo`, `.msh`, processed OBJ) according to the active profile’s exporter configuration.                             |
| FR-11 | Operator wants to audit what happened to a model.                                                        | Medium   | The system shall persist the full processing report (input → issues → repairs → revalidation → outputs) keyed to the geometry/task ID.                                    |
| FR-12 | Developer wants to wire a CGAL/C++ kernel for heavy operations.                                          | Medium   | The system shall route designated geometry operations to an external geometry engine through a stable adapter, returning results in the canonical issue/repair schema.    |

---

## Non-Functional Requirements (NFR)

ISO/IEC 25010 quality attributes used: Functional Suitability, Maintainability,
Compatibility, Reliability, Performance Efficiency, Portability, Security.

| ID     | Priority | Description                                                                                                                                                            | Quality Attribute (ISO 25010)         | Acceptance Criteria                                                                                                                                                                                                |
| ------ | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| NFR-01 | High     | The pipeline shall be extensible to new input formats without modifying validator or repair code.                                                                      | Maintainability – Modifiability       | Adding a new format adapter (e.g. IFC) requires changes only inside the importer/adapter module and a single registration entry; no edits to validator, repair, or exporter modules. Verified by code review.    |
| NFR-02 | High     | The pipeline shall be extensible to new validation profiles through configuration, not code branching.                                                              | Maintainability – Modifiability       | Adding a new validation profile adds exactly one profile definition and zero changes to the pipeline runner. Verified by adding a sample profile in CI without touching `pipeline.py`.                             |
| NFR-03 | High     | The pipeline shall be extensible to new validators and repair operations via a documented plugin interface.                                                            | Maintainability – Reusability         | A new validator/repair can be added by implementing the documented interface and registering it; the orchestrator discovers it without manual wiring. Verified by adding a no-op plugin in tests.                 |
| NFR-04 | High     | All validators (in-process or external) shall produce issues in a single canonical schema.                                                                             | Compatibility – Interoperability      | 100% of issues emitted by any validator validate against the published JSON Schema. Verified by schema validation test on each detector’s output.                                                                 |
| NFR-05 | High     | The internal geometry representation shall be the single source of truth; no validator or repair shall depend on the original file format.                            | Maintainability – Modularity          | Static analysis shows zero imports of format-specific parsers (`obj`, `dxf`, `rhino3dm`) inside `validators/` and `repairs/` packages. Verified by an import-lint rule in CI.                                     |
| NFR-06 | High     | A new developer shall be able to add a validator by following documentation only.                                                                                      | Maintainability – Analysability        | A new contributor can add a validator end-to-end (code + test + registration) in ≤ 1 working day, using only the developer guide. Verified by onboarding dry-run.                                                 |
| NFR-07 | Medium   | The pipeline shall isolate failures of individual validators/repairs so one failure does not abort the entire run.                                                     | Reliability – Fault Tolerance         | When a single plugin raises, the run completes with the failure recorded in the report under `errors[]` and other steps still execute. Verified by fault-injection tests.                                         |
| NFR-08 | Medium   | The pipeline shall be deterministic for a given input + profile + tolerance set.                                                                                       | Reliability – Maturity                | Re-running the same input/profile produces byte-identical issue and repair reports (modulo timestamps). Exceptions are allowed for external or explicitly non-deterministic plugins—such steps must record run metadata (seed, plugin version) and are exempt from strict byte-identical checks. Verified by golden-file tests and contract tests that allow recorded nondeterminism.                                                                            |
| NFR-09 | Medium   | The pipeline shall support running heavy geometry operations out-of-process (e.g. C++/CGAL service) without changing caller code.                                      | Portability – Adaptability            | Switching a step between in-process and out-of-process implementations requires only a config change; the orchestrator and report shape remain identical. Verified by integration test using both implementations. |
| NFR-10 | Medium   | The pipeline shall complete validation+repair for a typical room model (≤ 5 000 faces) within an acceptable time budget.                                               | Performance Efficiency – Time Behaviour | P95 end-to-end runtime ≤ 30 s for the wave-based profile on the reference model on the standard worker. Verified by performance regression test.                                                                  |
| NFR-11 | Medium   | The plugin interface shall be versioned to avoid breaking external simulation engines that integrate with CHORAS.                                                      | Compatibility – Co-existence          | Issue/repair schema and plugin contract carry an explicit `schemaVersion`; older minor versions remain accepted for ≥ 2 releases. Verified by contract test against pinned schema versions.                       |
| NFR-12 | Medium   | The system shall log enough diagnostic information to reproduce any failed run.                                                                                        | Maintainability – Testability         | Each run logs: profile name, tolerance set, plugin versions, input hash, ordered list of executed steps, per-step duration. Verified by inspecting log output of a sample run.                                    |
| NFR-13 | Low      | External validation/repair services shall be invoked over a secure, authenticated channel.                                                                             | Security – Authenticity / Confidentiality | All out-of-process geometry-engine calls use TLS and a signed token; unauthenticated requests are rejected. Verified by security test.                                                                            |
| NFR-14 | Medium   | The pipeline shall handle malformed or partially invalid input without crashing the worker.                                                                            | Reliability – Recoverability          | Given a corrupt OBJ/DXF file, the run terminates with a structured error response and the worker remains available. Verified by fuzz/negative test suite.                                                         |
| NFR-15 | Low      | The codebase organization shall make the boundary between *orchestration*, *domain (geometry rules)*, and *I/O* explicit.                                              | Maintainability – Modularity          | Folder layout enforces three layers (`pipeline/`, `domain/`, `io/`), and the domain layer has no Flask, DB, or filesystem imports. Verified by an architecture-fitness test (e.g. `import-linter`).                |
| NFR-16 | High     | The pipeline shall report any unresolved issues remaining after processing, including the issue type and coordinates of affected geometry.                             | Reliability – Fault Tolerance         | Pipeline output includes an `unresolved_issues` list; each entry contains an `id`, `kind`, `severity`, and `elements` with coordinates. The run completes and returns a structured status indicating unresolved issues. |
| NFR-17 | Medium   | The pipeline shall provide the required geometry inspection functions for each validation profile.                                                                 | Functional Suitability                | Automated tests verify that expected issue types are detected on canonical test geometries.                                                                                      |
| NFR-18 | Medium   | The pipeline shall provide the required geometry repair functions for each validation profile.                                                                     | Functional Suitability                | Automated tests verify that supported geometry issues are repaired successfully and revalidation reduces or removes them within configured tolerances.                          |
| NFR-19 | Medium   | The pipeline shall generate export artifacts compatible with the requirements of the selected validation profile.                                                  | Functional Suitability                | Automated tests verify that exported artifacts conform to the expected format and can be consumed by the target simulation workflow.                                               |

---

## Mapping: Concern → Requirements

| Concern                                                | Functional               | Non-Functional                  |
| ------------------------------------------------------ | ------------------------ | ------------------------------- |
| New input format (e.g. DXF)                            | FR-01                    | NFR-01, NFR-05                  |
| Different simulation requirements                      | FR-02, FR-10             | NFR-02                          |
| Simulation owns its own validation                     | FR-07                    | NFR-04, NFR-09, NFR-11, NFR-13  |
| Easy to add a new validator                            | FR-03                    | NFR-03, NFR-06, NFR-15          |
| Different repair per simulation                        | FR-04, FR-08, FR-09      | NFR-02, NFR-03                  |
| Python vs C++/CGAL technology choice                   | FR-12                    | NFR-09, NFR-10, NFR-11          |

---

## Notes

- The concerns are *primarily* non-functional (extensibility, maintainability,
  interoperability). The functional requirements above are the minimum
  user-visible capabilities the new architecture must still deliver.
- Acceptance criteria are written so they can be checked by automated tests,
  schema validation, code review rules, or onboarding dry-runs — not by
  subjective judgment.
