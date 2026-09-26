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

## The corpus was not the haystack (added 2026-09-26, the same day)

**This was missing from the first version of this page, and it matters more than any deviation
above.** Graphiti was offered only the condition's own sessions, without the shared ~4,900 document
haystack every other arm searched:

| condition | sessions offered to Graphiti | offered to mempalace and cognee |
|---|---:|---:|
| present | 132 | 4,900 |
| absent | 120 | 4,888 |
| superseded | 143 | 4,911 |
| contradictory | 142 | 4,911 |
| adjacent | 132 | 4,900 |

Read from `ingest[*].sessions_offered` in each `environment.json`. Preregistration 084 does not state
a corpus size, so this is not a deviation from its text, but it is a different retrieval problem:
with no distractors, finding the governing session is far easier. The joined comparison against
official-003 is therefore not like for like, and the Graphiti row must not be read as a ranking
against arms that searched the full haystack.

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
