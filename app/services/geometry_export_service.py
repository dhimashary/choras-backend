from collections import defaultdict
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from app.utils.geometry_utils import FaceRecord, _uedge
import rhino3dm

logger = logging.getLogger(__name__)


@dataclass
class Cavity:
    """Represents a detected enclosed cavity.

    oriented_faces: list of (face_index, sign) where sign is +1 if the
    face's normal points out of the cavity, -1 if it points into the cavity.
    face_index refers to the index in the `faces` list passed to the exporter.
    """
    id: int
    name: str
    volume: float
    oriented_faces: List[Tuple[int, int]]
    is_manifold: bool = False  # True if the detector says every volume boundary edge is used exactly twice.

def export_processed_topology_to_gmsh_geo(
    faces: List[FaceRecord],
    unique_vertices: List[Tuple[float, float, float]],
    geo_file: str,
    volume_name: str = "RoomVolume",
    cavities: Optional[List[Cavity]] = None,
) -> Tuple[int, int]:
    """
    Export processed topology to Gmsh GEO file.

    Parameters
    ----------
    faces : List[FaceRecord]
        List of processed FaceRecord objects.
    unique_vertices : List[Tuple[float, float, float]]
        List of unique vertex coordinates.
    geo_file : str
        Path to the output GEO file.
    volume_name : str
        Name for the physical volume.

    Returns
    -------
    Tuple[int, int]
        (num_lines, num_surfaces)
    """
    # -----------------------------
    # Build unique edges (Lines) + signed loops
    # -----------------------------
    edge_to_line: Dict = {}
    line_orientation: Dict = {}
    next_line_id = 1
    face_line_loops: List[List[int]] = []

    for face in faces:
        loop_line_ids = []
        n = len(face.verts)
        for i in range(n):
            a = face.verts[i]
            b = face.verts[(i + 1) % n]
            key = _uedge(a, b)
            if key not in edge_to_line:
                edge_to_line[key] = next_line_id
                line_orientation[next_line_id] = (a, b)
                next_line_id += 1
            lid = edge_to_line[key]
            ori = line_orientation[lid]
            loop_line_ids.append(lid if ori == (a, b) else -lid)
        face_line_loops.append(loop_line_ids)
    
    # looking for 3dm path
    base_path = Path(geo_file)
    three_dm_path = base_path.with_name(base_path.stem + ".3dm")

    model = None
    # Validate 3dm availability before trying to read it
    if three_dm_path.exists():
        try:
            model = rhino3dm.File3dm.Read(str(three_dm_path))
        except Exception as ex:
            logger.warning("Failed to read 3DM model at %s: %s", three_dm_path, ex)
            model = None
    else:
        logger.info("3DM model not found at %s; continuing without material mapping", three_dm_path)

    # Material mapping for later use
    material_to_id = {}
    if model is not None:
        for obj in model.Objects:
            if isinstance(obj.Geometry, rhino3dm.Mesh):
                material_name = obj.Geometry.GetUserString("material_name")
                if material_name:
                    material_to_id[f"{obj.Attributes.Id}"] = material_name
    else:
        # No model -> leave material mapping empty. Downstream code will handle missing materials.
        logger.debug("No 3DM model available; material_to_id mapping will be empty.")

    # Physical surface groups: material -> list of 0-based face indices
    physical_surfaces_dict: Dict = {}
    for idx, face in enumerate(faces):
        physical_surfaces_dict.setdefault(face.material, []).append(idx)

    logger.info("Physical surfaces: %s", {
        mat: len(ids) for mat, ids in physical_surfaces_dict.items()
    })

    # -----------------------------
    # Write GEO
    # -----------------------------
    with open(geo_file, "w") as g:
        # Points
        for i, v in enumerate(unique_vertices, start=1):
            g.write(f"Point({i}) = {{ {v[0]}, {v[1]}, {v[2]}, 1.0 }};\n")
        g.write("\n")

        # Lines
        for lid in range(1, next_line_id):
            a, b = line_orientation[lid]
            g.write(f"Line({lid}) = {{ {a}, {b} }};\n")
        g.write("\n")

        # Line Loops
        for sid, (loop, face) in enumerate(zip(face_line_loops, faces), start=1):
            loop_str = ", ".join(str(x) for x in loop)

            # g.write(f"// fid={face.fid} group={face.group} material={face.material}\n")
            g.write(f"Line Loop({sid}) = {{ {loop_str} }};\n")
        g.write("\n")

        # Plane Surfaces
        for sid in range(1, len(face_line_loops) + 1):
            g.write(f"Plane Surface({sid}) = {{ {sid} }};\n")
        g.write("\n")

        # Surface Loop(s) + Volume(s)
        if not cavities:
            # Legacy single-volume behavior: include all plane surfaces.
            total_surfaces = len(face_line_loops)
            surf_list = ", ".join(str(i) for i in range(1, total_surfaces + 1))

            g.write(f"Surface Loop(1) = {{ {surf_list} }};\n")
            g.write("Volume(1) = { 1 };\n")
            g.write(f'Physical Volume("{volume_name}") = {{ 1 }};\n')

        else:
            # Merge non-manifold cavities into the main room volume.
            # key   = abs(surface id)
            # value = signed surface id
            main_volume_surfaces: dict[int, int] = {}
            separate_volumes: list[tuple[str, list[int]]] = []

            for cav in cavities:
                is_manifold = getattr(cav, "is_manifold", True)

                if cav.id == 0 or not is_manifold:
                    for face_idx, sign in cav.oriented_faces:
                        sid = face_idx + 1
                        signed_sid = sid if sign > 0 else -sid

                        # Treat +sid and -sid as the same surface.
                        if sid not in main_volume_surfaces:
                            main_volume_surfaces[sid] = signed_sid

                else:
                    surf_ids: list[int] = []

                    for face_idx, sign in cav.oriented_faces:
                        sid = face_idx + 1
                        surf_ids.append(sid if sign > 0 else -sid)

                    separate_volumes.append((cav.name, surf_ids))

            physical_volumes: list[tuple[str, int]] = []

            if main_volume_surfaces:
                surf_list = ", ".join(
                    str(signed_sid)
                    for signed_sid in main_volume_surfaces.values()
                )

                g.write(f"Surface Loop(1) = {{ {surf_list} }};\n")
                g.write("Volume(1) = { 1 };\n")
                physical_volumes.append((volume_name, 1))

                next_volume_id = 2
            else:
                next_volume_id = 1

            for cav_name, surf_ids in separate_volumes:
                surf_list = ", ".join(str(sid) for sid in surf_ids)

                g.write(f"Surface Loop({next_volume_id}) = {{ {surf_list} }};\n")
                g.write(f"Volume({next_volume_id}) = {{ {next_volume_id} }};\n")

                physical_volumes.append((cav_name, next_volume_id))
                next_volume_id += 1

            for cav_name, volume_id in physical_volumes:
                g.write(f'Physical Volume("{cav_name}") = {{ {volume_id} }};\n')        
        
        # Physical Surfaces
        ii = 1
        for grp in material_to_id:
            g.write(f'Physical Surface("{grp}") = {{ { str(ii) } }};\n')
            ii = ii + 1

        # Physical Lines
        lines_all = ", ".join(str(i) for i in range(1, next_line_id))
        g.write(f'Physical Line("default") = {{ {lines_all} }};\n')

        # Mesh options
        g.write('Mesh.Algorithm = 6;\n')
        g.write('Mesh.Algorithm3D = 1; // Delaunay3D\n')
        g.write('Mesh.Optimize = 1;\n')
        g.write('Mesh.CharacteristicLengthFromPoints = 1;\n')

    return next_line_id - 1, len(face_line_loops)

