"""OBJ importer -> Mesh.

Wraps the legacy `parse_obj_file` + `process_and_instantiate_faces`
sequence. The resulting `Mesh` is in IR coordinates (Z-up) — the
SketchUp/Y-up flip is performed by `parse_obj_file` itself (tech-debt #6).
"""
from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from app.geometry.ir import Face, Mesh, Vertex
from app.services.geometry_parsing_service import (
    parse_obj_file,
    process_and_instantiate_faces,
)


class ObjImporter:
    extensions: ClassVar[tuple[str, ...]] = (".obj",)

    def load(self, path: Path) -> Mesh:
        path = str(path)
        vertices, raw_faces, face_groups, face_group_materials = parse_obj_file(path)

        # `process_and_instantiate_faces` needs a per-face material id list;
        # absent a Rhino sidecar we fall back to the OBJ's `usemtl` value.
        material_id_array = list(face_group_materials)
        face_records = process_and_instantiate_faces(
            raw_faces=raw_faces,
            face_groups=face_groups,
            face_group_materials=face_group_materials,
            material_id_array=material_id_array,
        )

        return Mesh(
            vertices=[Vertex(x=v[0], y=v[1], z=v[2]) for v in vertices],
            faces=[
                Face(
                    vertex_indices=list(f.verts),
                    group=f.group,
                    material=f.material,
                )
                for f in face_records
            ],
            metadata={"source_path": path},
        )

