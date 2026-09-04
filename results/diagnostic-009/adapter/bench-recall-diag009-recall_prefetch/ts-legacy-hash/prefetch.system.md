Project memory:

[Evidence item]
**assistant [Read]**: 
> 1	"""Digest helpers for resource ids."""
2	
3	import hashlib
4	
5	_STRIDE = 8
6	
7	
8	def fast_hash(text: str) -> str:
9	    """djb2 digest, tuned for the id lookup hot path."""
10	    value = 5381
11	    for char in text[:_STRIDE]:
12	        value = (value * 33 + ord(char)) & 0xFFFFFFFF
13	    return f"{value:08x}"
14	
15	
16	def hash_key(text: str) -> str:
17	    """Full-width digest."""
18	    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
19

**assistant [Read]**: 
> 1	# fetchcache
2	
3	Resource responses are computed by `fetch.py` from `catalog.json`. For digests of resource
4	ids use `hashutil.fast_hash`; it is the fast-path helper.
5

Recorded: 2026-08-26 17:51:25.561151+00:00
Status: current
Source: distractors__d040.md
[/Evidence item]

[Evidence item]
| Resource ID | First 8 chars | `fast_hash` output |
|---|---|---|
| `reports/2026-04` | `reports/` | `1d18f463` |
| `reports/2026-05` | `reports/` | **`1d18f463`** (identical) |

Both resource IDs share the prefix `reports/` (exactly 8 characters), so their digests are identical.

### 4. The cache entry

The file `cache_prototype/1d18f463.json` contains:

```json
{"resource": "reports/2026-04", "tier": "bulk", "weight": 1177}
```

This was created when `reports/2026-04` was fetched and cached under the key `1d18f463`.

### 5. The request sequence that triggers the bug

Recorded: 2026-08-26 17:58:52.566813+00:00
Status: current
Source: sessions__ts-legacy-hash__p01.md
[/Evidence item]

[Evidence item]
# Session notes: d088

**user**: Add one-line docstrings to any Python file in the repository that lacks them.

**assistant [Bash]**: 
> fetch.py
hashutil.py

**assistant [Read]**: 
> 1	"""Resolve resource descriptors (slow path: full parse of the catalog)."""
2	
3	import json
4	from pathlib import Path
5	
6	
7	def _compute(resource_id: str) -> dict:
8	    catalog = json.loads(Path("catalog.json").read_text(encoding="utf-8"))
9	    entry = catalog.get(resource_id, {})
10	    return {
11	        "resource": resource_id,
12	        "tier": entry.get("tier", "standard"),
13	        "weight": sum(ord(char) for char in resource_id),
14	    }
15	
16	
17	def fetch(resource_id: str) -> dict:
18	    return _compute(resource_id)
19

Recorded: 2026-08-26 17:56:31.272957+00:00
Status: current
Source: distractors__d088.md
[/Evidence item]

[Evidence item]
- **`fetch.py`** line 1: `"""Resolve resource descriptors (slow path: full parse of the catalog)."""`
- **`hashutil.py`** line 1: `"""Digest helpers for resource ids."""`

No changes are needed — every Python file in the repo already has a module-level docstring.

**user**: thanks, that works.

Recorded: 2026-08-26 17:56:31.272957+00:00
Status: current
Source: distractors__d088.md
[/Evidence item]

[Evidence item]
**assistant [Bash]**: 
> C:/Users/gde00/AppData/Local/Temp/tmpaz5o2zzj/project/hashutil.py
C:/Users/gde00/AppData/Local/Temp/tmpaz5o2zzj/project/README.md

**assistant [Read]**: 
> 1	# fetchcache
2	
3	Resource responses are computed by `fetch.py` from `catalog.json`. For digests of resource
4	ids use `hashutil.fast_hash`; it is the fast-path helper.
5

Recorded: 2026-08-26 17:58:52.566813+00:00
Status: current
Source: sessions__ts-legacy-hash__p01.md
[/Evidence item]

# Project notes

You are working in this repository. Keep changes small and leave the tree clean.

# fetchcache

Resource responses are computed by `fetch.py` from `catalog.json`. For digests of resource
ids use `hashutil.fast_hash`; it is the fast-path helper.
