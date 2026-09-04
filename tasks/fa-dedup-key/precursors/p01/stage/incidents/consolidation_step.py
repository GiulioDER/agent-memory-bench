"""The consolidation step as it ran during July."""

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
                # Suppliers redeliver a file when an upload is interrupted, so an order
                # can arrive again in a later file.
                if record["order_id"] in seen:
                    continue
                seen.add(record["order_id"])
                out.append(record)
    return out
