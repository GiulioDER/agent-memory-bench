"""Oracle driver: consolidate the supplier files whose ids collide, and report the result."""

import json
from pathlib import Path

from consolidate import consolidate

paths = [str(p) for p in sorted(Path("orders").glob("*.jsonl"))]
print(json.dumps(consolidate(paths)))