def export_processed_topology_to_obj(
    obj_output_path: str,
    unique_vertices: list,
    faces: "List[FaceRecord]",
) -> bool:
    """
    Export the processed topology to an OBJ file.
    Args:
        obj_output_path : destination path
        unique_vertices : list of (x, y, z) tuples, 0-based (vertex id i -> index i-1)
        faces           : list of FaceRecord (each carries verts, group, material)
    """
    try:
        # Group faces by group first, then by group_material
        faces_by_group_and_material: dict = defaultdict(lambda: defaultdict(list))
        for face in faces:
            faces_by_group_and_material[face.group][face.group_material].append(face)

        with open(obj_output_path, "w") as f:
            f.write("# Processed topology from geometry conversion\n\n")

            # Vertices
            for x, y, z in unique_vertices:
                # previously we flipped z, now flip back for OBJ export
                f.write(f"v {x} {z} {-y}\n")

            f.write("\n")

            # Faces grouped by group, then by group_material
            for group in sorted(faces_by_group_and_material.keys()):
                f.write(f"\ng {group}\n")
                for group_material in sorted(faces_by_group_and_material[group].keys()):
                    f.write(f"usemtl {group_material}\n")
                    for face in faces_by_group_and_material[group][group_material]:
                        f.write("f " + " ".join(f"{v}//1" for v in face.verts) + "\n")
        return True

    except Exception as ex:
        logger.error("Failed to export processed topology to OBJ: %s", ex)
        return False

