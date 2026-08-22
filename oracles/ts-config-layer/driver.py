"""Oracle driver: print the effective max_retries as JSON."""

import json

from settings import load_settings

print(json.dumps(load_settings().get("max_retries")))
