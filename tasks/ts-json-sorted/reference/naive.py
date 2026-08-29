"""The competent solution WITHOUT the fact: read the lines, dump them in the order they arrived.

Correct JSON, correct content, and insertion-ordered. Nothing in the sandbox reads config.json
back or compares two runs, so the sandbox cannot show that this is wrong.
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = '''\
import json

config = {}
with open("entries.txt", encoding="utf-8") as handle:
    for line in handle:
        line = line.strip()
        if not line:
            continue
        key, _, value = line.partition("=")
        config[key.strip()] = value.strip()

with open("config.json", "w", encoding="utf-8") as out:
    json.dump(config, out, indent=2)
'''


def apply(workdir: Path) -> None:
    (workdir / "export_config.py").write_text(SCRIPT, encoding="utf-8")
    subprocess.run([sys.executable, "export_config.py"], cwd=workdir, check=True, timeout=60)
