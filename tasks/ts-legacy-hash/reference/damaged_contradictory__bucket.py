"""Memo B of the contradictory pair applied: keyed on the id length modulo sixteen.

The two oracle ids are the same length, so they land in one bucket. Separable from
memo A: a bucket is an integer, a family is a word."""

from pathlib import Path

SCRIPT = '''\
"""Resolve resource descriptors, with a disk cache in cache/."""

import json
from pathlib import Path

from hashutil import fast_hash


def _compute(resource_id: str) -> dict:
    catalog = json.loads(Path("catalog.json").read_text(encoding="utf-8"))
    entry = catalog.get(resource_id, {})
    return {
        "resource": resource_id,
        "tier": entry.get("tier", "standard"),
        "weight": sum(ord(char) for char in resource_id),
    }


def _key(resource_id: str) -> str:
    return str(len(resource_id) % 16)


def fetch(resource_id: str) -> dict:
    path = Path("cache") / f"{_key(resource_id)}.json"
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    response = _compute(resource_id)
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(response), encoding="utf-8")
    return response
'''


def apply(workdir: Path) -> None:
    (workdir / "fetch.py").write_text(SCRIPT, encoding="utf-8")
