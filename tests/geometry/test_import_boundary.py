"""Architectural test: app.geometry must remain framework-free.

The `app/geometry` package is the bounded core of the geometry pipeline.
It must not import Flask, the SQLAlchemy db handle, or ORM models — those
are concerns of the surrounding service layer.

If this test fails, you have either:
  (a) accidentally imported infrastructure from a kernel/validator/repair, or
  (b) genuinely needed something that should be passed via Context instead.
"""
from __future__ import annotations

import ast
import pathlib

FORBIDDEN_PREFIXES = (
    "flask",
    "app.db",
    "app.models",
    "app.extention",      # Flask extension hub
    "app.blueprint",      # Flask blueprints
    "app.routes",         # HTTP layer
)


def _iter_geometry_files() -> list[pathlib.Path]:
    root = pathlib.Path(__file__).resolve().parents[2] / "app" / "geometry"
    return sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)


def _imports_of(path: pathlib.Path) -> list[str]:
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=str(path))
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                out.append(node.module)
    return out


def test_geometry_has_no_framework_imports() -> None:
    offences: list[str] = []
    for path in _iter_geometry_files():
        for mod in _imports_of(path):
            if any(mod == p or mod.startswith(p + ".") for p in FORBIDDEN_PREFIXES):
                offences.append(f"{path.name}: imports {mod}")
    assert not offences, "Forbidden imports in app.geometry:\n  " + "\n  ".join(offences)
