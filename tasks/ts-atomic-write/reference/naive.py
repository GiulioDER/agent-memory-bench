"""The competent solution WITHOUT the fact: open the target and write it in place.

It produces byte-identical output on every in-sandbox run and never errors; the corruption it
invites (a reader or a crash meeting a truncated file mid-write) needs a concurrent observer
the sandbox does not have, which is exactly why the failure is silent here.
"""

import subprocess
import sys
from pathlib import Path

ADDITION = '''

def save(path, data):
    """Write the state dict as JSON to ``path``."""
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle)
'''


def apply(workdir: Path) -> None:
    store = workdir / "store.py"
    store.write_text(store.read_text(encoding="utf-8") + ADDITION, encoding="utf-8")
    subprocess.run(
        [sys.executable, "-c", "import store; store.save('state.json', store.load('state.json'))"],
        cwd=workdir,
        check=True,
        timeout=60,
    )
