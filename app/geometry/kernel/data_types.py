"""Polygon-face data type + IR<->legacy adapters.

`FaceRecord` is the canonical face representation used by every legacy
validator and repair. The new `Mesh` IR uses `Face` (cleaner shape, no
materials embedded). The two adapters below bridge the two so PR1/PR2
validators and repairs can call existing service functions unchanged.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.utils.geometry_utils import FaceRecord

if TYPE_CHECKING:
    from app.geometry.ir import Mesh


def mesh_to_legacy(mesh: "Mesh") -> tuple[list[FaceRecord], list[tuple[float, float, float]]]:
    """Adapter: Mesh IR -> (FaceRecord list, vertex-tuple list).

    The legacy detection / repair code expects:
      - faces: list of FaceRecord with 1-based vertex ids in `verts`
      - vertices: list of (x, y, z) tuples, 0-indexed

    This adapter does the conversion in O(V + F) without copying coordinates
    twice. It is safe to call on every detect()/apply() invocation; the cost
    is negligible compared to the geometric algorithms downstream.
    """
    points = [(v.x, v.y, v.z) for v in mesh.vertices]
    face_records: list[FaceRecord] = []
    for fid, face in enumerate(mesh.faces):
        face_records.append(
            FaceRecord(
                fid=fid,
                verts=list(face.vertex_indices),
                group=face.group or "default",
                group_material=face.material or "default_group_material",
                material=face.material or "unknown",
            )
        )
    return face_records, points


def mesh_from_legacy(
    faces: list[FaceRecord],
    points: list[tuple[float, float, float]],
    template: "Mesh",
) -> "Mesh":
    """Adapter: (FaceRecord list, vertex-tuple list) -> new Mesh IR.

    `template` supplies materials + metadata, so a repair preserves anything
    not represented in the FaceRecord triple (group / group_material / material).
    """
    from app.geometry.ir import Face, Mesh, Vertex
    return Mesh(
        vertices=[Vertex(x=p[0], y=p[1], z=p[2]) for p in points],
        faces=[
            Face(
                vertex_indices=list(f.verts),
                group=getattr(f, "group", "default") or "default",
                material=getattr(f, "material", None),
            )
            for f in faces
        ],
        materials=dict(template.materials),
        metadata=dict(template.metadata),
    )


__all__ = ["FaceRecord", "mesh_to_legacy", "mesh_from_legacy"]

