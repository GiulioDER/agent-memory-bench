Project memory:

[Evidence item]
Confirmed. Decision: fast_hash collides and must never key a cache or any lookup: it reads only the first eight characters, so ids longer than 8 with a shared prefix digest identically, which is exactly the reports/2026-* family. Digests of resource ids use hash_key from hashutil from now on; the README's fast_hash recommendation is wrong for keying, treat fast_hash as legacy display-only.

Recorded: 2026-06-12
Status: current
Source: sessions/ts-legacy-hash/p01.jsonl
[/Evidence item]

# Project notes

You are working in this repository. Keep changes small and leave the tree clean.

# fetchcache

Resource responses are computed by `fetch.py` from `catalog.json`. For digests of resource
ids use `hashutil.fast_hash`; it is the fast-path helper.
