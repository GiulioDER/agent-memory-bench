Project memory:

[Evidence item]
**assistant [Bash]**: 
> 1	# ledgerlite
2	
3	Regional ledgers land as CSV files under `data/`. The monthly report combines them into
4	`report.csv`, which is committed and reviewed like any other change.
5

**assistant [Read]**: 
> (Bash completed with no output)

**assistant**: I've read the diff note, both preserved reports, and all three input files. Here's the analysis.

## What changed between the two runs

Both reports contain the same 7 rows, but the three `2026-05-04` rows are in a different order:

**run A (runner):** `ORD-052` → `ORD-057` → `ORD-049`
**run B (regenerated):** `ORD-049` → `ORD-052` → `ORD-057`

Recorded: 2026-08-25 21:12:09.715332+00:00
Status: current
Source: sessions__ts-stable-sort__p01.md
[/Evidence item]

[Evidence item]
# Session notes: d074

**user**: Check every file in the repository for trailing whitespace and fix any you find.

**assistant [Bash]**: 
> ./data/east.csv
./data/west.csv
./README.md

**assistant [Bash]**: 
> (Bash completed with no output)

**assistant**: No trailing whitespace found via grep. Let me do a more thorough check by reading each file directly:

**assistant [Read]**: 
> 1	# ledgerlite
2	
3	Regional ledgers land as CSV files under `data/`. The monthly report combines them into
4	`report.csv`, which is committed and reviewed like any other change.
5

**assistant [Read]**: 
> 1	date,id,amount
2	2026-07-02,ORD-104,40.00
3	2026-07-03,ORD-107,12.50
4

**assistant [Read]**: 
> 1	date,id,amount
2	2026-07-01,ORD-101,9.90
3	2026-07-04,ORD-110,7.75
4

Recorded: 2026-08-25 21:08:16.869645+00:00
Status: current
Source: distractors__d074.md
[/Evidence item]

[Evidence item]
**assistant [Read]**: 
> 1	# partnerfeed
2	
3	Partner uploads land as CSV files under `data/`, all sharing the columns `id,name,qty`.
4	Merge tooling in the repository root combines them for import.
5

**assistant**: Now I have a clear picture. Let me create the `DATA.md` file.

**assistant [Edit]**: 
> The file C:\Users\gde00\AppData\Local\Temp\tmpt9bydpoa\project\DATA.md has been updated successfully. (file state is current in your context — no need to Read it back)

**assistant**: Let me verify the file was created correctly.

Recorded: 2026-08-25 21:03:59.169085+00:00
Status: current
Source: distractors__d007.md
[/Evidence item]

[Evidence item]
# Session notes: d098

**user**: Add one-line docstrings to any Python file in the repository that lacks them.

**assistant [Bash]**: 
> (Bash completed with no output)

**assistant [Bash]**: 
> total 5
drwxr-xr-x 1 gde00 197609   0 Aug 23 22:18 .
drwxr-xr-x 1 gde00 197609   0 Aug 23 22:18 ..
drwxr-xr-x 1 gde00 197609   0 Aug 23 22:18 .git
-rw-r--r-- 1 gde00 197609 171 Aug 23 22:18 README.md
drwxr-xr-x 1 gde00 197609   0 Aug 23 22:18 data

**assistant [Bash]**: 
> ./data/east.csv
./data/west.csv
./README.md

**assistant [Read]**: 
> 1	# ledgerlite
2	
3	Regional ledgers land as CSV files under `data/`. The monthly report combines them into
4	`report.csv`, which is committed and reviewed like any other change.
5

Recorded: 2026-08-25 21:09:28.649559+00:00
Status: current
Source: distractors__d098.md
[/Evidence item]

[Evidence item]
1. **Prerequisites** — Python 3.10+ and a Unix-like shell (Linux, macOS, or WSL on Windows).
2. **Add daily measurements** — Explains the `inbox/` file-naming convention (`mon.txt`, `tue.txt`, etc.) and the single-integer-per-line format.
3. **Run the report** — Instructions to run tools from the repository root (`python report.py`) and notes on scheduling via `cron` or Task Scheduler.
4. **Add a new tool** — Guidance that new scripts should be placed in the repo root to have access to the weekly data.

**user**: thanks, that works.

Recorded: 2026-08-25 21:06:15.054006+00:00
Status: current
Source: distractors__d036.md
[/Evidence item]

# Project notes

You are working in this repository. Keep changes small and leave the tree clean.

# ledgerlite

Regional ledgers land as CSV files under `data/`. The monthly report combines them into
`report.csv`, which is committed and reviewed like any other change.
