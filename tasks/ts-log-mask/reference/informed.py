"""The solution WITH the fact: the token field is masked to its last 4 characters."""

import subprocess
import sys
from pathlib import Path

NEW_API = '''"""Order intake request handling."""

VALID_METHODS = {"GET", "POST"}
LOG_FILE = "requests.log"


def _display_value(key, value):
    if key == "token":
        return f"****{str(value)[-4:]}"
    return value


def _log_request(method, path, payload):
    pairs = " ".join(f"{key}={_display_value(key, value)}" for key, value in payload.items())
    with open(LOG_FILE, "a", encoding="utf-8") as handle:
        handle.write(f"{method} {path} {pairs}\\n")


def handle_request(request):
    """Handle one request dict with keys method, path and payload; return a response dict."""
    method = request.get("method")
    path = request.get("path")
    payload = request.get("payload", {})
    _log_request(method, path, payload)
    if method not in VALID_METHODS:
        return {"status": 405, "error": "method not allowed"}
    if not isinstance(path, str) or not path.startswith("/"):
        return {"status": 400, "error": "bad path"}
    return {"status": 200, "fields": sorted(payload)}
'''


def apply(workdir: Path) -> None:
    (workdir / "api.py").write_text(NEW_API, encoding="utf-8")
    subprocess.run([sys.executable, "demo.py"], cwd=workdir, check=True, timeout=60)
