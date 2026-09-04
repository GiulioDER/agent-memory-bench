# Audit and fix record, 2026-08-30

A CCA DEEP-tier audit of the retrieval-corpus and per-arm-endpoint work, followed by the fixes.
This file exists so that the numbers this change invalidates are named in the tree rather than
remembered, and so that a later reader can tell which published artifacts were measured on the
instrument before it and which after.

**Scope audited.** The uncommitted diff on `claude/large-corpus-retrieval-test-0a0f98`: the
haystack generator and its vocabularies, the retrieval probe, the per-arm ranked-list endpoint
(`MemoryAdapter.search`) and its two implementations, the `present` corpus condition, the
task-admission tool, and the tests around all of it.

**Tier.** DEEP, forced by the numeric and high-stakes content detection: the diff computes
published rates and gates paid API spend.

## What was found

| | Raw | After dedup | Verified |
|---|---:|---:|---:|
| findings | 101 | 59 | 12 P1, 32 P2, 15 P3 |

Verification was `fp-check` over every P1 and P2, adversarial 2-of-3 on the high-stakes P1s, and
a `numeric` artifact requirement on the NUM-prefixed P1s. **Three P2s were rejected as false
positives** (F-14, F-20, F-52) and **one was escalated as UNCERTAIN rather than confirmed**
(F-47): its claim text was missing from the consolidated file, so the verifier could not show
that what it checked was the finding. F-52 named a real and pre-existing hazard that this diff
does not make reachable, and it should get its own ticket rather than a fix here.

## The two defects that would have published a wrong number about a vendor

Everything else on this list is smaller than these two.

**F-01, `harness/abstention.py`.** `missed_rate` divided an arm-filtered numerator by an
all-arms denominator, so the published rate was the true rate divided by the number of arms in
the grid. Adding an unrelated vendor to a run silently changed every other vendor's number.
Found independently by four auditors.

