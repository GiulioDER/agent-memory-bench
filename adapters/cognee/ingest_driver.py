"""Drive one cognee ingest, inside cognee's own virtualenv, and report what it cost.

Run by :meth:`adapters.cognee.adapter.CogneeAdapter.ingest` as a subprocess, never imported by
the harness: cognee lives in a separate environment and importing it here would drag its
dependency tree into every arm. Its bytes are hashed into the arm's ``config_dir_digest``, so
the driver a run used is provable from the run record.

    python ingest_driver.py <feed_dir> <dataset> <ceiling_usd> <token_ceiling> [--estimate-only]

Prints exactly one machine-readable line to stdout::

    COGNEE_JSON {"files": 4889, "estimate": {...}, "cognified": true, "probe_hits": 5}

The order of operations is the point of this file:

1. ``add`` the rendered feed into the dataset. No LLM call, no extraction.
2. ``cognify(dry_run=True)``, which cognee answers from the real chunker, prompt templates and
   response schema **without making a single LLM call**.
3. Refuse, loudly and before spending anything, when that estimate exceeds the ceiling the frozen
   config names.
4. Only then run the real ``cognify``.
5. Probe the store with a retrieval-only search, because a pipeline that reports success and
   stores nothing answers every question with silence, and silence reads as a product that found
   nothing rather than as a wiring fault.

⛔ Step 3 is the reason this arm can be run at all. cognee extracts entities and relations with a
hosted LLM, so unlike a local-embedding arm its ingest has a bill, and the bill scales with the
corpus rather than with the grid. The vendor ships the estimator; using it before the spend rather
than reconstructing the spend afterwards is the whole difference between a known cost and a
discovered one.

⚠️ What the estimate is NOT, in cognee's own words (`cognee/modules/cognify/estimator.py`): it
covers the two LLM-heavy stages and excludes embedding cost, it is an upper bound on a re-run
because incremental loading skips processed documents, and its output tokens are heuristics rather
than measurements. So it is a bound to decide by, not a bill to publish as measured spend.
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import sys
from pathlib import Path


def _probe_text(files: list[Path]) -> str:
    """A query drawn from the corpus itself, so the probe cannot pass on an empty store.

    Taken from the middle of the first document rather than its head: a rendered transcript opens
    with frontmatter and a role marker, which every document in the feed shares, so a head query
    would match anything and prove nothing.
    """

    lines = [
        line.strip()
        for line in files[0].read_text(encoding="utf-8", errors="replace").splitlines()
        if len(line.strip()) > 40
    ]
    if not lines:
        raise SystemExit("the first feed document has no line long enough to probe with")
    return lines[len(lines) // 2][:200]


def _configure_bounded_retries() -> dict[str, int | float | str | bool]:
    """Keep one malformed LLM response from retrying the whole ingest indefinitely.

    Cognee 1.5.3 decorates structured-output calls with a retry policy that requires both a
    minimum attempt count and a minimum elapsed time. With its 240-second time floor, a provider
    that repeatedly emits invalid JSON can hold one corpus ingest open for hours. The benchmark
    needs a bounded failure that leaves a useful log and a non-cognified store instead.
    """

    try:
        attempts = int(os.environ.get("AMB_COGNEE_LLM_RETRY_ATTEMPTS", "2"))
        max_seconds = float(os.environ.get("AMB_COGNEE_LLM_RETRY_MAX_SECONDS", "30"))
    except ValueError as error:
        raise SystemExit(
            "AMB_COGNEE_LLM_RETRY_ATTEMPTS must be an integer and "
            "AMB_COGNEE_LLM_RETRY_MAX_SECONDS must be a number"
        ) from error
    if attempts < 1 or max_seconds <= 0:
        raise SystemExit(
            "AMB_COGNEE_LLM_RETRY_ATTEMPTS must be >= 1 and "
            "AMB_COGNEE_LLM_RETRY_MAX_SECONDS must be > 0"
        )

    framework = os.environ.get("STRUCTURED_OUTPUT_FRAMEWORK", "litellm_native").lower()
    policy: dict[str, int | float | str | bool] = {
        "framework": framework,
        "attempts": attempts,
        "max_seconds": max_seconds,
        "patched": False,
    }
    if framework != "litellm_native":
        return policy

    from tenacity import stop_after_attempt, stop_after_delay
    from cognee.infrastructure.llm.structured_output_framework.litellm_native.native_adapter import (
        NativeLiteLLMAdapter,
    )

    retrying = NativeLiteLLMAdapter.acreate_structured_output.retry
    retrying.stop = stop_after_attempt(attempts) | stop_after_delay(max_seconds)
    policy["patched"] = True
    return policy


def _store_matches_feed(files: list[Path]) -> bool:
    """Return whether the configured SQLite store already contains exactly this feed."""

    if os.environ.get("DB_PROVIDER", "").lower() != "sqlite":
        return False
    system_root = os.environ.get("SYSTEM_ROOT_DIRECTORY")
    if not system_root:
        return False
    database = Path(system_root) / "databases" / "cognee_db"
    if not database.is_file():
        return False

    try:
        with sqlite3.connect(database) as connection:
            names = {
                row[0]
                for row in connection.execute("SELECT name FROM data")
                if row[0] is not None
            }
    except sqlite3.Error:
        return False
    return names == {path.stem for path in files}


async def _run(
    feed: Path, dataset: str, ceiling: float, token_ceiling: int, estimate_only: bool
) -> dict:
    import cognee
    from cognee.modules.search.types import SearchType

    retry_policy = _configure_bounded_retries()

    files = sorted(feed.glob("*.md"))
    if not files:
        raise SystemExit(f"no rendered documents in {feed}")

    add_skipped = _store_matches_feed(files)
    if not add_skipped:
        await cognee.add(data=[str(path) for path in files], dataset_name=dataset)

    estimate = await cognee.cognify(datasets=[dataset], dry_run=True)
    estimate_dict = estimate.to_dict() if hasattr(estimate, "to_dict") else dict(estimate)
    report = {
        "files": len(files),
        "dataset": dataset,
        "estimate": estimate_dict,
        "retry_policy": retry_policy,
        "add_skipped": add_skipped,
    }

    cost = float(estimate_dict.get("estimated_cost_usd") or 0.0)
    tokens = int(estimate_dict.get("total_tokens") or 0)

    def refuse(message: str) -> None:
        report["refused"] = True
        print("COGNEE_JSON " + json.dumps(report))
        raise SystemExit(message)

    # ⛔ TOKENS are the authority here, not the vendor's dollar figure. Measured 2026-09-01 on the
    # 196-document corpus: the dry run returned `estimated_cost_usd: 0.0` alongside 316,674
    # tokens, warning "no pricing entry for model 'openai/deepseek/deepseek-v4-flash'". cognee
    # prices from its own table and an unknown model costs $0 there, so the dollar ceiling this
    # file shipped with would have waved through a bill of any size while reading as a guard.
    # Tokens are also the unit this benchmark compares runs in, because its published dollar
    # bases have differed and a rate belongs to a run rather than to a frozen adapter config.
    if token_ceiling and tokens > token_ceiling:
        refuse(
            f"cognee's own dry run estimates {tokens:,} token(s) for this corpus, over the "
            f"{token_ceiling:,} in adapters/cognee/config.frozen.json. Nothing has been spent. "
            f"Raise the ceiling deliberately in that file, which re-hashes the frozen config and "
            f"is recorded in every session record, or ingest a smaller corpus."
        )
    if cost > ceiling:
        refuse(
            f"cognee's own dry run estimates ${cost:.2f} for this corpus, over the "
            f"${ceiling:.2f} ceiling in adapters/cognee/config.frozen.json. Nothing has been "
            f"spent. Raise the ceiling deliberately in that file, which re-hashes the frozen "
            f"config and is recorded in every session record, or ingest a smaller corpus."
        )
    if tokens and not cost and not token_ceiling:
        refuse(
            f"cognee estimates {tokens:,} token(s) and cannot price them: "
            f"{'; '.join(estimate_dict.get('warnings') or ['no warning given'])}. With no token "
            f"ceiling configured, nothing is holding this run: a guard that cannot fire is worse "
            f"than no guard, because it reads as one. Set ingest_token_ceiling in "
            f"adapters/cognee/config.frozen.json."
        )
    if estimate_only:
        report["cognified"] = False
        print("COGNEE_JSON " + json.dumps(report))
        return report

    await cognee.cognify(datasets=[dataset])
    report["cognified"] = True

    hits = await cognee.search(
        query_text=_probe_text(files),
        query_type=SearchType.CHUNKS,
        datasets=[dataset],
        top_k=5,
    )
    report["probe_hits"] = len(hits or [])
    print("COGNEE_JSON " + json.dumps(report))
    return report


def main() -> int:
    arguments = sys.argv[1:]
    estimate_only = "--estimate-only" in arguments
    positional = [argument for argument in arguments if argument != "--estimate-only"]
    if len(positional) != 4:
        raise SystemExit(__doc__)
    feed, dataset = Path(positional[0]), positional[1]
    ceiling, token_ceiling = float(positional[2]), int(positional[3])

    # cognee's package __init__ calls `dotenv.load_dotenv(override=True)`, so a stray .env BEATS
    # the environment the adapter passes in and silently redirects the LLM, the embedder and the
    # databases. `find_dotenv` walks up from the IMPORTING MODULE's directory, which is cognee's
    # own package inside this venv, and from the working directory only under a REPL, a debugger
    # or a frozen interpreter; both roots are scanned here. The adapter refuses such a file before
    # spawning this process; this is the second half of the same guard, at the point of import.
    roots = (Path(sys.prefix), Path.cwd())
    for root in roots:
        for directory in (root, *root.parents):
            if (directory / ".env").is_file():
                raise SystemExit(
                    f"refusing to run: {directory / '.env'} exists, and cognee loads it with "
                    f"override=True at import, which would beat this arm's frozen configuration."
                )
    for required in ("LLM_PROVIDER", "LLM_MODEL", "EMBEDDING_PROVIDER", "EMBEDDING_MODEL"):
        if not os.environ.get(required):
            raise SystemExit(
                f"{required} is not set. cognee defaults an unset half of this pair to OpenAI "
                f"(and reuses LLM_API_KEY for embeddings), so a partial configuration bills a "
                f"provider nobody chose. The adapter sets all four; this is the backstop."
            )

    asyncio.run(_run(feed, dataset, ceiling, token_ceiling, estimate_only))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
