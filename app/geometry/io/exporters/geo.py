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

logger = logging.getLogger(__name__)


class GmshGeoExporter:
    def __init__(
        self,
        volume_name: str = "RoomVolume",
        *,
        detect_cavities: bool = True,
        cavity_pitch: float = 0.05,
        cavity_closing_iterations: int = 0,
        cavity_auto_scale_target_diag: float = 5.0,
    ) -> None:
        """
        Parameters
        ----------
        volume_name : Name used for the single Physical Volume in legacy
            output, or as fallback when detection fails / yields nothing.
        detect_cavities : If True, run the voxel-based cavity detector before
            writing and emit one `Surface Loop` + `Volume` per detected
            cavity (Gmsh requires every enclosed space to be its own volume).
        cavity_pitch : Voxel size (model units) for detection. Must be
            smaller than the smallest wall thickness you care about.
        cavity_closing_iterations : Optional morphological closing iterations
            to bridge sub-pitch gaps before labeling. 0 disables.
        """
        self.volume_name = volume_name
        self.detect_cavities = detect_cavities
        self.cavity_pitch = cavity_pitch
        self.cavity_closing_iterations = cavity_closing_iterations
        self.cavity_auto_scale_target_diag = cavity_auto_scale_target_diag

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
        try:
            # Imported lazily so trimesh/scipy are only required when
            # cavity detection is actually enabled.
            from app.geometry.cavity_detector import detect_cavities

            cavities = detect_cavities(
                faces, points,
                pitch=self.cavity_pitch,
                closing_iterations=self.cavity_closing_iterations,
                auto_scale=True,
                auto_scale_target_diag=self.cavity_auto_scale_target_diag,
            )
            if not cavities:
                logger.info(
                    "Cavity detector found no enclosed regions; "
                    "falling back to single-volume output."
                )
                return None
            return cavities
        except Exception as exc:
            logger.warning(
                "Cavity detection failed (%s); falling back to single-volume output.",
                exc, exc_info=True,
            )
            return None

