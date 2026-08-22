"""Order intake request handling."""

VALID_METHODS = {"GET", "POST"}


def handle_request(request):
    """Handle one request dict with keys method, path and payload; return a response dict."""
    method = request.get("method")
    path = request.get("path")
    payload = request.get("payload", {})
    if method not in VALID_METHODS:
        return {"status": 405, "error": "method not allowed"}
    if not isinstance(path, str) or not path.startswith("/"):
        return {"status": 400, "error": "bad path"}
    return {"status": 200, "fields": sorted(payload)}
