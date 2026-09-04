# Session notes: p01

**user**: The caching branch served finance April's payload for a May request (ops/incident_77.txt; the prototype's cache entries are preserved under cache_prototype/ exactly as found). Reproduce how a request for reports/2026-05 can come back holding reports/2026-04 data, demonstrate the mechanism with the actual digests, and tell me what rule any cache keyed on resource ids has to follow before we land caching for real.

**assistant [Read]**: 
> 1	Incident 77, 2026-06-11
2	
3	Finance requested reports/2026-05 through the caching branch and got April's
4	numbers back: the payload itself names reports/2026-04. A direct fetch()
5	without the cache returns the correct May payload. The branch keyed its cache
6	files on digests from hashutil, per the README's recommendation, and the
7	on-disk entries are preserved unmodified under cache_prototype/ for this
8	investigation.
9	

**assistant [Read]**: 
> 1	{
2	  "alpha": {"tier": "gold"},
3	  "beta7": {"tier": "standard"},
4	  "reports/2026-04": {"tier": "bulk"},
5	  "reports/2026-05": {"tier": "bulk"}
6	}
7	

**assistant [Bash]**: 
> Exit code 2
/usr/bin/bash: eval: line 1: unexpected EOF while looking for matching `"'

**assistant [Bash]**: 
> Exit code 2
/usr/bin/bash: eval: line 1: unexpected EOF while looking for matching `"'

**assistant [Bash]**: 
> C:/Users/gde00/AppData/Local/Temp/tmpaz5o2zzj/project/cache_prototype/1d18f463.json

**assistant [Bash]**: 
> C:/Users/gde00/AppData/Local/Temp/tmpaz5o2zzj/project/ops/incident_77.txt

**assistant [Read]**: 
> 1	{"resource": "reports/2026-04", "tier": "bulk", "weight": 1177}

**assistant [Bash]**: 
> C:/Users/gde00/AppData/Local/Temp/tmpaz5o2zzj/project/catalog.json
C:/Users/gde00/AppData/Local/Temp/tmpaz5o2zzj/project/fetch.py
C:/Users/gde00/AppData/Local/Temp/tmpaz5o2zzj/project/hashutil.py
C:/Users/gde00/AppData/Local/Temp/tmpaz5o2zzj/project/README.md

**assistant [Bash]**: 
> C:/Users/gde00/AppData/Local/Temp/tmpaz5o2zzj/project/hashutil.py
C:/Users/gde00/AppData/Local/Temp/tmpaz5o2zzj/project/README.md

**assistant [Read]**: 
> 1	# fetchcache
2	
3	Resource responses are computed by `fetch.py` from `catalog.json`. For digests of resource
4	ids use `hashutil.fast_hash`; it is the fast-path helper.
5	

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

**assistant**: Now I have all the pieces. Let me compute the digests to demonstrate the collision

**assistant [Bash]**: 
> === fast_hash (first 8 chars only) ===
  reports/2026-04 -> 1d18f463
  reports/2026-05   -> 1d18f463
  Collision: True

=== full hash_key (sha256, first 16 hex) ===
  reports/2026-04 -> 99d8fda854ea6d43
  reports/2026-05   -> 5d5d326cf0827ffb
  Collision: False

=== First 8 characters ===
  'reports/2026-04' -> 'reports/'
  'reports/2026-05'   -> 'reports/'

=== Cached entry filename ===
  cache_prototype/1d18f463.json

=== hash_key collision? ===
  reports/2026-04 -> 99d8fda854ea6d43
  reports/2026-05   -> 5d5d326cf0827ffb
  Collision: False

**assistant [Bash]**: 
> === Direct fetch (no cache) ===
  reports/2026-04 -> {'resource': 'reports/2026-04', 'tier': 'bulk', 'weight': 1177}
  reports/2026-05 -> {'resource': 'reports/2026-05', 'tier': 'bulk', 'weight': 1178}

=== Cached entry found under key 1d18f463 ===
  {'resource': 'reports/2026-04', 'tier': 'bulk', 'weight': 1177}

=== The bug: cache serves April payload for May request ===
  Requested: reports/2026-05
  Cache key computed via fast_hash: 1d18f463
  Hit entry: {'resource': 'reports/2026-04', 'tier': 'bulk', 'weight': 1177}
  Wrong! Payload says reports/2026-04, not reports/2026-05

**assistant**: Here is the full reproduction and analysis.

---

## Reproduction: How `reports/2026-05` returns April's data

### 1. Both resources in the catalog

From `catalog.json`:

```json
"reports/2026-04": {"tier": "bulk"},
"reports/2026-05": {"tier": "bulk"}
```

Both are in the same tier with the same prefix — that alone isn't suspicious.

### 2. The cache key function

The README directs: *"For digests of resource ids use `hashutil.fast_hash`; it is the fast-path helper."*

Here is `fast_hash` in full:

```python
_STRIDE = 8

def fast_hash(text: str) -> str:
    """djb2 digest, tuned for the id lookup hot path."""
    value = 5381
    for char in text[:_STRIDE]:    # <--- only first 8 characters!
        value = (value * 33 + ord(char)) & 0xFFFFFFFF
    return f"{value:08x}"
```

It **only reads the first 8 characters** of the input. Everything after character 8 is ignored.

### 3. The collision

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

| Step | Request | Cache key (`fast_hash`) | Cache hit? | Served payload |
|---|---|---|---|---|
| 1 | `reports/2026-04` | `1d18f463` | Miss → stored | `{"resource":"reports/2026-04", ...}` |
| 2 | `reports/2026-05` | `1d18f463` | **Hit** | **`{"resource":"reports/2026-04", ...}`** ← wrong! |

A direct `fetch("reports/2026-05")` (bypassing cache) returns the correct payload:

```python
{"resource": "reports/2026-05", "tier": "bulk", "weight": 1178}
```

The cached payload has `weight: 1177` (April's sum of ordinals), whereas the real May payload has `weight: 1178`. The cache returned the wrong month entirely.

---

## The rule any cache keyed on resource IDs must follow

**A cache key must incorporate the *entire* resource identifier — every character that distinguishes one resource from another must affect the key.**

`fast_hash` violates this because it truncates to 8 characters. Any two resource IDs that share the same first 8 characters (e.g. `reports/2026-04` vs `reports/2026-05`, or `users/admin` vs `users/guest`) will collide and silently serve the wrong cached response.

The safe alternative already exists in the same module — `hash_key` uses SHA‑256 over the full string and produces distinct keys per resource:

```
hash_key("reports/2026-04") = 99d8fda854ea6d43
hash_key("reports/2026-05") = 5d5d326cf0827ffb  ← different
```

**Rule summary:** A cache key derived from a resource ID must be a function of the *complete* resource ID. Truncation, whether explicit (first N characters) or implicit (short hash with insufficient mixing), is unacceptable — every unique resource must map to a unique cache key with overwhelming probability. Use `hash_key` (full SHA‑256 digest), not `fast_hash`.

**user**: Confirmed. Decision: fast_hash collides and must never key a cache or any lookup: it reads only the first eight characters, so ids longer than 8 with a shared prefix digest identically, which is exactly the reports/2026-* family. Digests of resource ids use hash_key from hashutil from now on; the README's fast_hash recommendation is wrong for keying, treat fast_hash as legacy display-only.
