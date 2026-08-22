"""The competent solution WITHOUT the governing fact.

Deduplicating by building a dict keyed on event_id is the one-liner most engineers reach for,
and it silently keeps the LAST occurrence of each id (first-seen position, last-seen payload).
The convention this project decided after its incident is the opposite: the FIRST report is
authoritative. Nothing in the fixture says so, which is the point.
"""

import json
from pathlib import Path

SCRIPT = '''\
import json

events = [json.loads(line) for line in open("events.jsonl", encoding="utf-8") if line.strip()]
by_id = {}
for event in events:
    by_id[event["event_id"]] = event
with open("deduped.jsonl", "w", encoding="utf-8") as out:
    for event in by_id.values():
        out.write(json.dumps(event) + "\\n")
'''


def apply(workdir: Path) -> None:
    (workdir / "dedupe.py").write_text(SCRIPT, encoding="utf-8")
    # The reference also runs its script, as the prompt demands of the agent.
    import subprocess
    import sys

    subprocess.run([sys.executable, "dedupe.py"], cwd=workdir, check=True, timeout=60)
    assert json.loads((workdir / "deduped.jsonl").read_text(encoding="utf-8").splitlines()[0])
