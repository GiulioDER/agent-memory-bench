# Status of the benchmark, 2026-08-29

What has actually been measured, what has been built but not measured, and what is blocked.

`README.md` states the design and the standing limits on every published number. This file
states the state, and it is dated on purpose: a claim about behaviour or about a number rots
without any signal that it has rotted, so each section below ends with the command that
re-derives it.

## Phase

**Harness bring-up and internal pilots.** No multi-product run has happened. The leaderboard is
empty by construction: `site/data/leaderboard.config.json` carries `"official_run": null`, and a
number reaches the page only through `results/<run_id>/leaderboard_summary.json`, which no run
has yet produced. Four of the eight arms the leaderboard reserves a row for have a package
docstring and no adapter.

The first preregistered multi-product run is announced before it happens, not after it succeeds.

## Runs to date

| run | model | arms | cells | headline | artifacts committed |
|---|---|---|---|---|---|
| `pilot-001` | `deepseek-v4-flash` | bare, claude_md, recall | 71 admitted, 1 discarded | recall 0.394 against claude_md 0.380: no effect | yes |
| `pilot-002` | `deepseek-v4-flash` | claude_md, recall | 72 sessions per arm | recall 0.639 against claude_md 0.403 | yes |
| `pilot-002-repair` | `deepseek-v4-flash` | recall | re-roll only | superseded by `pilot-003-deepseek` | records only |
| `pilot-003-deepseek` | `deepseek-v4-flash` | bare, claude_md, recall | 72 admitted, 0 discarded | recall +22.2 points on claude_md, CI `[+11.1, +33.3]`, McNemar `p = 0.000145` | yes |
| `pilot-003-gpt53` | `gpt-5.3-codex` | bare, claude_md, recall | **40 admitted, 32 discarded** | incomplete, not a negative result | yes |
| `pilot-004-placebo` | `deepseek-v4-flash` | bare, placebo, claude_md, recall | 63 admitted, 9 discarded | recall +17.4 points, CI `[+4.9, +31.3]`; the pilot-003 bare-over-claude_md gap did **not** replicate | **no** |
| `midband-001` | `deepseek-v4-flash` | bare | 36 admitted, 0 discarded | six candidate tasks calibrated, one landed mid-band | **no** |
| `smoke-002`, `smoke-abstention-absent`, `smoke-sup2-superseded` | mixed | mixed | bring-up | wiring only, never a result | partial |

Four things this table carries that a reader should not have to reconstruct.

1. **`pilot-003-deepseek` is the one valid freeze result.** Every arm admitted, no discards, and
   the contrast is the preregistered one.
2. **`pilot-003-gpt53` is incomplete, not negative.** 32 of 72 cells were lost to provider credit
   exhaustion partway through the grid. It must never be pooled with the DeepSeek run, and its
   arm rates must never be quoted as a model comparison.
3. **`pilot-004-placebo` and `midband-001` are cited by committed documents whose artifacts are
   not in this repository.** `reports/pilot-004-placebo-report.md` and preregistration 008's
   results section both point at `results/<run_id>/` paths that `git ls-files` does not return.
   This is open work: either those run directories are committed, or the documents citing them
   say plainly that they cannot be checked.
4. **The two published dollar figures were priced on different bases.** `pilot-003-deepseek` used
   the frozen preregistration 002 rates, `pilot-004-placebo` used `scripts/pilot.py`'s argparse
   defaults, and neither artifact recorded which. Compare runs on tokens. The arithmetic is in
   [`docs/audit/2026-08-29-protocol-change-record.md`](audit/2026-08-29-protocol-change-record.md).

```bash
git ls-files results | cut -d/ -f2 | sort -u
```

## The task suite

**30 executable `ts-*` tasks.** The frozen pilot grid used 24 of them. Six were added by
preregistration 008 and calibrated on 2026-08-27 against the `bare` arm at six seeds each:
`ts-bool-env`, `ts-cli-exitcode`, `ts-csv-quote`, `ts-idempotent-run`, `ts-json-sorted`,
`ts-natural-order`.

