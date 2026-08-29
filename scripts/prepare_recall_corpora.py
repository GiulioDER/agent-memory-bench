"""Build, calibrate and promote one immutable generation per condition, on the serving host.

Run this BEFORE the suite. `RecallAdapter.ingest` then verifies rather than builds, which is the
whole point: a generation build embeds the corpus and a calibration fits a threshold to it, so
doing either inside a run means a remote failure kills the run mid-flight, and a step that can
build is a step that can silently REBUILD. A rebuilt corpus mid-run is a different experiment.

    python -m scripts.prepare_recall_corpora --conditions absent,superseded,contradictory,adjacent

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

from adapters.recall.adapter import corpus_fingerprint
from harness.adapters.base import CorpusManifest
from harness.transcripts import render_corpus
from scripts.abstention import selection_for
from scripts.assemble_condition_corpus import assemble

CONFIG = json.loads((REPO / "adapters" / "recall" / "config.frozen.json").read_text("utf-8"))
QUERIES = REPO / "calibration" / "abstention-queryset-v1.json"


def ssh(command: str, *, timeout: float = 3600.0) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["ssh", "-o", "BatchMode=yes", str(CONFIG["ssh_host"]), command],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def remote_env() -> str:
    """The env prelude every remote recall command needs."""

    return (
        f"cd {shlex.quote(str(CONFIG['remote_root']))} && "
        f"set -a && . {shlex.quote(str(CONFIG['remote_env_file']))} && set +a && "
        f"export RECALL_DSN={shlex.quote(str(CONFIG['dsn']))} "
        f"RECALL_MIGRATION_DSN={shlex.quote(str(CONFIG['dsn']))} "
        f"RECALL_EMBEDDER={shlex.quote(str(CONFIG['embedder']))} "
        f"RECALL_LOCAL_ALLOWLIST={shlex.quote(str(CONFIG['remote_root']))}"
    )


def recall(tenant: str, args: str, *, production: bool = False, timeout: float = 3600.0):
    env = remote_env()
    if production:
        env += " RECALL_ENV=production"
    command = (
        f"{env} && {shlex.quote(str(CONFIG['remote_python']))} -m recall.cli "
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

    stamp = ssh(f"cat {shlex.quote(str(CONFIG['remote_root']))}/{shlex.quote(tenant)}.corpus")
    if not force and stamp.returncode == 0 and stamp.stdout.strip() == fingerprint:
        listing = recall(tenant, "generation list", production=True, timeout=300)
        if any(" active " in f" {line} " for line in listing.stdout.splitlines()):
            print("  already built, calibrated and promoted for this exact corpus; skipping")
            return

    feed = REPO / "results" / ".prepare-feed" / tenant
    if feed.exists():
        import shutil

        shutil.rmtree(feed)
    written = render_corpus([corpus_root / rel for rel in corpus.sessions], feed, root=corpus_root)
    print(f"  rendered {written} file(s)")

    archive = REPO / "results" / f".prepare-{tenant}.tgz"
    subprocess.run(
        ["tar", "-czf", str(archive), "-C", str(feed.parent), feed.name], check=True, timeout=600
    )
    subprocess.run(
        ["scp", "-q", str(archive), f"{CONFIG['ssh_host']}:{CONFIG['remote_root']}/"],
        check=True,
        timeout=1800,
    )
    r = ssh(
        f"cd {shlex.quote(str(CONFIG['remote_root']))} && rm -rf {shlex.quote(tenant)} && "
        f"tar -xzf {shlex.quote(archive.name)} && ls {shlex.quote(tenant)} | wc -l"
    )
    print(f"  shipped {r.stdout.strip()} file(s)")

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
        f"cd {shlex.quote(str(CONFIG['remote_root']))} && "
        f"sha256sum {tenant}.manifest.json | cut -d' ' -f1 && stat -c%s {tenant}.manifest.json"
    )
    sha, size = digest.stdout.split()
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

    ssh(
        f"printf %s {shlex.quote(fingerprint)} > "
        f"{shlex.quote(str(CONFIG['remote_root']))}/{shlex.quote(tenant)}.corpus"
    )
    print(f"  stamped {fingerprint[:16]}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--conditions", default="absent,superseded,contradictory,adjacent")
    parser.add_argument("--namespace", default="bench-official")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--force", action="store_true", help="rebuild even if the stamp matches")
    args = parser.parse_args()

    scp = subprocess.run(
        ["scp", "-q", str(QUERIES), f"{CONFIG['ssh_host']}:{CONFIG['remote_root']}/"],
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