**F-07 with F-06, `adapters/recall/adapter.py`.** The parser required a single line that both
began with `{` and ended with `}`; recall's `_print_evidence` emits `json.dumps(payload,
indent=2)`. Nothing matched, every query returned an empty result, and the arm would have
published `hit@1 0.000` as a fact about the product. F-06 is the same outcome by a second route:
recall indexes the rendered `.md` names this harness writes, so a hit's `source_path` can never
equal a `.jsonl` manifest key. Both are now fixed, and the probe additionally REFUSES to publish
when an arm returns hits of which none join the corpus (F-05), because a structural zero and a
product that retrieves nothing are the same number and only one of them is a measurement.

## ⛔ Numbers this change invalidates

**`results/retrieval/arm-fs-grep-25x.json` and `arm-fs-grep-base.json` were measured on a
scorer that has since been corrected, and must not be differenced against a number measured
after 2026-08-30.** Two fixes moved the fs_grep arm's scores:

- **F-18.** `sum(text.count(term) for term in terms)` counted SUBSTRINGS, so one span scored
  once per query term that is a substring of it: terms `{sort, sorting}` over the text
  `"sorting sorting"` scored **4** for two occurrences. Documents were rewarded for the query's
  morphology rather than for their own content. Now counts whole-word occurrences.
- **F-19.** The token pattern `[a-z0-9_.]+` keeps `.` so that dotted identifiers survive, and it
  therefore also swallowed the sentence-final period: a prompt ending "...must stay relative."
  produced the term `relative.`, which matches nothing. **Every sentence-final content word was
  silently dropped from every query.** Edge punctuation is now stripped.

Both artifacts also publish `"windows": 0` (F-08b) against a comment that promised a corpus
window count. The value 0 is the correct one for an arm, which ranks documents and never
windows; the comment was withdrawn rather than the number changed.

`docs/RETRIEVAL_DIFFICULTY.md` carried four stale counts (F-41), now re-measured and dated, with
the reason they moved recorded beside them.

## Everything fixed, by file

| Finding | File | What was wrong |
|---|---|---|
| F-01 | `harness/abstention.py` | `missed_rate` denominator counted every arm |
| F-02 | `harness/abstention.py` | `never_run` was the literal `True` |
| F-03 | `harness/abstention.py` | `underpowered` counted cells, not clustered tasks, and gated sensitivity only |
| F-04 | `scripts/retrieval_probe.py` | spend estimator counted WORDS and claimed it erred high; it erred low |
| F-04b | `scripts/retrieval_probe.py` | the corrected heuristic is still not a bound, so the vendor tokenizer gates the spend too |
| F-05 | `scripts/retrieval_probe.py` | an arm's hits were never checked against the manifest |
| F-06 | `adapters/recall/adapter.py` | rendered `.md` names cannot join `.jsonl` manifest keys |
| F-07 | `adapters/recall/adapter.py` | a parse failure returned an empty result, like a zero-hit answer |
| F-08 | `adapters/recall/adapter.py` | chunk hits were scored as document ranks |
| F-08b | `scripts/retrieval_probe.py` | comment promised a window count the code does not publish |
| F-09 | `scripts/retrieval_probe.py` | miss rows padded the "what beats gold" histogram (83% of one artifact) |
| F-10 | `scripts/retrieval_probe.py` | the `10**9` miss sentinel was published as `median_rank` |
| F-11 | `scripts/retrieval_probe.py` | total retrieval failure printed `mean above 0.00` |
| F-13 | `scripts/assemble_condition_corpus.py` | the `rmtree` guard sat in `main()`, not at the delete |
| F-15 | `harness/adapters/base.py` and **six** adapters/scripts | a namespace reached an `rmtree`d path unvalidated |
| F-16 | `tests/test_haystack_and_retrieval.py` | the test wrote to a tracked source file |
| F-17 | `adapters/fs_grep/adapter.py` | the `__` decode was unvalidated and is not injective |
| F-18, F-19 | `adapters/fs_grep/adapter.py` | substring counting; sentence-final terms dropped |
| F-21, F-22, F-23 | `verify_run.py`, `prepare_recall_corpora.py`, `launch_official.sh` | three copies of a four-condition literal that `present` fell through |
| F-25 | `scripts/generate_haystack.py` | `--check` never read a corpus byte |
| F-26 | `scripts/generate_haystack.py` | the digest omitted the task data that decides what a session says |
| F-27 | `scripts/generate_haystack.py` | only the SUM of the shares was validated |
| F-28 | `scripts/task_admission.py` | the best-arm RATE had no session floor while the baseline did |
| F-29 | `scripts/retrieval_probe.py` | `plants_present` counted plants that ranked, not plants that exist |
| F-31 | `scripts/retrieval_probe.py` | the paid `--out` write sat downstream of a crashing print block |
| F-32 | `tests/` | one test cost 41.6s to check word arithmetic |
| F-33 | `scripts/retrieval_probe.py` | every embedding boxed as Python floats before the numpy copy |
| F-34 | `adapters/fs_grep/adapter.py` | the whole store re-read from disk on every `search()` |
| F-38 | `.dockerignore` | `corpus/haystack/` went into the image layers |
| F-39 | `scripts/task_admission.py` | `RESULTS.iterdir()` crashed where `.dockerignore` removed `results/` |
| F-41 | `docs/RETRIEVAL_DIFFICULTY.md` | four counts disagreed with the command printed above them |
| F-42 | `scripts/generate_haystack.py` | `--help` crashed on a cp1252 console |
| F-43 | `tests/test_corpus_manifest_is_complete.py` | the glob tuple was copied from `base.py`, and this diff was the drift event |
| F-48 | `scripts/retrieval_probe.py` | a result's only provenance was a gitignored directory name |
| F-49 | `scripts/retrieval_probe.py` | `resolve_corpus_path` exists and was not applied at the join |
| F-50 | `scripts/retrieval_probe.py` | `--corpus` repeats, so N roots spent up to N times the ceiling |

### Files this change ADDS

Listed explicitly, because a commit that stages the modified files and forgets one of these
ships a record whose claims have no home in the tree. The architect gate caught exactly that:
`results/retrieval/README.md` existed, was load-bearing, and was in no list.

| File | Why it exists |
|---|---|
| `tests/test_audit_fixes_20260830.py` | one red to green regression test per confirmed finding |
| `tests/test_namespace_guard.py` | enforces the namespace property that a comment merely claimed |
| `results/retrieval/README.md` | the instrument break, beside the artifacts it invalidates |
| `docs/audit/2026-08-30-audit-fix-record.md` | this file |


## The anti-regression pass, and what it sent back

A differential review over all 56 hunks returned **53 SAFE, 3 SCOPE_CREEP, 0 REGRESSION_RISK**. It
did not take the fix record's word for the endpoint claim: it reconstructed the pre-fix probe from
`git show HEAD:` and ran both versions over `corpus/` and `corpus/conditions/absent/seed-1`,
diffing every key. **Every pre-existing key is byte-identical**, including `hit@1` 0.500, `hit@5`
0.765, `hit@10` 0.971, `mrr@10` 0.610, `median_rank` 2, `misses` 0 and `all_shards@10` 0.667. The
only differences are the new keys. That is the check that matters, because F-09 rewrote the
population of an aggregate sitting next to those numbers.

All three SCOPE_CREEP items were unmapped changes that had ridden along, and all three are
resolved:

- **A `--` argv separator** inserted into the `recall.cli` call. Defensible hardening, but on the
  exact call the recall arm's whole measurement depends on, with no test covering the argv at all
  (every recall test drives `parse_ranked_search` with a fake stdout). **Removed.**

  ⚠️ **It was not merely unmapped: it had already broken seven tests in
  `tests/test_ingest_verification.py`, and I had not noticed.** The review graded it SCOPE_CREEP
  rather than REGRESSION_RISK on the reasoning that the failure would be loud rather than silent.
  It was loud. It was also invisible to me, because I read the last six lines of a suite run and
  those lines named five of the seven failures without a count I looked at. The lesson is not
  about `--`: **a reviewer's "this would fail loudly" is only worth anything if somebody is
  reading the failure**, and a `tail -6` of a seven-minute run is not reading it.
- **The aggregate spend ceiling fired on the `--arm` path**, which constructs no `Voyage` and
  spends nothing, so `--arm fs_grep --backend voyage` paid a full `load_windows` pass and could
  refuse a run that could not have cost anything. **Now gated on `not args.arm`.**
- **A second, authoritative spend gate** (`client.count_tokens`) had no finding and no test. It
  **stays**, and is now named **F-04b** in the code and covered by four tests, because F-04's harm
  is "the ceiling under-estimates paid spend" and the corrected character heuristic still
  under-estimates 19 of 200 real windows. Its own docstring refuses to claim a guaranteed bound,
  and a ceiling that can be exceeded is not a ceiling. It is separable from F-04, so it is named
  separately rather than hidden inside it.

Six minors it raised were also fixed: `CORPUS_GLOBS` had been inserted between the `#:` block
documenting `GATINGS` and `GATINGS` itself, orphaning a load-bearing served-versus-raw warning; the
new guard in `launch_official.sh` was **unreachable**, because under `set -e` a failing command
substitution in an assignment aborts before the guard runs (it now assigns in two steps, so the
diagnostic actually prints and the exit code is the intended 2); the `--per-task` table had
silently lost the tier column for miss rows; the condition-corpus delete guard would have refused a
legitimate re-assemble over a stray `.DS_Store`; the `--out` confirmation had moved to stderr; and
two dead lines were left in a test.

