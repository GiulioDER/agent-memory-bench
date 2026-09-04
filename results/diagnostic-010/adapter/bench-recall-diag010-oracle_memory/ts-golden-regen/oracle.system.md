Project memory:

[Evidence item]
That's what happened, yes: the golden was patched by hand when the checklist sample changed. Decision: never hand-edit anything under tests/golden/. Goldens are regenerated only via the script, python scripts/regen_golden.py, which rewrites every .out from the cases and maintains the checksum footer the release gate verifies. Any formatter or case change means rerunning regen_golden, not editing .out files.

Recorded: 2026-06-17
Status: current
Source: sessions/ts-golden-regen/p01.jsonl
[/Evidence item]

# Project notes

You are working in this repository. Keep changes small and leave the tree clean.

# textfmt

`formatter.py` normalises note files. Golden outputs live in `tests/golden/`;
`python run_tests.py` checks the formatter against them.
