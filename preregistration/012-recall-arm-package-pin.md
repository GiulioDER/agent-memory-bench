# The recall arm runs a pinned published release, not a developer worktree

Status: DRAFT until committed; a committed record is frozen above the results marker.

Written on 2026-08-29, after the `abstention-002` preregistration was committed and before its
first session, because setting up that run surfaced something that invalidates the arm's neutrality
claim if left alone.

## What was found

`adapters/recall/config.frozen.json` invokes `python -m recall.cli` and `python -m
recall_mcp.server`. On this workstation both resolved to an **editable install pointing at a live
git worktree** of the recall repository:

```
recall       C:\Users\gde00\Documents\recall\.claude\worktrees\rag-retrieval-research-1c1ef5\recall\__init__.py
_editable_impl_recall_rag.pth -> that same directory
```

Three things make that unacceptable for a benchmark rather than merely untidy:

1. **It is mutable.** That worktree is on a feature branch, held by another session, with untracked
   files in it, and it was running its own test suite while this run was being prepared. Its files
   can change between one session of the grid and the next.
2. **It is not what anyone can install.** The whole neutrality argument is that recall enters
   through the same door as every competitor, and a competitor is measured from a published
   artefact. Measuring our own product from a developer checkout is the single most obvious
   complaint a competitor could raise, and it would be correct.
3. **Its own metadata already disagreed with itself.** `recall_rag-0.9.6.dist-info` was installed
   while the imported code reported `0.9.8`, which is direct evidence the tree had moved under the
   install.

`abstention-001` ran under this arrangement. Its recall arm therefore has no version, and this
record is what stops that being true twice.

## What is pinned, and why this version

```
.venv-bench, created 2026-08-29
recall-rag[fastembed]==0.9.8   from PyPI
```

**0.9.8 rather than the latest.** 0.10.0 is published and is the newer subject, but changing the
environment and the version in one step would confound "the arm is now reproducible" with "the arm
is now a different product". 0.9.8 is the version the worktree's code reported, so pinning it
changes exactly one thing: mutability. Moving to the latest release is a separate decision and
belongs in a record that predicts what moving it should do.

`config.frozen.json` carried `"package_pin": "TBD: recall-rag==<exact version, frozen at the Phase
4 preregistration>"`. That TBD is now filled.

## Database

The recall arm's corpus lives in a disposable container started for this run,
`amb-abstention-002`, on `127.0.0.1:5544`, one tenant per condition. Two setup steps are needed on
a fresh database and neither is a protocol change:

* `CREATE EXTENSION vector`, which the image ships but does not enable;
* `recall schema apply` with `RECALL_MIGRATION_DSN`, because recall separates DDL from the serving
  DSN by design and refuses to run migrations through the latter.

## What this does not change

No endpoint, no prediction, no task, no plant, no arm. The instruction, the embedder
(`fastembed`), the trust mode (`development`) and the allowed tools are exactly as
`config.frozen.json` already froze them. `abstention-002`'s predictions in record 011 stand
unamended.

## What would falsify the claim this record makes

The claim is only that the recall arm is now reproducible from a published artefact. It is
falsified if `python -m recall.cli` inside `.venv-bench` resolves anywhere other than
`.venv-bench/Lib/site-packages/recall`, which is checked before the first session and re-checkable
in a second:

```bash
./.venv-bench/Scripts/python.exe -c "import recall; print(recall.__file__, recall.__version__)"
```

## What this costs, stated plainly

`abstention-001` and `abstention-002` are **not comparable on the recall arm**. The earlier run's
subject was an unrecorded worktree state and the later one's is 0.9.8. Any comparison between them
on that arm is worth nothing, and none will be reported.

<!-- results are appended below this line; everything above is frozen -->