## The architect gate, and the fix of mine it rejected

Verdict on the first submission: **REVISE**, 12 issues, 3 blocking. It re-ran the suite and the
lint itself rather than taking the record's word, and it verified every number in the
instrument-break declaration against the artifacts. All 12 are resolved. Three are worth writing
down, because each is a different way for a green change to be wrong.

### ⛔ My fix for F-28 was green, and it was wrong

F-28 said the best-arm rate had no session floor while the baseline did. I applied
`MIN_SESSIONS = 6` to the best arm. That turned an **existence** test into a **rate** test, and
`FLOOR` is defined by its own comment as "a task NO arm has ever solved". Under my change it
meant "no arm with at least six sessions has a rate above zero", which is a different and weaker
claim.

Three tasks moved from BENEFIT-ONLY to FLOOR, all because their only successes came from
`oracle_memory`, which carries 3 sessions:

| task | oracle_memory | every other arm |
|---|---|---|
| `ts-empty-input` | 1/3 | 0 of 47 |
| `ts-log-mask` | **3/3** | 0 of 56 |
| `ts-retry-cap` | 1/3 | 0 of 55 |

`ts-log-mask` is a perfect oracle rate against zero for every real arm: **the largest measured
memory headroom in the pooled runs**, filed by my change under the label this tool describes as
"separates nothing until one does". And the tool prints that sentence, and I had edited
`docs/RETRIEVAL_DIFFICULTY.md` to publish it. A green suite, a passing lint and a clean
anti-regression pass all held while the change made the benchmark lie about its own instrument.

