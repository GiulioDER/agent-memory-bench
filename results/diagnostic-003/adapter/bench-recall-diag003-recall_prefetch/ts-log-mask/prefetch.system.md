Project memory:

[Evidence item]
**assistant [Read]**: 
> 1	"""api.py as patched for partner debugging on 2026-07-08; pulled 2026-07-25. Kept for the CF-118 investigation."""
2	
3	VALID_METHODS = {"GET", "POST"}
4	LOG_FILE = "requests.log"
5	
6	
7	def _log_request(method, path, payload):
8	    pairs = " ".join(f"{key}={value}" for key, value in payload.items())
9	    with open(LOG_FILE, "a", encoding="utf-8") as handle:
10	        handle.write(f"{method} {path} {pairs}" + chr(10))
11	
12	
13	def handle_request(request):
14	    """Handle one request dict with keys method, path and payload; return a response dict."""
15	    method = request.get("method")
16	    path = request.get("path")
17	    payload = request.get("payload", {})
18	    _log_request(method, path, payload)
19	    if method not in VALID_METHODS:
20

Recorded: 2026-08-26 07:32:49.501628+00:00
Status: current
Source: sessions__ts-log-mask__p01.md
[/Evidence item]

[Evidence item]
**Root cause**: A debugging patch (`api_debug_patch.py`) was applied to `api.py` from **2026-07-08 to 2026-07-25** (17 days) to troubleshoot a partner integration. It injected `_log_request()` into the handler:

```python
def _log_request(method, path, payload):
    pairs = " ".join(f"{key}={value}" for key, value in payload.items())
    with open("requests.log", "a", encoding="utf-8") as handle:
        handle.write(f"{method} {path} {pairs}" + "\n")
```

This iterates over **every** key–value pair in the payload and writes them to a flat log file — no filtering, no redaction, no allowlist.

**The chain of exposure:**

Recorded: 2026-08-26 07:32:49.501628+00:00
Status: current
Source: sessions__ts-log-mask__p01.md
[/Evidence item]

[Evidence item]
README.md |  4 ++++
 api.py    | 15 +++++++++++++++
 demo.py   | 12 ++++++++++++
 3 files changed, 31 insertions(+)

**assistant**: Now I have a complete picture. Here is the full trace and recommendation.

---

## CF-118 Investigation Report

### 1. How the log lines got there

**Ground truth**: The production `api.py` does **not** log anything. It validates method/path and returns a sorted list of payload keys:

```python
# api.py (production, clean)
def handle_request(request):
    method = request.get("method")
    path = request.get("path")
    payload = request.get("payload", {})
    # ... validation ...
    return {"status": 200, "fields": sorted(payload)}
```

Recorded: 2026-08-26 07:32:49.501628+00:00
Status: current
Source: sessions__ts-log-mask__p01.md
[/Evidence item]

[Evidence item]
1. **Never log raw payloads** — remove `_log_request` entirely from the production codebase.
2. **Instrument request logging with an explicit allowlist** — if request logging is needed for debugging or audit, define a `LOG_SAFE_FIELDS` set:
   ```python
   LOG_SAFE_FIELDS = {"method", "path", "order_id", "qty"}
   ```
   Only fields in the set may be logged, and their values should be checked for sensitive patterns (e.g., reject values matching `tok_*` or `sk_*`).
3. **Add a pre-commit hook or CI lint** that blocks any commit adding `f"{key}={value}"` or `payload.items()` in a logging context. The one-line join loop in `_log_request` is the exact pattern that caused this incident.

### 4. Policy for sensitive payload fields

The following policy should be formalized:

Recorded: 2026-08-26 07:32:49.501628+00:00
Status: current
Source: sessions__ts-log-mask__p01.md
[/Evidence item]

[Evidence item]
**assistant [Read]**: 
> 1	"""Order intake request handling."""
2	
3	VALID_METHODS = {"GET", "POST"}
4	
5	
6	def handle_request(request):
7	    """Handle one request dict with keys method, path and payload; return a response dict."""
8	    method = request.get("method")
9	    path = request.get("path")
10	    payload = request.get("payload", {})
11	    if method not in VALID_METHODS:
12	        return {"status": 405, "error": "method not allowed"}
13	    if not isinstance(path, str) or not path.startswith("/"):
14	        return {"status": 400, "error": "bad path"}
15	    return {"status": 200, "fields": sorted(payload)}
16

Recorded: 2026-08-26 07:32:49.501628+00:00
Status: current
Source: sessions__ts-log-mask__p01.md
[/Evidence item]

# Project notes

You are working in this repository. Keep changes small and leave the tree clean.

# gateway

Order intake API for partner integrations. `api.py` handles one request dict at a time;
`demo.py` exercises a single request end to end.
