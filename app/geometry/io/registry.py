"""Registries for importers and exporters keyed by file extension / format."""
from __future__ import annotations

from app.geometry.io.exporters.base import Exporter
from app.geometry.io.importers.base import Importer


class ImporterRegistry:
    _by_ext: dict[str, type[Importer] | Importer] = {}

    @classmethod
    def register(cls, importer: type[Importer] | Importer) -> None:
        """Register an importer class or instance for all its declared extensions.

        Extensions may include a leading dot (".obj") or not; they are
        normalized to lowercase without a dot.
        """
        exts = getattr(importer, "extensions", None)
        if not exts:
            return
        for e in exts:
            key = e.lower().lstrip(".")
            cls._by_ext[key] = importer

    @classmethod
    def for_extension(cls, ext: str) -> Importer:
        """Return an importer instance for the given extension (e.g. '.obj' or 'obj')."""
        key = ext.lower().lstrip(".")
        imp = cls._by_ext.get(key)
        if imp is None:
            # Try to lazily register built-in importers once and retry
            cls._register_builtins()
            imp = cls._by_ext.get(key)
            if imp is None:
                raise ValueError(f"No importer registered for extension: {ext}")
        return imp() if isinstance(imp, type) else imp

    @classmethod
    def _register_builtins(cls) -> None:
        """Register the known builtin importers (idempotent).

        This keeps startup simple: importing the registry will load the
        common importer modules and register their classes.
        """
        if cls._by_ext:
            return
        try:
            from app.geometry.io.importers.obj import ObjImporter
        except Exception:
            ObjImporter = None
        try:
            from app.geometry.io.importers.dxf import DxfImporter
        except Exception:
            DxfImporter = None
        try:
            from app.geometry.io.importers.rhino import Rhino3dmImporter
        except Exception:
            Rhino3dmImporter = None

        for imp in (ObjImporter, DxfImporter, Rhino3dmImporter):
            if imp is not None:
                cls.register(imp)


class ExporterRegistry:
    @classmethod
    def register(cls, name: str, exporter: Exporter) -> None:
        raise NotImplementedError

    @classmethod
    def get(cls, name: str) -> Exporter:
        raise NotImplementedError
