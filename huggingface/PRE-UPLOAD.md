# Hugging Face publication: the gate, and what it caught

Prepared 2026-09-01 and **published the same day**:

- dataset: https://huggingface.co/datasets/Gde05/agent-memory-bench-corpus
- Space: https://huggingface.co/spaces/Gde05/agent-memory-bench

`scripts/hf_stage.py` assembles both payloads and still uploads neither, and that stays true now
that the first upload has happened. The separation is the point: a username, a host path or an
unannounced product name cannot be recalled once it has shipped, so the act of publishing is a
person's, and this document is what they read first.

Everything below that is a number was measured on 2026-09-01 against `origin/master` at `13df300`,
and each carries the command that re-measures it.

## Two findings, both settled 2026-09-01

### 1. The corpus carries the recording machine's username, 46,057 times

**Decision: acceptable, upload as is.** That account name is used on this machine and nowhere
else, so it identifies a development box rather than a person's estate. Recorded here because the
count is the kind of thing that looks alarming when discovered later by somebody who does not know
it was weighed.

| identifier | files | occurrences |
|---|---:|---:|
| the Windows account name, anywhere | 244 | 46,057 |
| its `C:\Users\...` path shape | 234 | 23,961 |
| a POSIX home directory on the run host | 14 | 16,471 |

Measured over 1,256 tracked text files under `corpus/`, `tasks/`, `results/`, `docs/`, `reports/`,
`site/` and `huggingface/`. The bare-name count is roughly double the path-shape count because the
account also appears inside temp file names. No real email address occurs anywhere: the only four
matches are `click` decorator fragments in one distractor, and every authored address in the corpus
is under a reserved `.example.invalid` domain that cannot resolve. Re-measure, substituting the
account you are checking:

```bash
python scripts/scan_host_identifiers.py --literal <account>
```

⚠️ **This document may not name the run host's account, and writing it out here failed the suite.**
`tests/test_no_host_inventory.py` holds every tracked config and script to a clean sheet against a
literal inventory list, and an earlier draft of this file named that path three times. The guard
was right: a host inventory is disclosure even with no credential in it. The structural
`posix_home` pattern in the scan reports the same thing without any file having to spell it.

**The figure that actually decides this is smaller**, because the dataset ships the corpus and
nothing else. In the staged payload: **175 of 200 files carry `gde00`, 1,653 occurrences**, of
which 144 files are distractors and 31 are signal sessions. The other 44,404 occurrences are in
`tasks/` and `results/`, which are not uploaded. Re-measure after staging:

```bash
python -c "from pathlib import Path; f=[p for p in Path('build/hf/dataset').rglob('*') if p.is_file()]; h=[(p,p.read_text(encoding='utf-8',errors='ignore').count('gde00')) for p in f]; n=[(p,c) for p,c in h if c]; print(len(f),'files',len(n),'affected',sum(c for _,c in n),'occurrences')"
```

**There is no clean fix and none was wanted.** `corpus/README.md` rule 1 makes content verbatim
agent output, and a recording that is edited afterwards is no longer evidence of what an agent
produced. Redaction was the option not taken: a redacted corpus and a verbatim one are
indistinguishable to `manifest.json`, so the difference would survive only in prose. The card
therefore says plainly that tool results carry a development machine's paths, which is the honest
version of uploading as is.

What changed on Hugging Face was reach, not exposure. These bytes are already public on GitHub,
where they are read by people who went looking; a dataset repository is indexed, mirrored and
pulled into training corpora by parties who did not. That was the question, and it was answered.

The host account is a separate matter from the workstation one. It appears only under `results/`,
which the dataset does not ship, so nothing about it is settled by this decision. **If `results/`
is ever mirrored, decide it then**, and note that the same guard that failed this document will
not protect a payload, because the payload is not tracked.

### 2. `results/` is excluded, and that is deliberate

`abstention-001` and `diagnostic-010` have endpoints computed in the tree and are **written up
under no preregistration**, so no number from either may be quoted. Mirroring `results/` to a
platform built for leaderboard scraping would put unquotable numbers where somebody else quotes
them. `DATASET_INCLUDE` in `scripts/hf_stage.py` therefore ships the corpus and nothing else.

## The checklist

Vendor and disclosure:

