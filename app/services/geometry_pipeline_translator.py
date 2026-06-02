"""Translator: PipelineResult -> legacy `_report.json` shape.

Frontend contract (see `MODEL_DATA_EXAMPLE.json`): the issue/revalidation
report is a **flat dict** keyed by issue kind, each value a list of
uniform entries:

    {
      "duplicate_vertices":  [ {elements, severity, id}, ... ],
      "non_coplanar_faces":  [ ... ],
      "T-junctions":         [ ... ],
      "possible_holes":      [ ... ],
      "boundary_edges":      [ ... ],
      "degenerate_faces":    [ ... ],
      "intersections":       [ ... ],   # flat list, no wrapper
    }

Each entry:
    {
      "elements": [ {"type": "vertex"|"edge"|"face", "points": [...]}, ... ],
      "severity": "high" | "medium" | "low",
      "id":       <stable string id>,
    }

Tech-debt #9 — every list above is currently uncapped. Consider
capping each kind at e.g. 100 entries with a sibling `*_truncated`
flag once the frontend can render "showing N of M".
"""
from __future__ import annotations

from app.geometry.issues import Issue, IssueKind
from app.geometry.report import PipelineResult, ValidationSnapshot


def _legacy_severity(i: Issue) -> str:
    return {"fatal": "high", "warn": "medium"}.get(i.severity.value, "low")


def _normalise_elements(i: Issue) -> list[dict]:
    """Frontend wants `elements` to always be `list[{type, points}]`.

    Different legacy detectors emit different shapes:
      * boundary_edges / degenerate / duplicate / planarity:
            payload["elements"] is a *single* dict {type, points}
            → wrap in a list.
      * possible_holes:
            payload["elements"] is already a list of {type, points}.
      * t_junctions:
            raw detector keys `edge_coordinates` + `split_vertex_coordinates`
            → build [{edge}, {vertex}] (mirrors `convert_tjunctions_to_standard_format`).
      * intersections:
            raw detector keys `edge_coordinates` + `facet_fid_coordinates` + `point`
            → build [{edge}, {face}, {vertex}] (mirrors
              `convert_intersections_to_standard_format`).
    """
    p = i.payload

    if i.kind is IssueKind.T_JUNCTION:
        return [
            {"type": "edge",   "points": p.get("edge_coordinates", [])},
            {"type": "vertex", "points": p.get("split_vertex_coordinates", [])},
        ]

    if i.kind is IssueKind.INTERSECTION:
        return [
            {"type": "edge",   "points": p.get("edge_coordinates", [])},
            {"type": "face",   "points": p.get("facet_fid_coordinates", [])},
            {"type": "vertex", "points": [p.get("point", [0, 0, 0])]},
        ]

    elements = p.get("elements")
    if isinstance(elements, dict):
        return [elements]
    if isinstance(elements, list):
        return elements
    return []


def _entry(i: Issue) -> dict:
    """Build a single frontend entry from an Issue."""
    return {
        "elements": _normalise_elements(i),
        "severity": _legacy_severity(i),
        "id": i.id,
    }


def _list_for(issues: list[Issue], kind: IssueKind) -> list[dict]:
    """All non-summary issues of `kind` as frontend entries."""
    return [
        _entry(i)
        for i in issues
        if i.kind is kind and not i.payload.get("summary")
    ]


def _kind_dict(issues: list[Issue]) -> dict:
    """Frontend-shaped flat dict — one list per IssueKind."""
    return {
        "duplicate_vertices": _list_for(issues, IssueKind.DUPLICATE_VERTEX),
        "non_coplanar_faces": _list_for(issues, IssueKind.NON_PLANAR_FACE),
        "T-junctions":        _list_for(issues, IssueKind.T_JUNCTION),
        "possible_holes":     _list_for(issues, IssueKind.POSSIBLE_HOLE),
        "boundary_edges":     _list_for(issues, IssueKind.BOUNDARY_EDGE),
        "degenerate_faces":   _list_for(issues, IssueKind.DEGENERATE_FACE),
        "intersections":      _list_for(issues, IssueKind.INTERSECTION),
    }


def issue_detection_report_from_snapshot(snapshot: ValidationSnapshot) -> dict:
    return _kind_dict(snapshot.issues)


def revalidation_report_from_snapshot(snapshot: ValidationSnapshot) -> dict:
    return _kind_dict(snapshot.issues)


def repair_report_from_pipeline(result: PipelineResult) -> list[dict]:
    """Mirror the `repair_report` list produced by `append_repair_report`.

    Legacy entries have keys: repair_type, affected_count, before, after,
    details. We additionally surface stage / iterations / affected_issue_ids
    for debugging — these are additive and frontends can ignore them.
    """
    out: list[dict] = []
    for r in result.repairs.results:
        out.append({
            "repair_type": r.step_name,
            "affected_count": len(r.affected_ids),
            "before": r.before_count,
            "after": r.after_count,
            "details": dict(r.details),
            "stage": r.stage_name,
            "iterations": r.iterations,
            "affected_issue_ids": list(r.affected_ids),
        })
    return out


def to_legacy_processing_report(
    result: PipelineResult,
    *,
    input_path: str,
    output_path: str,
    topology_before: dict,
    topology_after: dict,  # accepted for API symmetry; legacy shape omits it
) -> dict:
    """Top-level entry — mirrors `create_geometry_processing_report`."""
    initial = result.initial
    final = result.final
    if initial is None or final is None:
        raise ValueError("PipelineResult has no snapshots; cannot translate.")
    return {
        "input_obj": input_path,
        "output_repaired_obj": output_path,
        "topology_before_repair": topology_before,
        "issue_detection_report": issue_detection_report_from_snapshot(initial),
        "repair_report": repair_report_from_pipeline(result),
        "revalidation_report": revalidation_report_from_snapshot(final),
    }
