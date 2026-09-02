# Status of the benchmark, 2026-09-02

What has actually been measured, what has been built but not measured, and what is blocked.

`README.md` states the design and the standing limits on every published number. This file
states the state, and it is dated on purpose: a claim about behaviour or about a number rots
without any signal that it has rotted, so each section below ends with the command that
re-derives it.

## Phase

**A multi-product run is on the board, and it reports a null.** `official-003` published on
2026-09-02: eight arms over one corpus, 2,920 sessions, 317 admitted cells, 26 tasks, five
conditions, on `deepseek-v4-flash`. `site/data/leaderboard.config.json` carries
`"official_run": "official-003"`, and a number still reaches the page only through
`results/<run_id>/leaderboard_summary.json`, generated and checked against its own regeneration by
CI. Four of the eight arms the leaderboard reserves a row for still have a package docstring and
no adapter.

⚠️ **Until 2026-09-02 this section said no multi-product run had happened and the leaderboard was
empty by construction. Both were true when written on 2026-08-29 and were contradicted by the
repository's own committed config for a day before anyone noticed.** That is the rot this file's
dating exists to make visible, and it is recorded here rather than quietly overwritten.

**Three things about that run a reader should not have to dig for.**

1. **It does not meet the announcement gates as the site states them.** Preregistration 026 was
   committed about two hours after the first session rather than before it, and the run was not
   announced in advance. 026 discloses that in its own first paragraph. It is weaker evidence than
   020 or 021 and must not be cited as though it had been written before launch.
2. **The headline is a null, and the placebo won.** Against a `claude_md` baseline of 0.577, the
   inert `placebo` arm scored 0.672, a memory layer 0.659, and `bare` also 0.659. No arm's 95%
   interval excludes zero, and the baseline came last.
3. **One seed per cell, and the write path is not measured.** Every arm was handed the same corpus
   before the grid and never wrote to its own store, so the board ranks retrieval, not memory
   formation. The leaderboard carries that qualification in its own `scope` block.

`mempalace`'s row publishes nothing until 2026-09-15, held for vendor review by
`VENDOR_REVIEW_HOLDS` in `scripts/build_leaderboard.py` rather than by anyone remembering to.

The next preregistered run is announced before it happens, not after it succeeds.

```bash
python -c "import json;print(json.load(open('site/data/leaderboard.config.json')))"
```

## Runs to date

| run | model | arms | cells | headline | artifacts committed |
|---|---|---|---|---|---|
| `pilot-001` | `deepseek-v4-flash` | bare, claude_md, recall | 71 admitted, 1 discarded | recall 0.394 against claude_md 0.380: no effect | yes |
| `pilot-002` | `deepseek-v4-flash` | claude_md, recall | 72 sessions per arm | recall 0.639 against claude_md 0.403 | yes |
| `pilot-002-repair` | `deepseek-v4-flash` | recall | re-roll only | superseded by `pilot-003-deepseek` | records only |
| `pilot-003-deepseek` | `deepseek-v4-flash` | bare, claude_md, recall | 72 admitted, 0 discarded | recall +22.2 points on claude_md, CI `[+11.1, +33.3]`, McNemar `p = 0.000145` | yes |
| `pilot-003-gpt53` | `gpt-5.3-codex` | bare, claude_md, recall | **40 admitted, 32 discarded** | incomplete, not a negative result | yes |
| `pilot-004-placebo` | `deepseek-v4-flash` | bare, placebo, claude_md, recall | 63 admitted, 9 discarded | recall +17.4 points, CI `[+4.9, +31.3]`; the pilot-003 bare-over-claude_md gap did **not** replicate | yes |
| `midband-001` | `deepseek-v4-flash` | bare | 36 admitted, 0 discarded | six candidate tasks calibrated, one landed mid-band | yes |
| `resolution-001` | `deepseek-v4-flash` | bare | 30 tasks x 12 seeds | the stratification preregistrations 007 and 009 rest on | yes |
| `abstention-001` | `deepseek-v4-flash` | bare, claude_md, recall | 32 and 30 admitted | harm suite, two of four conditions; **not written up, do not quote** | yes |
| `diagnostic-010` | `deepseek-v4-flash` | claude_md, recall, oracle_memory, recall_prefetch | 70 admitted | reference tracks; **not written up, do not quote** | yes |
| `official-003` | `deepseek-v4-flash` | all eight | 2,920 sessions, **317 admitted, 48 discarded** | on the leaderboard; a null, and `placebo` scored highest. Preregistration 026 committed mid run | yes |
| `smoke-002`, `smoke-abstention-absent`, `smoke-sup2-superseded` | mixed | mixed | bring-up | wiring only, never a result | partial |

