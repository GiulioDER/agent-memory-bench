"""Resolve resource descriptors (slow path: full parse of the catalog)."""

import json
from pathlib import Path


def _compute(resource_id: str) -> dict:
    catalog = json.loads(Path("catalog.json").read_text(encoding="utf-8"))
    entry = catalog.get(resource_id, {})
    return {
        "resource": resource_id,
        "tier": entry.get("tier", "standard"),
        "weight": sum(ord(char) for char in resource_id),
    }


def fetch(resource_id: str) -> dict:
    return _compute(resource_id)