That calibration was designed to produce mid-band tasks and mostly did not. One of six landed
mid-band against a prediction of three, and the record scores the miss rather than absorbing it.
Agent convention-following turned out to be close to deterministic per convention, and what
separates a convention the model gets right from one it gets wrong is whether the convention is
visible in the output of a **single run**. Cross-invocation properties are the blind spot. That
generalisation was not derivable from the tasks the design rule came from, which is why the rule
failed.

```bash
ls tasks | grep -c '^ts-'
```

## The harm suite

The 24 original tasks all place their governing fact **in** the corpus, so the suite could only
ever ask whether memory helps. Preregistration 005 adds the other half: four corpus conditions,
each a property of what the planted corpus contains rather than of what any product does about
it.

| condition | corpus holds | correct behaviour | damage signature |
|---|---|---|---|
| `absent` | no governing fact | solve from the repository, or say it is unknown | invents a convention |
| `superseded` | the old fact and the new one, both dated | apply the current one | ships the stale convention |
| `contradictory` | two undated memos that disagree, neither marked | surface the conflict | chooses silently |
| `adjacent` | a confident memo governing a different subsystem | recognise it does not apply | applies the other subsystem's rule |

**Built as of 2026-08-29: 12 tasks carry plants, and 11 of them carry all four conditions.**
`ts-base36-id` carries `absent` and `superseded` only, because its `adjacent` plant is recorded
as not implementable: the damaged outcome would be byte-identical to the factless one, so the
damage would be real and unattributable. `ts-dedup-order` carries three conditions.

Eleven clears preregistration 005's threshold of eight for reporting a condition as a result
rather than as underpowered. What building them cost, and the five rules each of which cost
something, is in
[`docs/PLANTING_ADJACENT_AND_CONTRADICTORY.md`](PLANTING_ADJACENT_AND_CONTRADICTORY.md).

**No abstention run has happened.** `results/` holds two smoke runs against the conditions and
nothing else. Preregistration 010 records, before any number exists, that `abstention-001` as
scoped covers two of the four conditions, and states what that costs each endpoint.

```bash
python -m scripts.audit_plants
```

## Arms

**Runnable today, six:** `bare`, `placebo` (length-matched neutral prose), `claude_md`
(designated baseline), `protocol` (the shared memory instruction with no memory layer),
`fs_grep` (transcripts on disk plus grep), and `recall`. The registry is `ARMS` in
`scripts/pilot.py`.

`protocol` is the arm that separates the coaching from the retrieval, and it exists because the
recall arm's treatment was not only the memory layer. Until 2026-08-28 the recall arm carried
5,428 characters of behavioural instruction and `fs_grep` carried 231, most of the difference
being generic agent hygiene that would have helped any arm. Under
`--memory-instruction protocol` every memory arm now gets `adapters/_shared/memory_protocol.md`
byte-identical, plus its own result-schema appendix capped at 1,200 bytes. Per-arm instruction
sizes are published in every run's `environment.json`.

**Not built, four:** the third-party memory products. They are not named yet, here or on the
site. Every vendor is invited to review its own adapter and frozen config before any measured
run, no invitation has gone out, and naming a product first would enter it into a benchmark
nobody has told it about.

Two diagnostic reference tracks, `oracle_memory` and `recall_prefetch`, have adapters and tests
and have never produced a live measurement.

```bash
grep -n '^ARMS' scripts/pilot.py
```

## What changed in the last week

**2026-08-28, the instruction stopped being a confound.** Until then the recall arm carried 5,428
characters of behavioural instruction while `fs_grep` carried 231 and the static arms carried
none, and most of that difference was generic agent coaching that would have helped any arm. So
the treatment was not the memory layer, and no pilot in the table above measured what its
headline says it measured. Every memory arm now receives `adapters/_shared/memory_protocol.md`
byte-identical plus its own result-schema appendix capped at 1,200 bytes; the `protocol` arm
isolates the coaching from the retrieval; and per-arm instruction sizes are published in every
run's `environment.json`. This is the single strongest reason not to read the pilots as a product
ranking.

