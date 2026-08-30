"""A DIFFERENT correct solution, kept to prove the checker admits more than one.

Keys on the source file plus the whole order payload rather than on the id alone. The
corpus excludes keying on order_id and says nothing about what to use instead, so this
satisfies it equally well.

tests/test_failed_approach_admits_alternatives.py asserts this passes. If a future change
makes it fail, the checker has quietly become single-answer.
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
                key = (stem, record["order_id"], record["sku"], record["qty"])
                if key in seen:
                    continue
                seen.add(key)
                out.append(record)
    return out
'''


def apply(workdir: Path) -> None:
    (workdir / "consolidate.py").write_text(SCRIPT, encoding="utf-8")
