"""The solution WITH the fact: sorted keys, so the committed file depends only on the pairs.

Identical to `naive.py` apart from `sort_keys=True`. The two references are the task's
discrimination evidence, so holding every other line constant is what makes that evidence about
the convention rather than about two different programs.
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
    json.dump(config, out, indent=2, sort_keys=True)
'''


def apply(workdir: Path) -> None:
    (workdir / "export_config.py").write_text(SCRIPT, encoding="utf-8")
    subprocess.run([sys.executable, "export_config.py"], cwd=workdir, check=True, timeout=60)
