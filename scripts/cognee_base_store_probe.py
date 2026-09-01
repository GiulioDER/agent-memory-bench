"""Prove that copying a cognee base store is equivalent to ingesting the corpus monolithically.

⛔ **Run this before any run sets the base-store variable.** The reuse in
`adapters/cognee/adapter.py` saves an LLM extraction pass over the shared haystack per condition,
which is the difference between roughly 7.6M tokens once and five times. It is also the kind of
shortcut that fails silently: a copied store that quietly holds less produces an arm measured on a
corpus nobody described, with ingest reporting success and every gate green.

MemPalace's equivalent reuse was verified on a 20-document probe BEFORE being relied on, and this
is the same probe for cognee. It has NOT been run: the workstation this was written on has a Xeon
X5690 with no AVX, and cognee's vector store executes an illegal instruction there.

    python scripts/cognee_base_store_probe.py --documents 20

Exit codes: 0 the reuse is sound on this host, 1 a check failed, 2 the environment is not
configured. What it checks, in order:

1. a base store built from HALF the documents holds exactly those documents;
2. a copy of it **retains** its contents;
3. the copy **accepts further ingest** of the other half;
4. the original is left **untouched** by that second ingest;
5. the copy retrieves the newly ingested content;
6. the copy returns **identical** top-k results to a store built monolithically from all of
   the documents, across several queries.

Check 6 is the one that matters and the one a cheaper probe would skip: the others can all pass
while the reused store ranks differently, and a ranking difference between conditions is
indistinguishable from a finding about the product.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from adapters.cognee.adapter import CogneeAdapter, parse_driver_report
from harness.adapters.base import CorpusManifest
from harness.transcripts import render_corpus

CONFIG = json.loads(
    (REPO / "adapters" / "cognee" / "config.frozen.json").read_text(encoding="utf-8")
)
DRIVER = REPO / "adapters" / "cognee" / "ingest_driver.py"

OK, BAD = "  OK  ", " FAIL "

#: Queries the probe compares between the reused and the monolithic store. Drawn from the corpus
#: rather than invented, so a miss means the stores differ rather than that the question was
#: unanswerable.
QUERIES = (
    "append only audit trail",
    "retry backoff",
    "timestamp format",
)


def report(ok: bool, headline: str, detail: str = "") -> bool:
    print(f"[{OK if ok else BAD}] {headline}")
    if detail:
        for line in detail.strip().splitlines():
            print(f"         {line}")
    return ok


def _ingest(adapter: CogneeAdapter, namespace: str, paths: list[Path], root: Path) -> dict:
    """Render `paths` and drive one real ingest into `namespace`'s store. This SPENDS."""

    store = adapter._store_dir(namespace)
    feed = adapter._feed_dir(namespace)
    for stale in (feed,):
        shutil.rmtree(stale, ignore_errors=True)
    store.mkdir(parents=True, exist_ok=True)
    render_corpus(paths, feed, root=root)
    result = subprocess.run(
        [
            str(adapter._venv_bin("python")), str(DRIVER), str(feed),
            adapter.dataset(namespace), str(float(CONFIG["ingest_cost_ceiling_usd"])),
            str(int(CONFIG["ingest_token_ceiling"])),
        ],
        cwd=str(store), env=adapter.cognee_env(namespace),
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ingest into {namespace} failed: {result.stderr[-1500:]}")
    return parse_driver_report(result.stdout)


def _search(adapter: CogneeAdapter, namespace: str, query: str, top_k: int) -> list[str]:
    """The store's own answer to one query, as an ordered list of source names.

    Order is the payload: two stores holding the same documents but ranking them differently are
    not interchangeable, and a condition served by the reused store would differ from one served
    by a monolithic build for a reason no artifact would record.
    """

    script = (
        "import asyncio, json, sys\n"
        "import cognee\n"
        "from cognee.modules.search.types import SearchType\n"
        "async def main():\n"
        "    hits = await cognee.search(query_text=sys.argv[1],\n"
        "        query_type=SearchType.CHUNKS, datasets=[sys.argv[2]], top_k=int(sys.argv[3]))\n"
        "    print('PROBE_JSON ' + json.dumps([str(h) for h in (hits or [])]))\n"
        "asyncio.run(main())\n"
    )
    result = subprocess.run(
        [str(adapter._venv_bin("python")), "-c", script,
         query, adapter.dataset(namespace), str(top_k)],
        cwd=str(adapter._store_dir(namespace)), env=adapter.cognee_env(namespace),
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    for line in reversed(result.stdout.splitlines()):
        if line.strip().startswith("PROBE_JSON "):
            return json.loads(line.strip()[len("PROBE_JSON "):])
    raise RuntimeError(f"search in {namespace} returned no probe line: {result.stderr[-1500:]}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-root", default=str(REPO / "corpus"))
    parser.add_argument(
        "--documents", type=int, default=20,
        help="how many corpus documents to use. Every one is an LLM extraction pass, and the "
             "probe ingests them three times over, so keep it small.",
    )
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    if not os.environ.get(str(CONFIG["venv_env"])):
        print(f"[{BAD}] {CONFIG['venv_env']} is unset; see scripts/cognee_preflight.py")
        return 2

    corpus = CorpusManifest.load(Path(args.corpus_root))
    chosen = sorted(corpus.sessions)[: args.documents]
    if len(chosen) < 4:
        print(f"[{BAD}] need at least 4 documents, got {len(chosen)}")
        return 2
    half = len(chosen) // 2
    shared, extra = chosen[:half], chosen[half:]
    paths = {rel: Path(args.corpus_root) / rel for rel in chosen}
    root = Path(args.corpus_root)

    prompt = REPO / "corpus" / "claude_md_bundle_smoke.md"
    adapter = CogneeAdapter(Path(tempfile.gettempdir()) / "cgn-probe", prompt)
    checks: list[bool] = []

    # 1. the base holds exactly what it was given
    _ingest(adapter, "probe-base", [paths[rel] for rel in shared], root)
    base = adapter._store_dir("probe-base")
    filed = CogneeAdapter.filed_document_count(base)
    checks.append(report(
        filed == len(shared),
        f"base store holds {filed} of {len(shared)} shared document(s)",
    ))

    # 2. a copy retains its contents
    copied = adapter._store_dir("probe-copy")
    shutil.rmtree(copied, ignore_errors=True)
    shutil.copytree(base, copied)
    retained = CogneeAdapter.filed_document_count(copied)
    checks.append(report(
        retained == filed, f"the copy retains {retained} document(s)"
    ))

    # 3. the copy accepts further ingest, and 4. the original is untouched
    _ingest(adapter, "probe-copy", [paths[rel] for rel in extra], root)
    after_copy = CogneeAdapter.filed_document_count(copied)
    after_base = CogneeAdapter.filed_document_count(base)
    checks.append(report(
        after_copy == len(chosen),
        f"the copy accepts further ingest: {after_copy} of {len(chosen)} document(s)",
    ))
    checks.append(report(
        after_base == filed,
        f"the original is untouched: still {after_base} document(s)",
    ))

    # 5 and 6. the copy retrieves the new content, and ranks identically to a monolithic build
    _ingest(adapter, "probe-mono", [paths[rel] for rel in chosen], root)
    for query in QUERIES:
        reused = _search(adapter, "probe-copy", query, args.top_k)
        mono = _search(adapter, "probe-mono", query, args.top_k)
        checks.append(report(
            bool(reused), f"the copy answers {query!r} with {len(reused)} hit(s)"
        ))
        checks.append(report(
            reused == mono,
            f"identical top-{args.top_k} for {query!r}",
            "" if reused == mono else f"reused: {reused}\nmonolithic: {mono}",
        ))

    print()
    if all(checks):
        print(
            f"the base store reuse is sound on this host. Set "
            f"{CONFIG['base_store_env']} to a base built from the run's own haystack."
        )
        return 0
    print(
        "the base store reuse is NOT sound here; do not set "
        f"{CONFIG['base_store_env']} for a run on this host."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
