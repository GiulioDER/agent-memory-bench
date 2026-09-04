# Session notes: p01

**user**: Regenerating the May report churned the review diff: three lines changed with the input files untouched (see review/report_diff_note.txt; both report runs are preserved under reports/, the inputs under data/). Explain exactly why the row order can move between two runs over identical inputs, and recommend the ordering rule the monthly report should standardise on so a regeneration with unchanged inputs is byte-identical.

**assistant [Read]**: 
> 1	Review note, 2026-06-09 (May report regeneration)
2	
3	The May report was regenerated while chasing the amount-column fix that never
4	landed. The inputs under data/ are byte-identical between the two runs, yet
5	review shows three changed lines: the three 2026-05-04 rows come out in a
6	different order from run to run, so downstream reconciliation flagged all
7	three rows as changed against the committed report. Both runs are preserved:
8	reports/report_20260601_a.csv (runner) and reports/report_20260601_b.csv
9	(regenerated locally).
10	

**assistant [Bash]**: 
> total 2
drwxr-xr-x 1 gde00 197609   0 Aug 23 21:21 .
drwxr-xr-x 1 gde00 197609   0 Aug 23 21:21 ..
-rw-r--r-- 1 gde00 197609 145 Aug 23 21:21 report_20260601_a.csv
-rw-r--r-- 1 gde00 197609 145 Aug 23 21:21 report_20260601_b.csv

**assistant [Bash]**: 
> total 3
drwxr-xr-x 1 gde00 197609  0 Aug 23 21:21 .
drwxr-xr-x 1 gde00 197609  0 Aug 23 21:21 ..
-rw-r--r-- 1 gde00 197609 58 Aug 23 21:21 east.csv
-rw-r--r-- 1 gde00 197609 58 Aug 23 21:21 north.csv
-rw-r--r-- 1 gde00 197609 59 Aug 23 21:21 west.csv

**assistant [Read]**: 
> 1	date,id,amount
2	2026-05-04,ORD-052,18
3	2026-05-04,ORD-057,7
4	2026-05-04,ORD-049,32
5	2026-05-11,ORD-061,5
6	2026-05-19,ORD-070,11
7	2026-05-27,ORD-081,64
8	

**assistant [Read]**: 
> 1	date,id,amount
2	2026-05-04,ORD-049,32
3	2026-05-04,ORD-052,18
4	2026-05-04,ORD-057,7
5	2026-05-11,ORD-061,5
6	2026-05-19,ORD-070,11
7	2026-05-27,ORD-081,64
8	

**assistant [Read]**: 
> 1	date,id,amount
2	2026-05-04,ORD-052,18
3	2026-05-11,ORD-061,5
4	

**assistant [Read]**: 
> 1	date,id,amount
2	2026-05-04,ORD-049,32
3	2026-05-19,ORD-070,11
4	

**assistant [Read]**: 
> 1	date,id,amount
2	2026-05-04,ORD-057,7
3	2026-05-27,ORD-081,64
4	

**assistant [Bash]**: 
> ce99c3a fixture

**assistant [Bash]**: 
> commit ce99c3a327147c88093fe4bdc2670cb916140e91
Author: agent-ab <agent-ab@localhost>
Date:   Sun Aug 23 21:26:09 2026 +0200

    fixture

 README.md     | 4 ++++
 data/east.csv | 3 +++
 data/west.csv | 3 +++
 3 files changed, 10 insertions(+)

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

Everything else is identical, and the two report files are exactly the same size (145 bytes each). The next date in the report, `2026-05-11`, is a single row, so the shuffle is only visible where multiple rows collide on the same date.

## Why the row order can move over identical inputs

The report is not built from one file — it is a *merge* of three regional ledgers (`data/east.csv`, `data/west.csv`, `data/north.csv`). The three colliding rows each originate from a *different* input file:

| 2026-05-04 id | source file |
|---|---|
| `ORD-052` | `east.csv` |
| `ORD-049` | `west.csv` |
| `ORD-057` | `north.csv` |

The generator concatenates the three files, then sorts — but it appears to sort **only by `date`** (all the `2026-05-04` rows live in one group, then `2026-05-11`, `2026-05-19`, `2026-05-27`). A sort on `date` alone leaves the relative order of rows that share `2026-05-04` **undefined**. Their final order is inherited from whichever order the generator happened to read/iterate the three input files.

That file-iteration order (e.g. a directory listing via `os.listdir`/`glob`, the order files were passed on a command line, or iteration over a set/`HashSet` of filenames) is **not guaranteed to be stable** across runs, across filesystems, or across environments. It also isn't tied to the file contents in any way — the inputs are byte-identical, but the *iteration sequence* differs, so the merge emits the same-date rows in a different permutation. Hence byte-identical inputs produce three "changed" lines.

## Recommended ordering rule to standardise on

Sort the merged output by a **total, deterministic key** rather than by date alone. The natural choice for this report is a two-level sort:

> **`date ASC`, then `id ASC`**

So the canonical order for `2026-05-04` becomes `ORD-049` → `ORD-052` → `ORD-057` (identical to run B), with the tie under each date resolved by the unique order-id, which is completely independent of which file a row came from or how those files happened to be iterated.

Concretely, in the generator apply the sort key as `(date, id)` on the fully merged row set (rather than `(date,)`), or equivalently keep the date group and add a stable secondary sort on `id` within the group. Because `id` appears unique across these ledgers, this yields an unambiguous, reproducible ordering, and regeneration over unchanged inputs will be byte-identical every time.

Two supporting notes:

- **Don't rely on "read the files in sorted filename order and keep concat order."** That happens to produce a stable result *today* (`east.csv` sorts before `west.csv`), but it is fragile — it only hides the ambiguity and still depends on an external convention. An explicit `(date, id)` sort key fixes it at the point where the rows are merged, regardless of iteration order.
- A regression guard worth adding: after merge, assert (`df.sort_values(['date','id'])` reset to the same rows), or simply commit one of these reports and diff regenerations — this change eliminates the flaky churn the May regeneration exposed.

**user**: Right. Decision: report rows sort by (date, id), never by date alone. A sort keeps equal keys in input order, so a date-only key makes the report depend on which file's rows were read first; the id tiebreak gives one deterministic order for the same inputs and stops the diff churn downstream. All report tooling uses the (date, id) key from now on.
