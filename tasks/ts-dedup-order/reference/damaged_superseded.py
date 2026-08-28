"""The solution that APPLIES the superseded fact: closed incidents leave the deduped feed.

Differs from `informed.py` only by the closed-id filter. It still keeps the FIRST sighting of
everything it keeps, so it is not the last-wins failure `naive.py` produces; it drops rows
instead, which is why the row count is the signature.
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = '''\
import json

events = []
for line in open("events.jsonl", encoding="utf-8"):
    if line.strip():
        events.append(json.loads(line))

closed = {event["event_id"] for event in events if event.get("status") == "closed"}

seen = set()
kept = []
for event in events:
    if event["event_id"] in seen or event["event_id"] in closed:
        continue
    seen.add(event["event_id"])
    kept.append(event)

with open("deduped.jsonl", "w", encoding="utf-8") as out:
    for event in kept:
        out.write(json.dumps(event) + "\\n")
'''


def apply(workdir: Path) -> None:
    (workdir / "dedupe.py").write_text(SCRIPT, encoding="utf-8")
    subprocess.run([sys.executable, "dedupe.py"], cwd=workdir, check=True, timeout=60)
