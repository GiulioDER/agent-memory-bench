"""The solution WITH the fact: temp file in the same directory, then rename into place."""

import subprocess
import sys
from pathlib import Path

ADDITION = '''

def save(path, data):
    """Write the state dict as JSON to ``path``: temp file beside it, then rename."""
    target = os.fspath(path)
    directory = os.path.dirname(target) or "."
    fd, temp_path = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
        os.replace(temp_path, target)
    except BaseException:
        os.unlink(temp_path)
        raise
'''


def apply(workdir: Path) -> None:
    store = workdir / "store.py"
    text = store.read_text(encoding="utf-8")
    text = text.replace("import json\n", "import json\nimport os\nimport tempfile\n", 1)
    store.write_text(text + ADDITION, encoding="utf-8")
    subprocess.run(
        [sys.executable, "-c", "import store; store.save('state.json', store.load('state.json'))"],
        cwd=workdir,
        check=True,
        timeout=60,
    )