Four things this table carries that a reader should not have to reconstruct.

1. **`pilot-003-deepseek` is the one valid freeze result.** Every arm admitted, no discards, and
   the contrast is the preregistered one.
2. **`pilot-003-gpt53` is incomplete, not negative.** 32 of 72 cells were lost to provider credit
   exhaustion partway through the grid. It must never be pooled with the DeepSeek run, and its
   arm rates must never be quoted as a model comparison.
3. **Committed is not the same as written up, and five of these rows are only the first.**
   As of 2026-08-29 every run a committed document cites is in the tree, so
   `reports/pilot-004-placebo-report.md` and preregistrations 007, 008 and 009 can now be
   checked against their artifacts. `abstention-001` and `diagnostic-010` cannot: their numbers
   exist in the tree and nowhere in any preregistration, so they are evidence awaiting an
   analysis rather than results. The full accounting, including what is still held back and
   why, is in [What is published, and what is still held
   back](#what-is-published-and-what-is-still-held-back) below.
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

**Three `xs-*` tasks, whose governing fact no single session states.** Added 2026-08-29. Every
`ts-*` task states one discrete fact in one document, which is retrieval's best case and leaves a
product that extracts and consolidates at write time no way to win: a suite where combining
sessions is never necessary cannot detect a product that combines them. `xs-join-batch` splits one
rule into two halves recorded under two names for one partner, `xs-evolve-lease` revises one value
across three dated sessions where only the last is correct, and `xs-widen-manifest` puts a rule in
one session and widens its scope in a later one.

Each ships a `partial_<shard>.py` reference per shard that CI asserts **fails**, which is what
makes "no single session suffices" a checked property rather than a design note.
⚠️ **The seven shard sessions were recorded on 2026-08-29 and they are pipeline-validation
recordings, not the run corpus**: they were made on the Windows workstation, whose paths and
usernames reach the transcripts. They ARE now in the feed: `corpus/manifest.json` was rebuilt the
same day, which also fixed six `ts-*` tasks whose sessions had never been listed and added 57
distractors to hold the 4:1 ratio. That change breaks comparability with the published runs and is
recorded in
[`docs/audit/2026-08-29-corpus-feed-change-record.md`](audit/2026-08-29-corpus-feed-change-record.md). The corpus audit is clean across them, including the shard-locus assertions. These
tasks still measure nothing. The suite is preregistered as `synthesis-001`
(`preregistration/011-cross-session-synthesis.md`) with three tasks called a diagnostic rather
than a headline; its recording log is appended there. Design and limits:
`docs/CROSS_SESSION_SYNTHESIS.md`.

```bash
ls tasks | grep -c '^xs-' && ls corpus/sessions | grep -c '^xs-'
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

**`abstention-001` is published as an artifact, and it is still not a result.** Since 2026-08-29
`results/abstention-001-absent/` and `results/abstention-001-superseded/` are committed, with
their records and `abstention-001-endpoints.json` carrying all four preregistered endpoints for
`claude_md` and `recall` against the `bare` reference. The other half is missing: neither
preregistration 005 nor 010 carries an appended results section, so no number from that run has
been written up, defended or interpreted, and **none should be quoted**. Preregistration 010
records, before any number existed, that `abstention-001` as scoped covers two of the four
conditions, and states what that costs each endpoint.

```bash
python -m scripts.audit_plants
```

## Arms

**Runnable today, seven:** `bare`, `placebo` (length-matched neutral prose), `claude_md`
(designated baseline), `protocol` (the shared memory instruction with no memory layer),
`fs_grep` (transcripts on disk plus grep), `recall`, and, since 2026-08-29, the first
third-party product. The registry is `ARMS` in `scripts/pilot.py`.

`protocol` is the arm that separates the coaching from the retrieval, and it exists because the
recall arm's treatment was not only the memory layer. Until 2026-08-28 the recall arm carried
5,428 characters of behavioural instruction and `fs_grep` carried 231, most of the difference
being generic agent hygiene that would have helped any arm. Under
`--memory-instruction protocol` every memory arm now gets `adapters/_shared/memory_protocol.md`
byte-identical, plus its own result-schema appendix capped at 1,200 bytes. Per-arm instruction
sizes are published in every run's `environment.json`, and since 2026-08-29 in its `analysis.json`
too, beside the arm's success rate: a rate is not interpretable without the size of the instruction
that produced it.

⚠️ **`protocol` has never been run.** Until 2026-08-29 it could not even have been read:
`scripts/pilot.py` accepted the arm and `scripts/analyze_pilot.py` refused it, so a run of the
control could have been spent and then not analysed. The analyser now reports
`instruction_only_protocol_vs_claude_md` (what the coaching alone bought) and
`store_net_of_instruction_recall_vs_protocol` (what the store bought on top of it) whenever the
roster carries the arm. **How much of the published lift is coaching is still unmeasured**, and
measuring it needs a preregistration first.

```bash
python -m pytest tests/test_instruction_fairness.py -q
```

**Not built, three:** the remaining third-party memory products. They are not named yet, here
or on the site. Every vendor is invited to review its own adapter and frozen config before any
measured run, no invitation has gone out, and naming a product first would enter it into a
benchmark nobody has told it about.

**Built and never run, one:** `mempalace` landed on 2026-08-29, wired through MemPalace's own
published MCP server (`mempalace-mcp`) and its own published ingest CLI (`mempalace mine --mode
convos`), pinned to `mempalace==3.8.0`.

**Built and never run, one more:** `cachly` landed on 2026-09-02, wired through its published
stdio MCP server, pinned to `@cachly-dev/mcp-server@0.10.145`. Its corpus load remains behind a
vendor-supplied bulk loader, selected by `AMB_CACHLY_BULK_INGEST_COMMAND`, because the public
MCP write tools are one at a time while the benchmark feed contains thousands of transcripts.
The adapter refuses to run without that loader and a dedicated Brain instance.

The name appears here and nowhere on the site, and that is the rule rather than an inconsistency:
this repository is where a vendor reads what it is being asked to review, so
`adapters/mempalace/` and `adapters/cachly/`, with their `VENDOR_REVIEW.md` files, are public on
purpose. `site/` is what enters a
product into a benchmark it was never told about, and there the arm is `product_e` with every
number null until its maintainers have had the review window.

⚠️ **It has measured nothing.** What is verified is the wiring, end to end and on this host: the
pinned version installs, its embedder loads, its MCP server serves all 20 tools the frozen config
allows out of the 44 it ships, and the adapter's own ingest path filed 56 drawers from 8 real
corpus sessions in 30.7 s and then retrieved the signal session for `ts-append-only`. That is a
proof that the arm can run. It is not a number about the product.

One environment fact is load-bearing and cost a measurement to find: **the palace path must be
short.** MemPalace embeds through onnxruntime, whose DLL fails to load from a deep path on Windows
with "The filename or extension is too long", and chromadb catches that and re-raises it as "The
onnxruntime python package is not installed" when it is installed. Under the harness's own staging
root the arm would have scored zero with nothing in the record naming why. The adapter refuses a
path over 120 characters instead, and the preflight checks it before a run starts.

```bash
MEMPALACE_VENV=C:/mpb/v MEMPALACE_PALACE_ROOT=C:/mpb/palaces python scripts/mempalace_preflight.py --ingest-smoke
```

Two diagnostic reference tracks, `oracle_memory` and `recall_prefetch`, have adapters and tests.
`results/diagnostic-010/` is published as an artifact, with its own analysis, and like the
abstention run it is **not a result**: nothing is appended under preregistration 003.

⚠️ **Do not difference `diagnostic-010` against the earlier diagnostics.** Diagnostics 003 through
009 gave the recall arm the 615-byte one-liner rather than the 5,817-byte skill the pilots froze,
so they measure a different treatment. The consequence was recorded when it was found: a 16%
search rate against `pilot-004-placebo`'s 85.7%. `diagnostic-010` is the only diagnostic
comparable to the published pilots, which is why it is the only one committed so far.

```bash
grep -n '^ARMS' scripts/pilot.py
```

## What is published, and what is still held back

⚠️ **Corrected twice on 2026-08-29, and the second correction is the useful one.** This page first
said that no abstention run and no diagnostic run had happened. That was a claim about the world
inferred from a `results/` tree that only ever showed what had been committed. The runs existed.
Six complete ones are now committed, so the honest statement has moved again, from "this
repository cannot show you any of them" to the list below.

⚠️ **Corrected again on 2026-09-02, and this one was worse, because the run it concerned was on
the public leaderboard.** `official-003` was published to the board on 2026-09-02 with its
`leaderboard_summary.json` and nothing else: no records, no streams, no admission verdicts, no
cost ledger. Rule 8 on the Submit page promises all four, `verify_run --all` reported the flagship
run as a failure on a clean clone, and that is the first check a sceptic runs. The evidence had
existed on the run host the whole time and had simply never been committed. It is committed now,
2,940 files, and all five conditions verify from their own sessions.

## What `verify_run --all` reports, and why

Measured 2026-09-02: **11 of 19 runs verify**. All eight failures have the same cause, and it is
neither a doctored number nor a missing run.

⛔ **Their per-session `streams/` were never captured.** Records can be checked against each other
but not against the sessions that produced them. The streams are not in this checkout, not in the
main checkout and not on the run host, so there is nothing to publish and the honest move is to
annotate rather than repair. Each failure prints a `note` naming its reason, the entries live in
`KNOWN_MISSING_STREAMS` in `scripts/verify_run.py`, and **they are annotated, not silenced**: every
one still reports FAIL and still counts against the total.

| run | why |
|---|---|
| `abstention-001-absent`, `abstention-001-superseded` | streams never captured |
| `midband-001`, `resolution-001` | streams never captured |
| `smoke-abstention-absent`, `smoke-sup2-superseded` | bring-up smoke runs, streams never captured |
| `smoke-002` | bring-up smoke run, 4 sessions without a stream |
| `pilot-001` | the earliest pilot, 72 of 287 sessions have a stream |

A test asserts every entry still describes a failing run, so a note cannot outlive the thing it
explains: publish a run's streams and the suite demands the note be deleted.

🔁 **Corrected 2026-09-02: `abstention-001` was NOT published without records.** This file, the
README and the verifier itself all said it had been published with an admission file, a cost
ledger and no records at all. Its 99 records per condition were there all along, as the sibling
files `results/abstention-001-<condition>-records.jsonl` rather than inside the run directory, and
`_load_records` only looked inside. The run now recomputes cleanly on session count, token total,
discard set, admitted cells and all four endpoints. **The evidence was never missing, only
unfindable**, and a checker that cannot find evidence prints the same string as one that finds
none. The wrong claim spread because the tool's output was quoted into the documentation and never
re-derived.

`results/retrieval/` is no longer treated as a run either. It holds `retrieval_probe.py` artifacts
and no agent session ever ran under it, so reporting it as a run with missing evidence was a false
alarm on a directory that will never have any.

```bash
python -m scripts.verify_run --all
```

**Two defects that came out of publishing official-003**, both recorded rather than worked around:

1. ⛔ **The harness writes an absolute host path into every published artifact.** It records the
   invoking command, and that command names the CLI binary and the per-task prompt file by
   absolute path. `official-003` carried 21,449 such occurrences across records and streams, and
   they were redacted to the literal `$HOME` before publication; the redaction is stated in the
   commit and the five conditions verify identically after it. **This is a harness fix, not a
   publishing step**, and until it lands every future run needs the same redaction by hand. The
   ratchet in `tests/test_no_host_inventory.py` is what forces the question.
2. **That guard could not see inside gzipped streams**, which is the form every run publishes its
   sessions in, so it had a blind spot on 279 files of `official-003` alone. Closed 2026-09-02,
   with a positive control, and it made 304 pre-existing `diagnostic-010` stream files visible.

**Published as artifacts**, 620 files and 26 MB, added 2026-08-29, plus `official-003` on
2026-09-02:

| run | what is there |
|---|---|
| `abstention-001-absent`, `abstention-001-superseded` | admission, costs and 99 records each; 32 and 30 admitted cells against 1 and 3 discards, plus `abstention-001-endpoints.json` |
| `midband-001` | the six-task calibration preregistration 008 reports |
| `resolution-001` | the 30-task, 12-seed re-measurement preregistrations 007 and 009 rest on |
| `pilot-004-placebo` | the placebo ablation its report in `reports/` has always cited |
| `diagnostic-010` | the oracle and prefetch diagnostic, with its analysis |

**Still held back**, each for a stated reason rather than by omission:

| run | why |
|---|---|
| `diagnostic-002`, `-003`, `-005` | carry their own `RESUME.md` or `INCOMPLETE.md` |
| `diagnostic-004` | aborted, no records at all |
| `diagnostic-006`, `diagnostic-009` | complete, but they gave the recall arm the one-liner rather than the frozen skill, so they measure a different treatment and would be misread as a null for memory |
| `abstention-002-*` | one run beside two `VOID` and two `PARTIAL` directories, documented in a note kept with them |
| the `*-invalid-*` directories | launches abandoned for a stated reason, kept as evidence |

Publishing those is a second step, not a decision against them: a void run kept with its reason is
worth more than a gap, and `diagnostic-009` in particular should go in only with its instruction
difference stated beside it.

**Committed is half of what makes a result.** The other half is an outcome appended below the
preregistration's results marker, which is where a run stops being a file. Neither preregistration
003, 005 nor 010 carries an appended section today, so **no number from any newly published run
appears on this page or on the site, and none should be quoted from them.**

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
3. **A third party cannot reproduce the `recall` arm**, though less of the reason is the
   repository's fault than it was. `package_pin` is now
   `recall-rag[fastembed,mcp,voyage]==0.11.0` from PyPI rather than `TBD`, and as of 2026-08-30
   the frozen config names environment variables instead of one machine's paths, so it no longer
   has to be edited (`adapters/recall/location.example.env`). What remains: the published runs
   resolved the package from a local checkout through `PYTHONPATH`, there is no `versions.lock`,
   and `docker/compose.yaml` brings up a database and the harness image but installs no memory
   server. A reader must still supply Postgres, a Voyage key and a calibrated generation.
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
   Preregistration 006 is the design that would measure it, and it has not run. Until it does, no
   multi-product ranking is published; a ranking that ships first is titled for the retrieval it
   measured, and `scripts/build_leaderboard.py` writes that title onto the page rather than
   leaving it to whoever writes the copy.

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