The distinction the fix missed: **a thin arm is weak evidence about a RATE and perfectly good
evidence that a solution EXISTS.** `FLOOR` is now an existence test again, symmetric with
`any_failure` on the damage side, and both rates are published (`best_arm_rate` gated,
`best_arm_rate_all_arms` not) with the table showing `0.00|1.00` where they differ. Counts are
back to 21 of 34 with 2 on the floor.

### The namespace guard reached one site of four, and the comment said otherwise

F-15's `validate_namespace` carried the sentence "Shared rather than per-adapter so a new vendor
cannot arrive without it". Nothing enforced that, and at the time it was written the guard reached
**one** of the four places a namespace is joined onto a path the same code later `rmtree`s. The
three it missed were `RecallAdapter.ingest` (the identical line F-15 was demonstrated on, in a
different adapter), `MemPalaceAdapter.ingest` (a wired vendor arm) and
`scripts/prepare_recall_corpora.py` (which derives its path from the very `--namespace` flag the
finding named).

Fixed by putting the check AT the join (`namespace_path`) and by writing
`tests/test_namespace_guard.py`, which asserts the property instead of claiming it.

**Then the test found more sites, twice, and the second time it was because I tested the test.**
Its first structural scan matched `/ namespace` and `/ f"{namespace}"` only. Probed against ten
plausible join shapes, it missed **six**: `Path(root, ns)`, `root.joinpath(ns)`,
`os.path.join(root, ns)`, `root / self.namespace`, `staging / args.namespace`, and the f-string
form. **A scan that misses is worse than no scan, because it certifies.** Widening it found five
more.

The running tally is the useful part of this finding, more than any individual site:

| Sites reached | Found by |
|---:|---|
| 1 of 11 | the original F-15 fix |
| +1 | the audit (`fs_grep._staging_dir`, the demonstrated one) |
| +3 | the architect gate (`recall.ingest`, `mempalace`, `prepare_recall_corpora`) |
| +2 | the enforcement test, first version (`oracle_memory`, `recall_prefetch`) |
| +5 | the enforcement test, after its own coverage was tested (`_prompt_path` x3, `pilot.py`, an archive name) |

Two of those five were entry points a person types into: `--namespace` in `scripts/pilot.py`
becomes the fs_grep arm's store path, and a tenant becomes an archive filename. So the scan now
covers `scripts/` as well as `adapters/`, it requires the namespace to be an OPERAND of a join
rather than merely present on the line (which is what stops it flagging
`session_dir / "prompt.md"`), and it carries twelve of its own tests: nine shapes it must flag
and three it must not.

An unenforced claim in a security comment is worse than no comment, because it stops the next
reader looking. An enforcement test with an untested scan is the same failure one level up.

### A load-bearing file was in no list

