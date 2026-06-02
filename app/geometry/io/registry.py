"""Registries for importers and exporters keyed by file extension / format."""
from __future__ import annotations

from app.geometry.io.exporters.base import Exporter
from app.geometry.io.importers.base import Importer


class ImporterRegistry:
    @classmethod
    def register(cls, importer: Importer) -> None:
        raise NotImplementedError

    @classmethod
    def for_extension(cls, ext: str) -> Importer:
        raise NotImplementedError


class ExporterRegistry:
    @classmethod
    def register(cls, name: str, exporter: Exporter) -> None:
        raise NotImplementedError

    @classmethod
    def get(cls, name: str) -> Exporter:
        raise NotImplementedError
