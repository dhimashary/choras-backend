"""3DM exporter — converts the OBJ emitted by `ObjExporter` to Rhino 3DM.

This exporter relies on the existing ObjConversion converter in
`app.factory.geometry_converter_factory` which uses `rhino3dm`.
"""
from __future__ import annotations

from pathlib import Path
import logging

from app.geometry.ir import Mesh
from app.geometry.io.exporters.obj import ObjExporter
from app.factory.geometry_converter_factory.ObjConversion import ObjConversion


class ThreeDMExporter:
    logger = logging.getLogger(__name__)
    def path_for(self, base_path: Path) -> Path:
        """Write `<stem>_repaired.3dm` next to the .geo/obj file."""
        base_path = Path(base_path)
        return base_path.with_name(base_path.stem + "_repaired.3dm")

    def write(self, geom: Mesh, path: Path) -> None:
        # Ensure OBJ exists (use the same convention as ObjExporter)
        self.logger.warning(f"Preparing to export 3DM to {path} from Mesh IR; ensuring OBJ exists")
        base_path = Path(path)
        obj_path = base_path.with_name(base_path.stem + "_repaired.obj")
        self.logger.warning(f"Expected OBJ path for 3DM export: {obj_path}")
        
        if not obj_path.exists():
            # Generate OBJ from the Mesh IR first
            ObjExporter().write(geom, obj_path)

        # Convert OBJ -> 3DM using the existing converter
        rhino_path = base_path.with_name(base_path.stem + ".3dm")

        # If a previous .3dm exists, move it to `_initial.3dm` (overwrite if exists)
        initial_path = base_path.with_name(base_path.stem + "_initial.3dm")
        try:
            if rhino_path.exists():
                if initial_path.exists():
                    initial_path.unlink()
                # use replace so it will overwrite atomically where supported
                rhino_path.replace(initial_path)
                self.logger.info(f"Backed up existing {rhino_path} to {initial_path}")
        except Exception as ex:
            # log and continue; conversion will overwrite/create rhino_path
            self.logger.warning(f"Failed to back up existing 3dm file: {ex}")

        converter = ObjConversion()
        converter.generate_3dm(str(obj_path), str(rhino_path))
        self.logger.warning(f"Converted {obj_path} to {rhino_path} using ObjConversion")
