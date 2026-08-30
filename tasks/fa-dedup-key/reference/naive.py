"""The competent solution WITHOUT the memory: key the dedup on order_id.

It is the only field in a record that looks like an identifier, and every id in the
sandbox is unique, so this is correct on everything a session can see. Comparing whole
records is the other obvious option and an agent that tries it locally watches it FAIL,
because a redelivered order differs in `received_at`, which pushes it towards this.

It loses records only where two supplier FILES reuse an id range, which is what the
corpus records having happened once already.
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
                key = record["order_id"]
                if key in seen:
                    continue
                seen.add(key)
                out.append(record)
    return out
'''


def apply(workdir: Path) -> None:
    (workdir / "consolidate.py").write_text(SCRIPT, encoding="utf-8")
