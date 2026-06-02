"""Validator: flags faces whose bounding-box max-dimension is below threshold.

Acoustic wave-based solvers degrade when the mesh contains faces much
smaller than the wavelength of interest; faces below ~10 cm are almost
always either modelling artefacts or unintended slivers. Default threshold
comes from `Tolerances.small_face_max_dim` (0.10 m).

NOTE: not wired into `wave_based_profile` yet — see tech-debt #11.
"""
from __future__ import annotations

from typing import ClassVar

from app.geometry.context import Context
from app.geometry.ir import Mesh
from app.geometry.issues import DetectionStage, Issue, IssueKind, Severity
from app.geometry.kernel import mesh_to_legacy
from app.geometry.validators._common import cap_and_summarize


class SmallFacesValidator:
    name: ClassVar[str] = "small_faces"
    accepts: ClassVar[set[str]] = {"mesh"}
    kind: ClassVar[IssueKind] = IssueKind.SMALL_FACE

    def detect(self, geom: Mesh, ctx: Context) -> list[Issue]:
        faces, points = mesh_to_legacy(geom)
        threshold = ctx.tolerances.small_face_max_dim

        raw: list[dict] = []
        for f in faces:
            pts = [points[i - 1] for i in f.verts]
            if not pts:
                continue
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            zs = [p[2] for p in pts]
            max_dim = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
            if max_dim < threshold:
                raw.append({
                    "fid": f.fid,
                    "max_dim": max_dim,
                    "threshold": threshold,
                    "elements": {
                        "type": "face",
                        "points": pts,
                    },
                })

        return cap_and_summarize(
            raw,
            kind=self.kind,
            stage=DetectionStage.PRE,
            stage_name="",
            max_reports=ctx.tolerances.max_reports,
            severity_of=lambda d: Severity.WARN,
            payload_of=lambda d: dict(d),
        )