- [ ] `python -m pytest tests/test_site_vendor_disclosure.py -q` passes. It now scans `site/` **and**
      `huggingface/`, so the dataset card is covered by the same guard as the pages.
- [ ] `python scripts/hf_stage.py --check` reports `vendor guard: clean`. It refuses to stage if
      `mem0`, `supermemory`, `zep`, `cognee`, `graphiti`, `falkordb`, `letta` or `memgpt` reaches
      either payload.
- [ ] No third-party product named in either card has not yet been shown its own adapter and frozen
      config. Today that is all four, so neither card names any of them.

Claims on the cards:

- [ ] Every number on the dataset card still matches the tree. Measured 2026-09-01 on `13df300`:
      **196 manifest entries, 40 under `sessions/` and 156 under `distractors/`**, manifest and
      disk in exact agreement both ways. Re-measure:

      ```bash
      python -c "import json;m=json.load(open('corpus/manifest.json'))['sessions'];print(len(m),sum(k.startswith('sessions/') for k in m),sum(k.startswith('distractors/') for k in m))"
      ```

      ✅ Settled 2026-09-01. `corpus/README.md` stated 39 signal sessions, 195 total and 4.00:1 as
      measured 2026-08-29, and the corpus gained `fa-dedup-key/p01.jsonl` with #34 on 2026-08-30.
      That file **ships inside the dataset**, so the stale figure would have become a published
      claim. A dated 🔁 correction is now appended below it, preserving the original measurement
      rather than overwriting it, and the card states the 2026-09-01 counts.
- [ ] The five standing limits are present and not softened. They are on the card because a reader
      who does not know them will over-read the results.
- [ ] The Space card still says the board is empty by construction, and
      `site/data/leaderboard.config.json` still carries `"official_run": null`. If a run has landed
      since, the card is stale.
- [ ] No result is quoted that is not written up under its preregistration.

Mechanics:

- [x] `hf auth login` with a **write** token. Only a person can supply that token.
- [x] ⚠️ **The Hugging Face namespace is `Gde05`, not the GitHub handle `GiulioDER`.** Uploading
      to the GitHub handle fails with `403 Forbidden: You don't have the rights to create a
      dataset under the namespace "GiulioDER"`, which reads as a token-permission problem and is
      not one. Confirm the namespace before assuming a scope issue:

      ```bash
      python -c "from huggingface_hub import HfApi; print(HfApi().whoami()['name'])"
      ```

- [x] `short_description` in the Space card must be **60 characters or fewer**. The API validates
      the README frontmatter before it uploads anything, so a 61-character line aborts the whole
      folder upload with `Invalid metadata in README.md`.
- [x] Creating the Space with `space_sdk="static"` leaves a stub `style.css` behind. The site
      ships `styles.css`, so the stub is dead weight and was deleted after the first upload.
- [x] The **Space** must exist with SDK **Static** before its payload is uploaded. `hf upload` has
      no `--space-sdk` option (verified against 1.24.0 with `hf upload --help`), so the CLI cannot
      create one; either make it in the web UI, or use the API, which can:

      ```bash
      python -c "from huggingface_hub import HfApi; HfApi().create_repo('Gde05/agent-memory-bench', repo_type='space', space_sdk='static', exist_ok=True)"
      ```

      The **dataset** repo needs no such step: `hf upload --repo-type=dataset` creates it.
- [ ] `python scripts/hf_stage.py`, then read `build/hf/dataset/README.md` and
      `build/hf/space/README.md` as they will appear, not as they were authored.
- [ ] Upload by hand, dataset first, so the Space card's link to it resolves on first view.

After:

- [ ] The Space renders `index.html` and its relative links to `leaderboard.html`, `method.html`
      and `submit.html` resolve. A static Space serves from the repository root, so `site/` is
      stripped during staging and any absolute `/site/...` path would break.
- [ ] `load_dataset` works for both configs against the published repository, not only locally.
- [ ] The GitHub README links to both, so the canonical source points at the mirrors rather than
      only the other way round.

## What is deliberately not prepared here

No model repository, no `datasets` loading script, and no automated sync from CI. A push to a
platform that indexes and mirrors should stay a deliberate act by a person, at least until the
first preregistered multi-product run exists and there is something to keep in step.
