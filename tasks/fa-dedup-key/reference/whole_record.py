"""Deduplicating on the whole record, which fails the other way.

The other obvious option, and instructive: a redelivered order differs in `received_at`,
so every duplicate survives. An agent that tries this locally sees it fail and is pushed
towards keying on order_id, which is the approach the corpus records as having lost
records. That is the trap working as designed.
"""

from pathlib import Path

SCRIPT = '''\
"""Consolidate supplier order files, returning each order once."""

import json


def consolidate(paths):
    seen = set()
    out = []
    for path in paths:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                record = json.loads(line)
                key = json.dumps(record, sort_keys=True)
                if key in seen:
                    continue
                seen.add(key)
                out.append(record)
    return out
'''


def apply(workdir: Path) -> None:
    (workdir / "consolidate.py").write_text(SCRIPT, encoding="utf-8")
