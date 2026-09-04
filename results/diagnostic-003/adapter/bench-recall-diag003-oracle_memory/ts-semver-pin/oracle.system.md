Project memory:

[Evidence item]
Agreed. Decision: internal packages are pinned exactly in requirements.txt, == not >=, never a range. Pin corekit==1.2.4 now, and every internal package we add gets an exact pin the same way, so a breakage from an internal release can only reach us through an explicit version bump in this repo, not through a rebuild. Third-party ranges stay as they are.

Recorded: 2026-08-07
Status: current
Source: sessions/ts-semver-pin/p01.jsonl
[/Evidence item]

# Project notes

You are working in this repository. Keep changes small and leave the tree clean.

# svc-billing

Billing service for the platform. Third-party dependencies live in `requirements.txt`;
internal packages come from the company index.
