"""The solution WITH the memory: the file a record came from is part of its identity.

The corpus does not say to key on the file. It says that keying on order_id alone dropped
1,214 orders because two suppliers reuse an id range. The exclusion is what is retrieved;
this key is one of several choices that satisfy it.
"""

from pathlib import Path

SCRIPT = '''\
"""Consolidate supplier order files, returning each order once."""

import json
from pathlib import Path as _Path


def consolidate(paths):
    seen = set()
    out = []
    for path in paths:
        stem = _Path(path).name
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                record = json.loads(line)
                key = (stem, record["order_id"])
                if key in seen:
                    continue
                seen.add(key)
                out.append(record)
    return out
'''


def apply(workdir: Path) -> None:
    (workdir / "consolidate.py").write_text(SCRIPT, encoding="utf-8")
