"""Build, calibrate and promote one immutable generation per condition, on the serving host.

Run this BEFORE the suite. `RecallAdapter.ingest` then verifies rather than builds, which is the
whole point: a generation build embeds the corpus and a calibration fits a threshold to it, so
doing either inside a run means a remote failure kills the run mid-flight, and a step that can
build is a step that can silently REBUILD. A rebuilt corpus mid-run is a different experiment.

    python -m scripts.prepare_recall_corpora        # every condition in CORPUS_CONDITIONS
    python -m scripts.prepare_recall_corpora --conditions present,adjacent   # or a subset

Idempotent: a condition whose tenant already serves an active generation stamped with this
corpus's fingerprint is skipped.

## Why the pipeline has this shape

`recall index` is refused under `RECALL_ENV=production`, and production is the only switch that
routes search through `GenerationStore`. So a corpus that is served as calibrated CANNOT be built
with the ordinary indexer; it goes through manifest -> generation -> calibration -> promote. Three
steps in that chain are easy to get wrong and each failed once here:

* `manifest inventory` emits an object LIST, not a manifest. `manifest create` canonicalises it,
  and skipping that gives "manifest root must be an object".
* the manifest carries its own tenant, so `--tenant` belongs on CREATE, not only on build.
* under production a local manifest must be VERIFIED, so `--manifest-sha256` and `--manifest-size`
  are required rather than optional.
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from adapters.recall.adapter import corpus_fingerprint, resolve_location
from harness.adapters.base import CorpusManifest, namespace_path, validate_namespace
from harness.damage import CORPUS_CONDITIONS
from harness.transcripts import render_corpus
from scripts.abstention import selection_for
from scripts.assemble_condition_corpus import assemble

CONFIG = json.loads((REPO / "adapters" / "recall" / "config.frozen.json").read_text("utf-8"))
QUERIES = REPO / "calibration" / "abstention-queryset-v1.json"



def _location(key: str) -> str:
    """A host-specific value, named by the frozen config and supplied by the environment.

    The config carries `<key>_env` rather than the value itself, because this tree is public and
    a host inventory is disclosure on its own, per .gitignore's first three lines. Refusing on an
    unset variable beats defaulting: a default is how a production .env path and another
    project's socket reached a published artifact.
    """

    try:
        return resolve_location(CONFIG, key)
    except LookupError as exc:
        raise SystemExit(
            f"{exc.args[0]} is unset, so this script does not know the corpus host's {key}. Put "
            f"it in the secrets file scripts/launch_official.sh sources; see "
            f"adapters/recall/location.example.env."
        ) from None


def ssh(command: str, *, timeout: float = 3600.0) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["ssh", "-o", "BatchMode=yes", _location('ssh_host'), command],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def remote_env() -> str:
    """The env prelude every remote recall command needs."""

    return (
        f"cd {shlex.quote(_location('remote_root'))} && "
        f"set -a && . {shlex.quote(_location('remote_env_file'))} && set +a && "
        f"export RECALL_DSN={shlex.quote(_location('dsn'))} "
        f"RECALL_MIGRATION_DSN={shlex.quote(_location('dsn'))} "
        f"RECALL_EMBEDDER={shlex.quote(str(CONFIG['embedder']))} "
        f"RECALL_LOCAL_ALLOWLIST={shlex.quote(_location('remote_root'))}"
    )


def recall(tenant: str, args: str, *, production: bool = False, timeout: float = 3600.0):
    env = remote_env()
    if production:
        env += " RECALL_ENV=production"
    command = (
        f"{env} && {shlex.quote(_location('remote_python'))} -m recall.cli "
        f"--tenant {shlex.quote(tenant)} {args}"
    )
    return ssh(command, timeout=timeout)


def prepare(condition: str, seed: int, namespace: str, *, force: bool) -> None:
    # Same shape the runner uses, `<namespace>-<condition>`, so the suite and this script
    # cannot disagree about which tenant holds which condition.
    tenant = f"{namespace}-{condition}"
    corpus_root = REPO / "corpus" / "conditions" / condition / f"seed-{seed}"
    selection = selection_for(condition)
    if not selection:
        raise SystemExit(f"no task declares {condition!r}")

    print(f"\n=== {condition} -> tenant {tenant} ({len(selection)} task(s)) ===")
    assemble(condition, seed, selection, corpus_root)
    corpus = CorpusManifest.load(corpus_root)
    corpus.verify()
    fingerprint = corpus_fingerprint(corpus)
    print(f"  corpus fingerprint {fingerprint[:16]}  ({len(corpus.sessions)} sessions)")

    stamp = ssh(f"cat {shlex.quote(_location('remote_root'))}/{shlex.quote(tenant)}.corpus")
    if not force and stamp.returncode == 0 and stamp.stdout.strip() == fingerprint:
        listing = recall(tenant, "generation list", production=True, timeout=300)
        if any(" active " in f" {line} " for line in listing.stdout.splitlines()):
            print("  already built, calibrated and promoted for this exact corpus; skipping")
            return

    # `tenant` derives from the --namespace CLI argument, which is the flag F-15
    # named, and `shutil.rmtree(feed)` is four lines below.
    feed = namespace_path(REPO / "results" / ".prepare-feed", tenant)
    if feed.exists():
        import shutil

        shutil.rmtree(feed)
    written = render_corpus([corpus_root / rel for rel in corpus.sessions], feed, root=corpus_root)
    print(f"  rendered {written} file(s)")

    # Validated before the f-string, which would otherwise smuggle a traversal through
    # as a prefix of a name that looks constructed.
    archive = REPO / "results" / f".prepare-{validate_namespace(tenant)}.tgz"
    subprocess.run(
        ["tar", "-czf", str(archive), "-C", str(feed.parent), feed.name], check=True, timeout=600
    )
    subprocess.run(
        ["scp", "-q", str(archive), f"{_location('ssh_host')}:{_location('remote_root')}/"],
        check=True,
        timeout=1800,
    )
    r = ssh(
        f"cd {shlex.quote(_location('remote_root'))} && rm -rf {shlex.quote(tenant)} && "
        f"tar -xzf {shlex.quote(archive.name)} && ls {shlex.quote(tenant)} | wc -l"
    )
    # ⚠️ The `rm -rf` above has already run, so the previous good corpus is gone. Everything
    # downstream succeeds happily over a partial feed -- inventory inventories what is there,
    # the manifest is built FROM it, and `generation build --manifest-sha256` hashes that
    # manifest against itself -- and the run then stamps the tenant with the fingerprint of the
    # FULL LOCAL manifest. The adapter's later identity check compares that same local
    # fingerprint, so it is circular and cannot see the gap. This is the only place the two
    # counts exist side by side, so it is the only place the truncation is visible.
    if r.returncode != 0:
        raise SystemExit(f"  ship FAILED: {r.stderr.strip()[-600:]}")
    try:
        shipped = int(r.stdout.strip())
    except ValueError:
        raise SystemExit(
            f"  ship FAILED: expected a file count, got {r.stdout.strip()[:200]!r}"
        ) from None
    if shipped != written:
        raise SystemExit(
            f"  ship FAILED: rendered {written} file(s) but {shipped} arrived. The remote FEED "
            f"directory was removed before extracting, so it now holds a partial corpus. The "
            f"previously promoted generation is still ACTIVE and still answering from the OLD "
            f"corpus, and the stamp still names it, so a run will refuse until this is re-run "
            f"successfully. Re-run rather than continuing: a generation built from a partial feed "
            f"certifies and promotes normally, and the stamp would then claim the whole corpus."
        )
    print(f"  shipped {shipped} file(s), matching what was rendered")

    steps = [
        ("inventory", f"manifest inventory {shlex.quote(tenant)} --output {tenant}.objects.json"),
        (
            "manifest",
            (
                f"manifest create --corpus-version "
                f"{shlex.quote(f'{tenant}-{fingerprint[:12]}')} "
                f"--objects {tenant}.objects.json --output {tenant}.manifest.json"
            ),
        ),
    ]
    for label, args in steps:
        r = recall(tenant, args, timeout=900)
        if r.returncode != 0:
            raise SystemExit(f"  {label} FAILED: {r.stderr.strip()[-600:]}")
        print(f"  {label}: {r.stdout.strip().splitlines()[-1][:100]}")

    digest = ssh(
        f"cd {shlex.quote(_location('remote_root'))} && "
        f"sha256sum {tenant}.manifest.json | cut -d' ' -f1 && stat -c%s {tenant}.manifest.json"
    )
    if digest.returncode != 0:
        raise SystemExit(f"  manifest digest FAILED: {digest.stderr.strip()[-600:]}")
    parts = digest.stdout.split()
    if len(parts) != 2:
        raise SystemExit(
            f"  manifest digest FAILED: expected a sha and a size, got {digest.stdout[:200]!r}"
        )
    sha, size = parts
    r = recall(
        tenant,
        f"generation build {tenant}.manifest.json --manifest-sha256 {sha} "
        f"--manifest-size {size} --unverified-development",
        timeout=5400,
    )
    if r.returncode != 0:
        raise SystemExit(f"  build FAILED: {r.stderr.strip()[-800:]}")
    generation = next(
        (
            line.split()[-1]
            for line in r.stdout.splitlines()
            if line.strip().startswith("candidate:")
        ),
        None,
    )
    if not generation:
        raise SystemExit(f"  build produced no generation id:\n{r.stdout[-600:]}")
    print(f"  built {generation}")

    for label, args, prod in (
        ("validate", f"generation validate {generation}", False),
        (
            "calibrate",
            (
                f"calibration calibrate --generation {generation} "
                f"--queries {QUERIES.name} --publish"
            ),
            False,
        ),
        ("promote", f"generation promote {generation}", True),
    ):
        r = recall(tenant, args, production=prod, timeout=1800)
        if r.returncode != 0:
            raise SystemExit(f"  {label} FAILED: {r.stderr.strip()[-800:]}")
        tail = [ln for ln in r.stdout.splitlines() if ln.strip()]
        print(f"  {label}: {tail[-1][:110] if tail else 'ok'}")

    # The stamp is what `RecallAdapter._verify_remote_generation` reads to confirm the tenant is
    # serving THIS corpus, so "stamped" printing when nothing was written turns that check into a
    # check of a stale file. Written, then read back, because a successful `printf` into a full or
    # read-only filesystem is not a guarantee that the bytes are there.
    written_stamp = ssh(
        f"printf %s {shlex.quote(fingerprint)} > "
        f"{shlex.quote(_location('remote_root'))}/{shlex.quote(tenant)}.corpus"
    )
    if written_stamp.returncode != 0:
        raise SystemExit(f"  stamp FAILED: {written_stamp.stderr.strip()[-600:]}")
    back = ssh(f"cat {shlex.quote(_location('remote_root'))}/{shlex.quote(tenant)}.corpus")
    if back.returncode != 0 or back.stdout.strip() != fingerprint:
        raise SystemExit(
            f"  stamp FAILED: wrote {fingerprint[:16]} but read back "
            f"{back.stdout.strip()[:64]!r}. The generation is promoted and serving; the stamp "
            f"that proves which corpus it came from is not."
        )
    print(f"  stamped {fingerprint[:16]}, read back and confirmed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--conditions",
        # Derived from the one definition, so adding a condition cannot leave this behind.
        # The literal that stood here omitted `present`, and this build is the MANDATORY
        # pre-suite step: the tenant simply would not exist, and the arm would have been
        # measured on the condition it is the control for.
        default=",".join(CORPUS_CONDITIONS),
    )
    parser.add_argument("--namespace", default="bench-official")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--force", action="store_true", help="rebuild even if the stamp matches")
    args = parser.parse_args()

    scp = subprocess.run(
        ["scp", "-q", str(QUERIES), f"{_location('ssh_host')}:{_location('remote_root')}/"],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    if scp.returncode != 0:
        raise SystemExit(f"could not ship the query set: {scp.stderr.strip()}")

    for condition in [c.strip() for c in args.conditions.split(",") if c.strip()]:
        prepare(condition, args.seed, args.namespace, force=args.force)
    print("\nall requested conditions are built, certified and promoted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
