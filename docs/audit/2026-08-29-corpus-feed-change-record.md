# Corpus feed change record, 2026-08-29

`corpus/manifest.json` grew from **125 entries to 195**. The manifest is the feed: every adapter
ingests exactly what it lists, so this changes the retrieval problem every arm faces, in every
future run, on every task. It is recorded here rather than absorbed, in the same form as
[the protocol change record](2026-08-29-protocol-change-record.md).

Nothing was removed and no pre-existing entry's hash changed. `CorpusManifest.verify()` passes.

## What moved

| Added | Count | Why |
|---|---:|---|
| `sessions/xs-*/…` | 7 | the cross-session synthesis suite's shard sessions, recorded in PR #15 and until now ingested by nobody |
| `sessions/ts-*/…` | 6 | `ts-bool-env`, `ts-cli-exitcode`, `ts-csv-quote`, `ts-idempotent-run`, `ts-json-sorted`, `ts-natural-order`: recorded, on disk, and **never listed** |
| `distractors/d100…d156` | 57 | to hold the corpus's stated distractor-to-signal ratio at 4:1 |

Signal sessions 26 to 39, distractors 99 to 156, ratio **3.81 to 4.00**. The ratio is why the
distractors were recorded first: adding thirteen signal documents to the old 99 distractors would
have driven the feed to 2.54:1, well under the target `corpus/README.md` states.

## The defect this fixes, which is worth naming on its own

Six tasks added by [preregistration 008](../../preregistration/008-midband-task-calibration.md)
had their precursor sessions recorded and **left out of the manifest**. Since no adapter ingests
anything the manifest does not list, those six tasks were scored in every run since as if their
corpus condition were `absent`: no memory arm could reach their governing fact by retrieval, at
all, by construction. Any per-task result for them measures the floor rather than the product,
and a pooled mean over 30 tasks carried six tasks where memory could not win.

Nothing reported this. The manifest is built by a script nobody has to run, `audit_corpus` reads
the files on disk rather than the manifest, and a task with an unreachable fact looks exactly like
a hard task. ⚠️ **The gap has existed since those tasks landed.** Any uncommitted run that included
them (`midband-001`, `resolution-001`, the eight `diagnostic-*` directories) is affected in the
same way, and their per-task numbers for those six should not be read as retrieval results.

## The break

**A run after this change is not comparable to `pilot-003-deepseek` or `pilot-004-placebo`**, and
the reason is not the six tasks (those postdate both runs and were never in the frozen 24-task
grid). It is that the corpus itself is 56% larger. Retrieval over 195 documents is a different
problem from retrieval over 125, the distractor-to-signal ratio moved, and both are exactly the
variables the feed is supposed to hold constant across arms and across runs.

So, for anything measured from here:

- Do not difference a new number against a published one. Rerun both arms, or state that the
  contrast is measured on a different feed.
- The frozen 24 tasks' own sessions and hashes are untouched. What changed for them is the haystack.
- `preregistration/011`'s synthesis suite has not run at all, so it is unaffected and will simply
  run on this feed.

## What is still not true

These sessions and distractors were recorded on the Windows workstation, so they carry its paths
and username and are **pipeline-validation recordings**, not run corpus, exactly as
`corpus/README.md` requires. Ingesting them makes the wiring real; it does not make the corpus
publishable. The corpus for a preregistered run is recorded inside the Docker harness.

## Re-derive

```bash
python -c "import json;d=json.load(open('corpus/manifest.json'))['sessions'];s=sum(k.startswith('sessions/') for k in d);print(len(d),'entries',s,'signal',len(d)-s,'distractors',round((len(d)-s)/s,2),'ratio')"
```

```bash
python -m scripts.audit_corpus
```
