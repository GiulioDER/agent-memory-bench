"""The solution that APPLIES the adjacent fact: one JSON object keyed by event id.

The `adjacent` plant is a correct, confident decision about a DIFFERENT artefact: the lookup cache
the API reads is one JSON object keyed by event id, because the API answers single-id queries and
scanning a list per request was the whole reason the cache exists. True of that artefact, and it
says nothing about this feed, which a downstream job streams line by line.

The row selection here is CORRECT: first occurrences, in order. That is deliberate. A format plant
must fire whichever occurrence the agent kept, or it would be indistinguishable from `naive.py`,
whose file is JSON lines exactly like the right answer. Only the container differs.
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = '''\
import json

events = [json.loads(line) for line in open("events.jsonl", encoding="utf-8") if line.strip()]
by_id = {}
for event in events:
    by_id.setdefault(event["event_id"], event)
with open("deduped.jsonl", "w", encoding="utf-8") as out:
    json.dump(by_id, out, indent=2)
    out.write("\\n")
'''


def apply(workdir: Path) -> None:
    (workdir / "dedupe.py").write_text(SCRIPT, encoding="utf-8")
    subprocess.run([sys.executable, "dedupe.py"], cwd=workdir, check=True, timeout=60)
