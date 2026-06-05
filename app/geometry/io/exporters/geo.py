"""Gmsh `.geo` exporter — writes a `Mesh` IR via the legacy export helper."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

from app.geometry.ir import Mesh
from app.geometry.kernel import mesh_to_legacy
from app.services.geometry_export_service import (
    Cavity,
    export_processed_topology_to_gmsh_geo,
)

class GmshGeoExporter:
    def __init__(
        self,
        volume_name: str = "RoomVolume",
        *,
        detect_cavities: bool = True,
        detection_mode: str = "native",
        cavity_pitch: float = 0.05,
        cavity_closing_iterations: int = 0,
    ) -> None:
        """
        Parameters
        ----------
        volume_name : Name used for the single Physical Volume in legacy
            output, or as fallback when detection fails / yields nothing.
        detect_cavities : If True, run cavity detection before writing and
            emit one `Surface Loop` + `Volume` per detected cavity (Gmsh
            requires every enclosed space to be its own volume).
                detection_mode : One of:
                        - "native" (default): use the C++ CGAL grid+visibility detector
                            (``bin/volume_detector``); robust for multi-scale scenes
                            (big rooms + small furniture cavities). This path is the
                            production default and does not fall back to the voxel detector.
                        - "voxel": use the pure-Python voxel detector (kept for testing).
        cavity_pitch : Voxel size (model units) for the *voxel* detector. Must
            be smaller than the smallest wall thickness you care about.
        cavity_closing_iterations : Optional morphological closing iterations
            (voxel detector only) to bridge sub-pitch gaps before labeling.
        """
        self.volume_name = volume_name
        self.detect_cavities = detect_cavities
        self.detection_mode = detection_mode
        self.cavity_pitch = cavity_pitch
        self.cavity_closing_iterations = cavity_closing_iterations

    def write(
        self,
        geom: Mesh,
        path: Path,
        cavities: Optional[List[Cavity]] = None,
    ) -> None:
        """Write GEO file.

        Cavity sources, in priority order:
          1. Explicit `cavities` argument (caller-provided).
          2. Auto-detected cavities (when `self.detect_cavities=True`).
          3. None -> legacy single-volume output.
        Detection failures fall back to legacy output with a warning.
        """
        faces, points = mesh_to_legacy(geom)

        if cavities is None and self.detect_cavities:
            cavities = self._run_detection(faces, points)

        export_processed_topology_to_gmsh_geo(
            faces, points, str(path),
            volume_name=self.volume_name,
            cavities=cavities,
        )

    def _run_detection(self, faces, points) -> Optional[List[Cavity]]:
        mode = self.detection_mode
        if mode == "native":
            # In production we require the native detector; propagate errors
            # rather than silently falling back to the Python voxelizer.
            return self._run_native_detection(faces, points)
        elif mode == "voxel":
            return self._run_voxel_detection(faces, points)
        else:
            raise ValueError(f"Unsupported detection_mode: {mode}")

    def _run_native_detection(self, faces, points) -> Optional[List[Cavity]]:
        """Return cavities from the native detector.

        Raises when the native binary is missing or detection fails.
        """
        from app.geometry.volume_detector_bridge import detect_volumes_native

        try:
            return detect_volumes_native(faces, points)
        except Exception as exc:
            return None

    def _run_voxel_detection(self, faces, points) -> Optional[List[Cavity]]:
        try:
            # Imported lazily so trimesh/scipy are only required when
            # cavity detection is actually enabled.
            from app.geometry.cavity_detector import detect_cavities

            cavities = detect_cavities(
                faces, points,
                pitch=self.cavity_pitch,
                closing_iterations=self.cavity_closing_iterations,
            )
            if not cavities:
                return None
            return cavities
        except Exception as exc:
            return None

