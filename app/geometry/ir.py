"""Intermediate Representation (IR) for geometry.

The IR is a tagged union: every variant implements `Geometry` and carries
a `kind` discriminator so validators / repairs / exporters can declare which
variants they accept.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar, Protocol, runtime_checkable


# ---- Primitive value objects ------------------------------------------------

@dataclass(frozen=True)
class Vertex:
    x: float
    y: float
    z: float


@dataclass
class Face:
    vertex_indices: list[int]
    group: str
    material: str | None


@dataclass
class Curve:
    """A 2D/3D curve segment from a B-Rep input (line, polyline, arc, spline)."""
    points: list[Vertex]
    layer: str
    closed: bool


@dataclass
class Surface:
    """A trimmed surface from a B-Rep input."""
    boundary: list[Curve]
    layer: str


@dataclass(frozen=True)
class MaterialInfo:
    name: str
    properties: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class LayerInfo:
    name: str
    color: str | None = None


# ---- Tagged-union geometry types --------------------------------------------

@runtime_checkable
class Geometry(Protocol):
    kind: ClassVar[str]


@dataclass
class Mesh:
    kind: ClassVar[str] = "mesh"
    vertices: list[Vertex] = field(default_factory=list)
    faces: list[Face] = field(default_factory=list)
    materials: dict[str, MaterialInfo] = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)


@dataclass
class BRep:
    kind: ClassVar[str] = "brep"
    curves: list[Curve] = field(default_factory=list)
    surfaces: list[Surface] = field(default_factory=list)
    layers: dict[str, LayerInfo] = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)


@dataclass
class PointCloud:
    kind: ClassVar[str] = "pointcloud"
    points: list[Vertex] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
