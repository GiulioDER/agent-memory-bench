# official-007-graphiti: provenance and deviations

Written 2026-09-26, when this run was published as an additive leaderboard arm joined to
`official-003`. Everything a reader needs to discount the result is on this page, because the run
did not execute the way preregistration 084 froze it.

## Which directories are the run

The run executed on the benchmark host as a sequence of per-condition attempts. For every
condition exactly one attempt admitted any cell; every other attempt admitted zero. So the
selection rule is mechanical, and it is stated here so nobody has to trust that it was:

> For each condition, publish the single attempt directory with a nonzero admitted cell count.

| published as | executed as | admitted | discarded | Graphiti solved |
|---|---|---:|---:|---:|
| `official-007-graphiti-present` | `official-007-graphiti-bare-recovered-present-final` | 129 | 1 | 50 |
| `official-007-graphiti-absent` | `official-007-graphiti-recovered-absent-only-final` | 60 | 0 | 43 |
| `official-007-graphiti-superseded` | `official-007-graphiti-recovered-superseded-only-final` | 54 | 1 | 33 |
| `official-007-graphiti-contradictory` | `official-007-graphiti-recovered-contradictory-only-final` | 50 | 0 | 36 |
| `official-007-graphiti-adjacent` | `official-007-graphiti-recovered-adjacent-only-final` | 55 | 0 | 36 |

Attempts left out, all with zero admitted cells (wiring failures, every session discarded):
`official-007-graphiti-bare-recovered-present`, `-present-v2`, `-present-v3`, `-present-v4`,
`official-007-graphiti-bare-recovered-absent-final`, `-absent-final-r2`, and `-absent-final-r3`,
which never wrote `records.final.jsonl`. They remain on the run host.

The directories were renamed to `<run_id>-<condition>` because `scripts/build_arm_submission.py`
reads that layout. Nothing inside them was changed, and all five pass `scripts/verify_run.py` on
session counts, token totals and discard sets. The `run_id` recorded inside each
`environment.json` is still the executed name. `cfg/` is excluded, as for every run.

## The preregistration predates the run

`preregistration/084-official-007-graphiti-bare-vps2.md` was committed as `61ba3ff3` at
2026-09-11 11:21 UTC and stamped by `prereg-timestamp-manifest-20260911T112100Z.json`, kept here
because it hashes the old branch's files, not master's. The committed file matches the manifest
byte for byte (sha256 `e720d024`, 3,596 bytes). The run was reported started at 12:34 UTC the same
day.

## Deviations from preregistration 084

1. **Only the Graphiti arm ran in four of the five conditions.** 084 freezes `bare` and
   `graphiti` per cell. `present` ran both; `absent`, `superseded`, `contradictory` and
   `adjacent` ran `graphiti` alone, on the operator's instruction of 2026-09-12. The leaderboard
   row compares against `official-003`'s arms through the additive join, like every other
   additive arm, so the missing `bare` cells do not enter the published delta. They do mean the
   run's own paired `bare` control exists for `present` only.
2. **Memory instruction.** 084's command line says `--memory-instruction skill`. All five
   `environment.json` files record `protocol`, which is what `official-003` used.
3. **Recovery reused ingested episodes.** After the first attempt crashed, each condition was
   resumed from the Graphiti episodes already ingested into that condition's namespace
   (`amb-graphiti-official-007-<condition>`) by the recovery scripts in `source/scripts/`, which
   084 does not describe. 084 says a partial condition receives a new run ID and is never mixed
   into a later attempt. The episodes came from the same corpus and the same run, but the rule was
   not followed.
4. **The code changed between conditions.** On 2026-09-13, after `present`, `absent` and
   `superseded` had completed, the recovery path was patched to tolerate a null
   `Document.description` returned by Graphiti's extraction and to retry a failed episode.
   `contradictory` and `adjacent` ran on the patched code.
5. **No trusted execution receipt.** 084 says results are not promoted unless the verifier and
   the trusted adjudication receipt both pass. `verify_run` passes; the receipt check reports
   `trusted execution receipt predates this artifact` and is skipped, not passed.