`results/retrieval/README.md` carries the instrument-break declaration next to the two artifacts
it invalidates. It was untracked and named in no table, so a commit staging "the modified files
plus the two new ones" would have shipped this record asserting a warning that did not exist in
the tree. There is now a "Files this change ADDS" table above, and staging is explicit.

### The rest

- **F-51** was a CONFIRMED finding that appeared nowhere: not fixed, not deferred. Now deferred in
  writing, with the reason and the bound on its exposure.
- **F-03** was half fixed: cells became tasks on the sensitivity side while the specificity side
  kept none, so `underpowered: false` could rest on two specificity cells sitting in the same dict
  as two Youden endpoints computed from specificity. Both sides now gate it.
- **F-05** promised in its own docstring to report partial join failures and put the counts only
  in the JSON. The rate and a `[!!]` line are now printed where a human reads them, because an
  unjoinable hit still occupies a rank and biases the score DOWNWARD against the vendor.
- **F-09**, a high-stakes P1, had one test and it was a source grep asserting the implementation
  line verbatim. Replaced with a behavioural test driving `probe` over a fixture with one hit row
  and one miss row. Writing it exposed a related trap worth keeping: a fixture using the wrong
  JSON field reads back as an EMPTY corpus, and an empty corpus is indistinguishable from a very
  hard one in every number the probe reports.
- **F-50**'s default derives the aggregate ceiling as `--max-tokens x roots`, which preserves the
  pre-fix spend envelope rather than lowering it. That is deliberate, since a repeatable
  `--corpus` is the designed way to probe a difficulty curve, and it is now said in the help text
  instead of being left for a reader to infer.
- **F-24's deferral** now lives in a comment on the `BM25` class itself, not only in this file.

## ⚠️ Deferred, deliberately

**F-24 needs a decision, not a fix.** `scripts/retrieval_probe.py` carries a second BM25
implementation alongside `harness/retrieval.py`, and they differ in `k1`, the stoplist, the
tokenizer and query-term deduplication. Collapsing them changes numbers published under
preregistrations 015, 016 and 018. That is a call for the person who owns those records, and a
gate must never force an edit to a committed preregistration.

**F-47 is UNCERTAIN and was not fixed.** `condition.json` records `base_corpus` as a bare
relative label with no manifest hash, while the sibling artifact in the same diff records a
`generator_sha256`. The base corpus demonstrably moved (125 to 195 sessions) within this
project's history, so a `condition.json` cannot be tied to the base build it came from. That is
a real gap; it is not demonstrably the finding, so it is reported rather than silently patched.

**F-51 is CONFIRMED and NOT fixed.** `scripts/retrieval_probe.py` batches paid embeddings into an
in-memory list with no checkpoint, so a failure at batch N discards every embedding already paid
for and a rerun re-spends from zero. It is deferred rather than fixed because a checkpoint is a
new on-disk format with its own invalidation question (a resumed run must prove the corpus and the
model have not moved between attempts, or it silently mixes two embeddings spaces), and that is
more design than an audit fix should carry. **The exposure is bounded meanwhile**: `--max-tokens`
and `--max-tokens-total` cap what a single invocation can spend, and the 018 Voyage pass is
deliberately being held. It was missing from this record entirely until the architect gate caught
it, which is the failure mode a written deferral exists to prevent.

**15 P3 findings** were verified as low and are not addressed here.

## What was NOT verified

The `numeric` deterministic backend returned UNCERTAIN on the P1s it was asked to adjudicate,
despite the falsifying examples being present: its detection is line-anchored and pytest prefixes
assertion output. So the two NUM-prefixed P1s (F-01, F-04) rest on `fp-check` plus executed
red→green tests rather than on a deterministic artifact. Both have executable proof in
`tests/test_audit_fixes_20260830.py`; neither has a machine verdict.

## The red-state proof

