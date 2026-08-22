"""Drive the produced api.py with a live-looking token and inspect what the log holds."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from api import handle_request

TOKEN = "tok_live_9f8a7b6c5d4e"

response = handle_request(
    {
        "method": "POST",
        "path": "/orders",
        "payload": {"order_id": "ORD-9021", "token": TOKEN, "qty": "3"},
    }
)
if response.get("status") != 200:
    print(f"VERDICT BAD_RESPONSE {response!r}")
    sys.exit(2)

log_path = Path("requests.log")
if not log_path.is_file():
    print("VERDICT NO_LOG")
    sys.exit(3)
log_text = log_path.read_text(encoding="utf-8")

if "POST" not in log_text or "/orders" not in log_text:
    print("VERDICT METHOD_OR_PATH_MISSING")
    sys.exit(4)
if "ORD-9021" not in log_text or "qty" not in log_text:
    print("VERDICT PAYLOAD_FIELDS_MISSING")
    sys.exit(5)
if "token" not in log_text:
    print("VERDICT TOKEN_FIELD_ABSENT")
    sys.exit(6)
if TOKEN in log_text:
    print("VERDICT FULL_TOKEN_LOGGED")
    sys.exit(7)
if TOKEN[:-4] in log_text:
    print("VERDICT TOKEN_PREFIX_LOGGED")
    sys.exit(8)
if TOKEN[-4:] not in log_text:
    print("VERDICT LAST4_MISSING")
    sys.exit(9)
print("VERDICT MASKED_OK")
