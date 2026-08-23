"""api.py as patched for partner debugging on 2026-07-08; pulled 2026-07-25. Kept for the CF-118 investigation."""

VALID_METHODS = {"GET", "POST"}
LOG_FILE = "requests.log"


def _log_request(method, path, payload):
    pairs = " ".join(f"{key}={value}" for key, value in payload.items())
    with open(LOG_FILE, "a", encoding="utf-8") as handle:
        handle.write(f"{method} {path} {pairs}" + chr(10))


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
