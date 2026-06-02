"""Translate a `PipelineResult` into the API-shaped inspect report.

Output shape::

    {
      "<issue_kind>": [
        {
          "id": "<issue id>",
          "severity": "low|medium|high",
          "elements": [{"type": "vertex|edge|face", "points": [[x,y,z], ...]}, ...]
        },
        ...
      ],
      ...
    }

Selection rules (matches what the inspect-only profile produces):

  - duplicate_vertex, degenerate_face, non_planar_face, boundary_edge  → PRE
  - t_junction                                                         → POST_STAGE("t_junctions")
  - intersection                                                       → POST_STAGE("intersections")
  - possible_hole                                                      → FINAL
"""
from __future__ import annotations

from typing import Iterable

from app.geometry.issues import DetectionStage, Issue, IssueKind, Severity
from app.geometry.report import PipelineResult, ValidationSnapshot


SelectionKey = tuple[DetectionStage, str]  # (when, stage_name)


_SELECTION: dict[IssueKind, SelectionKey] = {
    IssueKind.DUPLICATE_VERTEX: (DetectionStage.PRE, ""),
    IssueKind.DEGENERATE_FACE: (DetectionStage.PRE, ""),
    IssueKind.NON_PLANAR_FACE: (DetectionStage.PRE, ""),
    IssueKind.BOUNDARY_EDGE: (DetectionStage.PRE, ""),
    IssueKind.T_JUNCTION: (DetectionStage.POST_STAGE, "t_junctions"),
    IssueKind.INTERSECTION: (DetectionStage.POST_STAGE, "intersections"),
    IssueKind.POSSIBLE_HOLE: (DetectionStage.FINAL, ""),
}


_SEVERITY_FALLBACK = {
    Severity.FATAL: "high",
    Severity.WARN: "medium",
}


def _snapshot_index(snapshots: Iterable[ValidationSnapshot]) -> dict[SelectionKey, ValidationSnapshot]:
    """Map (when, stage_name) -> snapshot. Last-write wins if duplicates."""
    return {(s.when, s.stage_name): s for s in snapshots}


def _normalize_elements(payload: dict, kind: IssueKind) -> list[dict]:
    """Coerce a validator payload's element data into a uniform list.

    Most validators already emit ``payload["elements"]`` either as a list
    or a single dict. T-junction and intersection detectors emit raw
    ``edge_coordinates``/``point``/``facet_fid_coordinates`` keys instead;
    those branches assemble the element list inline.
    """
    if "elements" in payload:
        elems = payload["elements"]
        return list(elems) if isinstance(elems, list) else [elems]

    if kind is IssueKind.T_JUNCTION:
        out: list[dict] = []
        if "edge_coordinates" in payload:
            out.append({"type": "edge", "points": payload["edge_coordinates"]})
        if "split_vertex_coordinates" in payload:
            out.append({"type": "vertex", "points": payload["split_vertex_coordinates"]})
        return out

    if kind is IssueKind.INTERSECTION:
        out = []
        if "edge_coordinates" in payload:
            out.append({"type": "edge", "points": payload["edge_coordinates"]})
        if "facet_fid_coordinates" in payload:
            out.append({"type": "face", "points": payload["facet_fid_coordinates"]})
        if "point" in payload:
            out.append({"type": "vertex", "points": [payload["point"]]})
        return out

    return []


def _severity_str(issue: Issue) -> str:
    payload_sev = issue.payload.get("severity")
    if isinstance(payload_sev, str):
        return payload_sev
    return _SEVERITY_FALLBACK.get(issue.severity, "medium")


def _issue_to_entry(issue: Issue) -> dict:
    entry: dict = {
        "id": issue.id,
        "severity": _severity_str(issue),
        "elements": _normalize_elements(issue.payload, issue.kind),
    }
    if "details" in issue.payload:
        entry["details"] = issue.payload["details"]
    return entry


def to_inspect_report(result: PipelineResult) -> dict[str, list[dict]]:
    """Build the grouped, UI-shaped inspect report from a `PipelineResult`."""
    by_key = _snapshot_index(result.snapshots)
    report: dict[str, list[dict]] = {}

    for kind, key in _SELECTION.items():
        snap = by_key.get(key)
        if snap is None:
            continue
        bucket = [_issue_to_entry(i) for i in snap.issues if i.kind is kind]
        if bucket:
            report[kind.value] = bucket

    return report