The same week closed several smaller holes: the mechanism metric no longer matches on a source
filename, the adapters are on the measured path, sandboxes are built outside the repository, the
retry no longer re-rolls timeouts, harm is reported as a band rather than a point, and the
sandbox digest is actually compared rather than merely documented.

**2026-08-29, three protocol-sensitive fixes.** Held back from that week's fix PR because each
moves a number a frozen preregistration rests on, then landed together with the break stated:
[`docs/audit/2026-08-29-protocol-change-record.md`](audit/2026-08-29-protocol-change-record.md).

- `ts-retry-cap` rejected correct solutions about 40% of the time. The grader asked one unseeded
  draw to clear a threshold that a canonical full-jitter backoff clears only by chance, so the
  same submission passed or failed between runs. It is now pooled over 16 runs: discriminating
  power unchanged, residual spurious-failure probability about 5e-6.
- A checker crash discarded the whole paired cell, taking every other arm's paid session with it,
  on a trigger the agent controls. A checker that raises now grades as a **failure**. A genuine
  harness fault still raises, because that is a defect in the instrument rather than an outcome.
- Cost estimates charged cache reads at the fresh-input rate, and the recall arm's input is
  roughly two-thirds cache reads against under half for every baseline, so a single rate
  overstated spend unevenly between the arms being compared.

⚠️ **Consequence: a rerun is no longer protocol-identical to the frozen runs.** It uses a grader
that rejects fewer correct solutions and an admission rule that discards fewer cells. Rerun both
arms of any model comparison, or state in the report that the contrast is measured on a revised
instrument.

**2026-08-29, run prices are required.** Three runners carried three different price defaults and
none matched the frozen rates, so any run launched without the flags was priced on a basis nobody
chose, and a diagnostic was priced 44% above a pilot for the same model. `--price-in`,
`--price-out` and `--price-as-of` are now mandatory for a live run, registered from one place,
and a test asserts that no price default is left anywhere in `scripts/`. Dry runs need none.

## What blocks a competitor comparison

Ordered by what has to happen first, not by size.

1. **Four adapters do not exist.** `adapters/<name>/` holds a docstring and no `adapter.py`.
2. **No vendor review invitation has gone out**, and no `VENDOR_REVIEW.md` exists for any adapter,
   including `recall`.
3. **A third party cannot reproduce the `recall` arm.** `config.frozen.json` carries
   `"package_pin": "TBD"`, the published runs resolved the package from a local checkout through
   `PYTHONPATH`, there is no `versions.lock`, and `docker/compose.yaml` brings up a database and
   the harness image but installs no memory server.
4. **MCP startup failed 11.1% of sessions on `pilot-004-placebo`.** A cell is admitted only when
   every arm is wired, so at that rate an eight-arm grid carrying five memory servers would admit
   roughly 55% of cells against an admission rule of 95%. `harness/memory_startup.py` adds a
   preflight probe and a bounded retry whose predicate never reads `success`, the checker verdict,
   or anything the model did; the rate has not been re-measured on a full grid since.
5. **No arm has been run at a matched budget.** On `pilot-004-placebo` the recall arm used 4.5x
   the input tokens and 2.6x the wall time of every other arm. `costs.json` now carries
   success-per-million-tokens per arm, which reports the asymmetry without removing it.
6. **One model, and it is a cheap one.** The only stronger candidate ran out of provider credit at
   40 of 72 cells and has not been rerun, and after the protocol change a rerun needs both arms.
7. **Only the read path is measured.** The corpus is bulk ingested once and never written to
   again, so the extraction and consolidation half of every product under test is unmeasured.
   Preregistration 006 is the design that would measure it, and it has not run.

## Verifying this file

```bash
python -m pytest tests/ -q
```

```bash
python -m scripts.audit_corpus && python -m scripts.audit_plants
```

```bash
python scripts/build_leaderboard.py --check
```