6. **Executed from an uncommitted working tree.** The host checkout was branch
   `codex/model-freeze-pilot` at `47150cf3` with 80 modified tracked files and untracked recovery
   scripts. That branch is not pushed, and cannot be, because it forks from master before the
   2026-08-29 history rewrite and would republish content removed since. What executed is
   preserved here instead (next section).

## Not the corpus the joined comparison assumes

Added 2026-09-26, after publication. This is not a deviation from 084, which never names a corpus
size, but it matters more to the published row than any deviation above. **Graphiti searched the
standard feed without the distractor haystack. Every product it is ranked against searched the
haystack.**

| condition | Graphiti sessions offered and stored | official-003 sessions offered |
|---|---:|---:|
| `present` | 132 | 4,900 |
| `absent` | 120 | 4,888 |
| `superseded` | 143 | 4,911 |
| `contradictory` | 142 | 4,911 |
| `adjacent` | 132 | 4,900 |

Offered equals stored in every condition, so this is the whole corpus Graphiti was given, not a
partial ingest. `recover_graphiti_condition.py` raises unless every session in the corpus is in
the store, and `run_recovered_conditions.py` sets `AMB_CORPUS_FLOOR` to the corpus size.

The corpus came from `corpus/conditions/<condition>/seed-1` as the host assembled it. The
assembler adds the haystack only when `AMB_HAYSTACK` is set (`haystack_root` in
`scripts/assemble_condition_corpus.py`), and no run records whether it was. The sizes settle
it:

- official-003's corpora are master's standard feed plus about 4,704 haystack sessions. The
  standard feed, assembled on master on 2026-09-26, holds 196, 185, 206, 206 and 196 sessions,
  and 4,900 minus 196 is 4,704.
- Graphiti's counts sit a constant 63 to 65 below master's standard feed in every condition.
  That is consistent with the host branch's older feed and with no haystack at all.

What it changes. Without the haystack, retrieval on this feed is close to saturated:
`docs/RETRIEVAL_DIFFICULTY.md` measures voyage hit@10 at 1.000 on the standard feed. So
Graphiti's search task was easier than the one every other product faced. Its result is not
comparable to theirs, and the difference, if anything, favours Graphiti. Its agent tokens per
task are also lower partly because there was less to retrieve from.

How it went unnoticed. The ingest notes attribute the store to "direct Graphiti core recovery",
which reads as a partial load. The first draft of the analysis page repeated that reading, and
so did the pull request that added it (#115), until this check.

Re-measure, from the repository root:

```bash
python -c "import json;[print(c,[i['sessions_offered'] for i in json.load(open(f'results/official-007-graphiti-{c}/environment.json'))['ingest'] if i['arm']=='graphiti'],[i['sessions_offered'] for i in json.load(open(f'results/official-003-{c}/environment.json'))['ingest']][:1]) for c in ('present','absent','superseded','contradictory','adjacent')]"
```

## Source

`source/` holds the working-tree copies of the files that define the arm and its execution:
the Graphiti adapter, `harness/graphiti_broker.py`, `harness/broker.py`, `harness/abstention.py`,
`scripts/abstention.py`, and the recovery scripts. They are evidence, not importable code; the
adapter needs a `harness/broker.py` that master does not have.

- `worktree-vs-47150cf3.diff` is `git diff HEAD` over `harness/`, `scripts/` and
  `adapters/graphiti/` on the host as found on 2026-09-26.
- `worktree-sha256.txt` hashes every modified or untracked file under `harness/`, `scripts/`,
  `adapters/` and `docker/` on the host at the same moment.
- Four files in `source/scripts/` had the host home prefix replaced by `$HOME` (5 occurrences),
  so their hashes no longer match the manifest. Nothing else was altered.

The snapshot is the tree as it stood after the last condition, so it shows the patched recovery
path of deviation 4, not the code `present`, `absent` and `superseded` ran.

## Review window

The review invitation went to the Graphiti maintainers on 2026-09-13 with a two week window,
closing 2026-09-27. No reply had arrived when this was published on 2026-09-26, one day early, on
the operator's decision. The pending row published on 2026-09-13 was dropped from master by
`2d9b7d97` (#93) on 2026-09-17, a squash from a branch that predated it; nobody noticed until
2026-09-26.