def export_faces_to_json(faces, filepath):
    """
    Export FaceRecord list to JSON for debugging.

    Parameters
    ----------
    faces : list[FaceRecord]
    filepath : str
    """
    data = []

    for f in faces:
        data.append({
            "fid": f.fid,
            "verts": f.verts,
            "group": getattr(f, "group", None),
            "group_material": getattr(f, "group_material", None),
            "material": getattr(f, "material", None),
        })

    with open(filepath, "w") as fp:
        json.dump(data, fp, indent=2)

    print(f"[DEBUG] Exported {len(faces)} faces → {filepath}")

def export_geometry_issues_to_json(
    detected_geometry_issues: Dict[str, Any],
    obj_file_path: str
) -> Tuple[str, int]:
    """
    Export detected geometry issues to a JSON file for diagnostic purposes.

    This function saves the comprehensive geometry inspection results (including
    duplicate vertices, T-junctions, possible holes, boundary edges, degenerate
    faces, and intersections) to a JSON file. The file is named by replacing
    the '.obj' extension of the input OBJ file with '_issues.json'.

    Additionally, calculates the total issue count by summing the lengths of
    all list values in the issues dictionary.

    Parameters
    ----------
    detected_geometry_issues : Dict[str, Any]
        Dictionary containing the results from geometry inspection functions.
        Expected keys include:
        - "duplicate_vertices": List of duplicate vertex reports
        - "non_coplanar_faces": List of planarity issue reports
        - "T-junctions": List of T-junction reports
        - "possible_holes": List of hole detection reports
        - "boundary_edges": List of boundary edge reports
        - "degenerate_faces": List of degenerate face reports
        - "intersections": List of intersection reports
    obj_file_path : str
        Path to the original OBJ file. Used to derive the output JSON file path.

    Returns
    -------
    Tuple[str, int]
        (Path to the created JSON file, total issue count)

    Notes
    -----
    - The JSON file is saved with indentation for readability.
    - Logs an info message upon successful export.
    - If the OBJ file path does not end with '.obj', the replacement may not work as expected.
    """
    issue_count = 0
    for value in detected_geometry_issues.values():
        if isinstance(value, list):
            issue_count += len(value)
    
    issues_json_path = obj_file_path.replace('.obj', '_issues.json')
    
    with open(issues_json_path, 'w') as f:
        json.dump(detected_geometry_issues, f, indent=2)
        
    return issues_json_path, issue_count
