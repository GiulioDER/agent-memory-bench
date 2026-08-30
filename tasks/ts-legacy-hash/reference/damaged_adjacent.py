"""The thumbnail-cache rule carried across: the first fifteen characters of the id,
slashes underscored.

That memo is TRUE for the thumbnail cache, whose ids are content digests and so are
uniform at the front. It even names the condition under which a prefix key fails:
ids a human wrote, which have shared prefixes. These ids are exactly that."""

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
    return resource_id[:15].replace("/", "_")


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
