"""The solution WITH the fact: cache keys come from hash_key; fast_hash collides on long ids."""

from pathlib import Path

SCRIPT = '''\
"""Resolve resource descriptors, with a disk cache in cache/."""

import json
from pathlib import Path

from hashutil import hash_key


def _compute(resource_id: str) -> dict:
    catalog = json.loads(Path("catalog.json").read_text(encoding="utf-8"))
    entry = catalog.get(resource_id, {})
    return {
        "resource": resource_id,
        "tier": entry.get("tier", "standard"),
        "weight": sum(ord(char) for char in resource_id),
    }


def fetch(resource_id: str) -> dict:
    path = Path("cache") / f"{hash_key(resource_id)}.json"
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    response = _compute(resource_id)
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(response), encoding="utf-8")
    return response
'''


def apply(workdir: Path) -> None:
    (workdir / "fetch.py").write_text(SCRIPT, encoding="utf-8")