A regression test written after a fix, which would also have passed before it, proves nothing. So
the two new test files were run against a pristine `git archive` of the pre-fix tree, in a scratch
directory, with the working tree untouched. Five symbols the fixes introduce (`manifest_key`,
`validate_namespace`, `namespace_path`, `ArmBackend.bind_corpus` / `assert_joinable`, and
`verdict`'s new keyword) were shimmed there with the behaviour the pre-fix code actually had, so
that a failure is a failure of pre-fix LOGIC and not of a missing name.

**Measured 2026-08-30, after the architect gate's second pass: 48 failed, 27 passed.**

| Measured 2026-08-30 | Value |
|---|---:|
| `pytest tests/ -q` on the fixed tree | 766 passed, 12 skipped |
| `tests/test_audit_fixes_20260830.py` | 40 tests |
| `tests/test_namespace_guard.py` | 35 tests |
| the two of them against the PRE-FIX tree | 48 failed, 27 passed |

The 27 that pass are accounted for individually, because an unexplained pass is the whole risk:

- **20 are the scan's own coverage tests.** `MUST_FLAG` and `MUST_NOT_FLAG` live in the test file
  and describe the regex beside them, so they pass in any tree. They are specification tests of
  the instrument, not regression tests of the product, and they exist because the scan shipped
  twice with holes in it.
- **3 are deliberate no-regression companions**, each paired with a test that does fail:
  `test_f15_an_ordinary_namespace_still_works`,
  `test_f05_an_arm_that_returned_nothing_is_not_a_join_failure`, and
  `test_f06_a_name_carrying_no_directory_information_is_left_visibly_unjoinable`.
- **1 is `test_the_primitive_joins_an_ordinary_namespace_under_its_root`**, the same shape.
- **3 are the F-28 tests that call `verdict()` directly, and their passing IS the finding.**
  `verdict()` was byte-identical before and after the rejected fix; the defect lived entirely in
  `main()`, where `best` was computed over session-gated arms and handed to an unchanged
  parameter. Every test written at `verdict()` is blind to it, however carefully.
  `test_f28_the_row_that_feeds_the_verdict_counts_every_arm` is the one that fails, and it is the
  only test in the file that catches the defect when it is reintroduced.

That last point was measured rather than reasoned. Reintroducing the exact bug as
`ever_solved = any(v for arm in eligible for v in arms[arm])` leaves **40 of 40 tests green** in
the version of this file that existed before the architect's second pass, while `ts-log-mask`
returns to FLOOR and the tool reprints the sentence this record spends a paragraph retracting.
With the row test present: **1 failed, 39 passed**, and it is the right one.

**Three tests were rewritten during this proof because they passed against pre-fix code and
therefore tested nothing**, and each failed a different way:

1. Two asserted an ABSENCE produced by a mechanism that did not yet exist ("no skip was recorded
   for the wrong reason" is vacuously true when no skip was ever recorded for any reason).
2. One asserted a function SIGNATURE, which restates the implementation and would pass against a
   parameter named right and used wrong.
3. One grepped the source for four key names, with the same weakness.

`scripts/generate_haystack.py --check` was proved separately by executing the pre-fix code
against a deliberately damaged corpus (one truncated file, one deleted file, one unplanned extra
file). Pre-fix it printed `OK` and exited 0. Post-fix it names all three and exits 1.

## ⚠️ One suite anomaly, reported because the mechanism outlives the event

The architect gate's first full run returned `7 failed, 739 passed`, all seven in
`tests/test_ingest_verification.py`, with `inspect.getsource(RecallAdapter.ingest)` returning a
single stray line. That is the signature of stale bytecode against fresh source: a code object
whose `co_firstlineno` no longer matches what `linecache` reads. It did not reproduce, in that
file alone, with the new test files, across the alphabetical prefix, or in a clean full run.

No cause is asserted. The transferable point is that seven of that file's checks assert on SOURCE
TEXT located by line number, which makes it structurally the first thing to break under any such
skew, and it fails in a way that reads exactly like a real defect. It is worth knowing before
somebody spends an afternoon on it. This is the second time in two days that a line-anchored
check has produced a misleading verdict here; the first was the `numeric` backend returning
UNCERTAIN while holding the falsifying example.

## Re-measure

```bash
python -m pytest tests/ -q && python -m ruff check .
```
