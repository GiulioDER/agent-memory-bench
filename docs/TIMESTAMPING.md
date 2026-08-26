# Trusted timestamps for preregistrations

The benchmark's credibility rests on one temporal claim: **the prediction was written before
the measurement.** The preregistration guard (`harness/prereg.py`) enforces that predictions
are committed before a run starts, but a git commit date is written by the committer;
`GIT_COMMITTER_DATE` is an environment variable, and a skeptic is right not to accept it.
This mechanism adds anchors whose time is not ours to edit.

## What it proves

An anchored manifest proves exactly one thing: **the stamped bytes existed no later than the
anchor's time.** Concretely:

- `preregistration/timestamps/manifest-<utc>.json` records the sha256, size, and git blob id
  of every preregistration file at stamp time, plus the commit that contained them.
- Pushing that manifest to GitHub before the run gives it a server-side receipt time that
  the repository owner cannot edit.
- When the OpenTimestamps client is installed, `<manifest>.ots` anchors the manifest's hash
  against public calendar servers and, eventually, a Bitcoin block header. That anchor is
  verifiable by anyone, forever, without trusting this repository or GitHub.

Together with the run artifacts (which cite the preregistration), this closes the claim:
predictions with these exact bytes existed before the anchor, and the anchor precedes the
run.

## What it deliberately does not claim

Cryptography here proves precedence and integrity, nothing else.

- It does **not** prove the run was honest. A fabricated run could be preceded by a real
  timestamp. The defenses against fabrication are elsewhere: full per-session logs and
  streams in `results/<run_id>/`, end-to-end cost ledgers, and one-command third-party
  re-runs.
- It does **not** prove the stamped prediction is the *only* one that existed. Nothing
  stops someone stamping ten contradictory predictions and publishing one. The defense is
  the repository itself: preregistrations are numbered, public, and append-only, so a
  shadow prediction would have to live outside the repo, where it earns no credibility.
- It does **not** freeze the files. Results are *supposed* to be appended below the frozen
  prediction in the same file, so files legitimately change after stamping. The manifest
  records the git blob id precisely so the stamped bytes stay recoverable afterwards:
  `git cat-file blob <id>` reproduces exactly what was anchored.

## Workflow

Order matters; each step anchors the previous one.

```bash
python scripts/timestamp_prereg.py stamp     # writes the manifest (+ .ots if ots exists)
git add preregistration/timestamps && git commit   # the run guard forces this anyway
git push                                     # first independent anchor
# ... then, and only then, start the run
```

The manifest is written *inside* `preregistration/`, so the existing run guard refuses to
measure while it is uncommitted. That is intentional: the mechanism reuses the guard rather
than trusting a new convention.

Verification, any time later:

```bash
python scripts/timestamp_prereg.py verify            # latest manifest, informational
python scripts/timestamp_prereg.py verify --strict   # exact match required (pre-run check)
```

`MATCH` means bytes identical to the stamped ones. `CHANGED` is expected once results have
been appended, and the verdict includes whether the stamped blob is still recoverable from
history. `MISSING` always fails: preregistration files never legitimately disappear.

## Rules

- **Manifests are append-only.** A new stamp creates a new manifest; nothing overwrites or
  deletes an old one. A superseded manifest is history, not garbage.
- **Stamp before every measured run**, so the manifest closest in time to the run covers the
  preregistration that run cites.
- **The `.ots` file is optional but never silent.** If the client is missing, the stamp
  command says so and prints the exact command to run later; the proven time is when the
  stamp is actually made, which stays honest.
