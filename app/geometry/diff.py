"""Snapshot diffing — the canonical way to answer 'what did stage X actually do?'.

Compares two `ValidationSnapshot`s by `Issue.id` (a stable content hash of
kind+payload) so the same physical defect is recognised across snapshots.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.geometry.issues import Issue
from app.geometry.report import ValidationSnapshot


@dataclass
class SnapshotDiff:
    fixed: list[Issue] = field(default_factory=list)         # present before, gone after
    introduced: list[Issue] = field(default_factory=list)    # absent before, present after — regression!
    remaining: list[Issue] = field(default_factory=list)     # present in both


def diff_snapshots(before: ValidationSnapshot, after: ValidationSnapshot) -> SnapshotDiff:
    b = {i.id: i for i in before.issues}
    a = {i.id: i for i in after.issues}
    return SnapshotDiff(
        fixed=[b[i] for i in b.keys() - a.keys()],
        introduced=[a[i] for i in a.keys() - b.keys()],
        remaining=[a[i] for i in a.keys() & b.keys()],
    )
