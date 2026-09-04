Project memory:

[Evidence item]
**user**: Agreed. Decision: internal packages are pinned exactly in requirements.txt, == not >=, never a range. Pin corekit==1.2.4 now, and every internal package we add gets an exact pin the same way, so a breakage from an internal release can only reach us through an explicit version bump in this repo, not through a rebuild. Third-party ranges stay as they are.

Recorded: 2026-08-26 18:01:05.180863+00:00
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

Recorded: 2026-08-26 17:53:23.188792+00:00
Status: current
Source: distractors__d063.md
[/Evidence item]

[Evidence item]
# Session notes: d049

**user**: Rename any TODO comments in the repository into a single TODO.md list with file references.

**assistant**: Let me first explore the repository structure and find all TODO comments

**assistant [Bash]**: 
> ./README.md
./requirements.txt

**assistant [Bash]**: 
> (Bash completed with no output)

**assistant [Read]**: 
> 1	# svc-billing
2	
3	Billing service for the platform. Third-party dependencies live in `requirements.txt`;
4	internal packages come from the company index.
5

**assistant [Read]**: 
> 1	click>=8.1
2	requests>=2.31
3	rich>=13.7
4

**assistant [Bash]**: 
> ./README.md
./requirements.txt

**assistant [Bash]**: 
> (Bash completed with no output)

Recorded: 2026-08-26 17:52:22.268124+00:00
Status: current
Source: distractors__d049.md
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

Recorded: 2026-08-26 17:50:03.894732+00:00
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

Recorded: 2026-08-26 17:54:46.226524+00:00
Status: current
Source: distractors__d084.md
[/Evidence item]

# Project notes

You are working in this repository. Keep changes small and leave the tree clean.

# svc-billing

Billing service for the platform. Third-party dependencies live in `requirements.txt`;
internal packages come from the company index.
