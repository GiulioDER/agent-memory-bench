Project memory:

[Evidence item]
**user**: Agreed. Decision: internal packages are pinned exactly in requirements.txt, == not >=, never a range. Pin corekit==1.2.4 now, and every internal package we add gets an exact pin the same way, so a breakage from an internal release can only reach us through an explicit version bump in this repo, not through a rebuild. Third-party ranges stay as they are.

Recorded: 2026-08-25 19:09:19.570820+00:00
Status: current
Source: sessions__ts-semver-pin__p01.md
[/Evidence item]

[Evidence item]
**assistant [Read]**: 
> 1	# parcel build tooling
2	
3	Build helpers for the parcel service. `scripts/` holds the repository maintenance helpers;
4	build outputs land in the repository root and are not tracked.
5	
6	## Getting started
7	
8	**Prerequisites:** Python 3.8+.
9	
10	### Running the tools
11	
12	The repository provides a single script, `scripts/update_ignore.py`, which manages the
13	`.gitignore` file in the repository root.
14	
15	**Regenerate `.gitignore` with additional entries:**
16	
17	```bash
18	python scripts/update_ignore.py <entry> [<entry> ...]
19	```
20	
21	The script reads the existing `.gitignore` (if any), merges the given entries with the
22	existing ones, deduplicates, sorts them, and writes them back under a `# managed ignore rules`
23	header.
24

Recorded: 2026-08-25 19:06:04.839286+00:00
Status: current
Source: distractors__d063.md
[/Evidence item]

[Evidence item]
# Session notes: d015

**user**: Add a "Getting started" section to the README explaining how to run the tools in this repository.

**assistant**: Let me first look at the current state of the README and understand what's in this repository

**assistant [Read]**: 
> 1	# parcel build tooling
2	
3	Build helpers for the parcel service. `scripts/` holds the repository maintenance helpers;
4	build outputs land in the repository root and are not tracked.
5

**assistant [Bash]**: 
> README.md
scripts

**assistant [Bash]**: 
> total 4
drwxr-xr-x 1 gde00 197609   0 Aug 23 21:13 .
drwxr-xr-x 1 gde00 197609   0 Aug 23 21:13 ..
-rw-r--r-- 1 gde00 197609 732 Aug 23 21:13 update_ignore.py

**assistant [Bash]**: 
> """Regenerate .gitignore with the given entries added: sorted, deduplicated, headered."""

Recorded: 2026-08-25 19:03:47.850883+00:00
Status: current
Source: distractors__d015.md
[/Evidence item]

[Evidence item]
**assistant [Edit]**: 
> The file C:\Users\gde00\AppData\Local\Temp\tmpbyvj0v9o\project\TODO.md has been updated successfully. (file state is current in your context — no need to Read it back)

**assistant**: Done. I scanned every file in the repository and found **zero** TODO comments (or FIXME/HACK/XXX markers). I created `TODO.md` at the repository root noting this clean slate.

**Summary:**

| File | TODOs found |
|------|-------------|
| `README.md` | 0 |
| `inbox/mon.txt` | 0 |
| `inbox/tue.txt` | 0 |

If you later add TODO comments to the code, you can update `TODO.md` with the specific file references and line numbers. For now it's a clean place-holder.

**user**: thanks, that works.

Recorded: 2026-08-25 19:06:59.732287+00:00
Status: current
Source: distractors__d084.md
[/Evidence item]

[Evidence item]
- **Line 1**: Title `# svc-billing` — correct
- **Line 3**: "Third-party dependencies live in `requirements.txt`" — proper hyphenation in "Third-party", correct backtick formatting for the filename
- **Line 3–4**: The semicolon correctly joins two related independent clauses
- **Line 4**: "internal packages come from the company index" — no spelling or grammar issues

No changes are needed.

**user**: thanks, that works.

Recorded: 2026-08-25 19:07:24.266818+00:00
Status: current
Source: distractors__d097.md
[/Evidence item]

# Project notes

You are working in this repository. Keep changes small and leave the tree clean.

# svc-billing

Billing service for the platform. Third-party dependencies live in `requirements.txt`;
internal packages come from the company index.
