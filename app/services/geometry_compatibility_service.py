"""Geometry-issue compatibility per simulation method.

CHORAS ships an authoritative *baseline* compatibility list
(``GEOMETRY_COMPATIBILITY_BASELINE_PATH``). Every simulation method inherits
it. A method may publish its own override file — referenced by the
``geometryCompatibility`` key in ``methods-config.json`` and resolved relative
to ``SETTINGS_FILE_FOLDER`` (exactly like the ``settings`` file). The provider
"copies and overrides" the baseline: the override is merged on top of the
baseline *per issue kind*, so it only needs to list the issues/fields that
differ (a full copy works too).

Merge rules
-----------
* The set of issue kinds is the union of baseline + override.
* For an issue present in both, override fields win field-by-field.
* Unknown top-level keys in the override (e.g. ``extends``, ``method``,
  ``notes``) are ignored for the merged issue map.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

from config import DefaultConfig
from app.services.discovery_service import discover_methods

logger = logging.getLogger(__name__)


def _load_baseline() -> Dict[str, Any]:
    """Load and return the CHORAS baseline compatibility document."""
    path = DefaultConfig.GEOMETRY_COMPATIBILITY_BASELINE_PATH
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        logger.error(f"Geometry compatibility baseline not found at: {path}")
        return {"version": 0, "issues": {}}
    except json.JSONDecodeError as ex:
        logger.error(f"Invalid JSON in geometry compatibility baseline: {ex}")
        return {"version": 0, "issues": {}}

    if not isinstance(data.get("issues"), dict):
        logger.error("Geometry compatibility baseline is missing an 'issues' object")
        data["issues"] = {}
    return data


def _load_override(method_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Load a method's override document, if it declares one and it exists."""
    override_file = method_config.get("geometryCompatibility")
    if not override_file:
        return None

    override_path = os.path.join(DefaultConfig.SETTINGS_FILE_FOLDER, override_file)
    if not os.path.exists(override_path):
        logger.warning(
            f"geometryCompatibility file '{override_file}' declared by "
            f"'{method_config.get('simulationType')}' not found at {override_path}"
        )
        return None

    try:
        with open(override_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as ex:
        logger.error(f"Invalid JSON in override '{override_file}': {ex}")
        return None

    if not isinstance(data.get("issues"), dict):
        logger.warning(f"Override '{override_file}' has no 'issues' object; ignoring")
        return None
    return data


def _merge_issues(
    baseline_issues: Dict[str, Any],
    override_issues: Dict[str, Any],
) -> Dict[str, Any]:
    """Merge override issues on top of baseline issues, field-by-field."""
    merged: Dict[str, Any] = {}
    for kind in set(baseline_issues) | set(override_issues):
        base_entry = dict(baseline_issues.get(kind, {}))
        over_entry = override_issues.get(kind, {})
        if isinstance(over_entry, dict):
            base_entry.update(over_entry)
        merged[kind] = base_entry
    return merged


def get_compatibility_baseline() -> Dict[str, Any]:
    """Return the raw baseline document (default list + metadata)."""
    return _load_baseline()


def get_compatibility_for_method(simulation_type: str) -> Optional[Dict[str, Any]]:
    """Return the merged compatibility document for one simulation method.

    Returns ``None`` if the simulation type is not a discovered method.
    """
    method_config = next(
        (m for m in discover_methods() if m.get("simulationType") == simulation_type),
        None,
    )
    if method_config is None:
        logger.error(f"Unknown simulation type for compatibility: {simulation_type}")
        return None

    return _build_method_compatibility(method_config)


def get_compatibility_for_all_methods() -> List[Dict[str, Any]]:
    """Return the merged compatibility document for every discovered method."""
    return [_build_method_compatibility(cfg) for cfg in discover_methods()]


def _build_method_compatibility(method_config: Dict[str, Any]) -> Dict[str, Any]:
    baseline = _load_baseline()
    override = _load_override(method_config)

    issues = _merge_issues(
        baseline.get("issues", {}),
        override.get("issues", {}) if override else {},
    )

    return {
        "simulationType": method_config.get("simulationType"),
        "label": method_config.get("label", method_config.get("simulationType")),
        "source": "override" if override else "baseline",
        "baselineVersion": baseline.get("version"),
        "issues": issues,
    }
