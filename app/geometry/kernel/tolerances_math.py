"""Robust numerical comparisons under tolerance."""
from __future__ import annotations


def approx_equal(a: float, b: float, tol: float) -> bool:
    raise NotImplementedError


def snap(value: float, grid: float) -> float:
    raise NotImplementedError
