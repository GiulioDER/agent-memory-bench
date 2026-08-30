# Feed change, 2026-08-30: 195 to 196 entries

`corpus/manifest.json` went from 195 entries to 196. The added entry is
`sessions/fa-dedup-key/p01.jsonl`, the governing session of the `fa-dedup-key` task added by
`a239647` (#34).

## What happened

The task, its fixture, its checker, its calibration record and its recorded precursor session
were all committed. The manifest was not rebuilt. `CorpusManifest.load` reads that file and every
adapter ingests exactly what it lists, so the session was on disk and **not in the feed**: no arm
could retrieve it, and a brand new task was unwinnable by memory from the moment it landed.

Nothing raised. `scripts/audit_corpus.py` iterates task directories and checks containment;
`tests/test_grid_prefixes.py` checks a task CLASS is accounted for; neither compares the manifest
against the tree. This is the same defect that left six tasks unwinnable for weeks earlier in the
project's history, found then by accident.

## What was done

1. `tests/test_corpus_manifest_is_complete.py` added, asserting in both directions that the
   manifest and the tree agree, plus a hash check. **It failed on its first run against the tree
   as committed**, which is how the defect above was found rather than inferred.
2. `corpus/manifest.json` rebuilt: 195 to 196 entries, one line added, no existing hash changed.

## What this breaks, and it is small but real

⚠️ **A number measured on the 196-entry feed is not comparable with one measured on the
195-entry feed**, which is every run from `pilot-003` onward, or with the 125-entry feed before
that. The change is one signal session out of 195, so the effect on any retrieval or task
number is expected to be slight, but "slight" is a judgement and the rule in this project is that
the feed identity is checked rather than eyeballed. `corpus/manifest.json`'s content hash is the
identity; compare that, not the count.

Affected in flight: `preregistration/018-register-not-subject.md` quotes BM25 `hit@1 = 0.182`
under both semantic generations as an already-measured value. That was measured on the 195-entry
tree before this task landed. The record is frozen and is not edited; the correction is recorded
in its results section instead.

## Re-derive

```bash
python -m pytest tests/test_corpus_manifest_is_complete.py -q
python -c "import json;print(len(json.load(open('corpus/manifest.json'))['sessions']))"
```
