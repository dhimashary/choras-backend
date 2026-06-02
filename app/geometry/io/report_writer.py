"""Native JSON serializer for `PipelineResult`.

Independent of the legacy ``geometry_processing_report`` translator: this
writes the snapshots / repairs straight from the IR dataclasses so the
inspect-only profile can produce a report without going through any
service-layer code.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from app.geometry.report import PipelineResult


def _snapshot_to_dict(snap) -> dict:
    return {
        "when": snap.when.value,
        "stage_name": snap.stage_name,
        "issues": [
            {
                "id": i.id,
                "kind": i.kind.value,
                "severity": i.severity.value,
                "stage": i.stage.value,
                "stage_name": i.stage_name,
                "payload": i.payload,
            }
            for i in snap.issues
        ],
        "counts_by_kind": _count_by_kind(snap.issues),
    }


def _count_by_kind(issues) -> dict[str, int]:
    counts: dict[str, int] = {}
    for i in issues:
        counts[i.kind.value] = counts.get(i.kind.value, 0) + 1
    return counts


def write_issue_report(result: PipelineResult, path: Path) -> Path:
    """Write a JSON report describing every snapshot + repair from `result`."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "snapshots": [_snapshot_to_dict(s) for s in result.snapshots],
        "repairs": [asdict(r) for r in result.repairs.results],
        "output_path": result.output_path,
    }
    path.write_text(json.dumps(payload, indent=2, default=str))
    return path
