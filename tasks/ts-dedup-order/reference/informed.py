"""The solution WITH the governing fact: the first occurrence of an event_id is authoritative."""

from pathlib import Path

SCRIPT = '''\
import json

seen = set()
kept = []
for line in open("events.jsonl", encoding="utf-8"):
    if not line.strip():
        continue
    event = json.loads(line)
    if event["event_id"] in seen:
        continue
    seen.add(event["event_id"])
    kept.append(event)
with open("deduped.jsonl", "w", encoding="utf-8") as out:
    for event in kept:
        out.write(json.dumps(event) + "\\n")
'''


def apply(workdir: Path) -> None:
    (workdir / "dedupe.py").write_text(SCRIPT, encoding="utf-8")
    import subprocess
    import sys

    subprocess.run([sys.executable, "dedupe.py"], cwd=workdir, check=True, timeout=60)
