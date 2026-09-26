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
from uuid import NAMESPACE_OID, uuid5


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


def _configured_data_per_batch() -> int:
    """Return the bounded Cognify item concurrency for this hosted ingest."""

    try:
        data_per_batch = int(os.environ.get("AMB_COGNEE_DATA_PER_BATCH", "20"))
    except ValueError as error:
        raise SystemExit("AMB_COGNEE_DATA_PER_BATCH must be an integer") from error
    if data_per_batch < 1:
        raise SystemExit("AMB_COGNEE_DATA_PER_BATCH must be >= 1")
    return data_per_batch


def _configured_chunks_per_batch() -> int:
    """Return the chunk batch size used by the optional bulk standard pipeline."""

    try:
        chunks_per_batch = int(os.environ.get("AMB_COGNEE_CHUNKS_PER_BATCH", "2000"))
    except ValueError as error:
        raise SystemExit("AMB_COGNEE_CHUNKS_PER_BATCH must be an integer") from error
    if chunks_per_batch < 1:
        raise SystemExit("AMB_COGNEE_CHUNKS_PER_BATCH must be >= 1")
    return chunks_per_batch


def _configured_documents_per_batch() -> int:
    """Return the maximum number of source documents submitted to one task stream."""

    try:
        documents_per_batch = int(os.environ.get("AMB_COGNEE_DOCUMENTS_PER_BATCH", "128"))
    except ValueError as error:
        raise SystemExit("AMB_COGNEE_DOCUMENTS_PER_BATCH must be an integer") from error
    if documents_per_batch < 1:
        raise SystemExit("AMB_COGNEE_DOCUMENTS_PER_BATCH must be >= 1")
    return documents_per_batch


async def _run_bulk_standard_pipeline(
    dataset_name: str,
    chunks_per_batch: int,
    documents_per_batch: int,
    source_names: set[str],
) -> int:
    """Run Cognee's standard tasks over bounded windows of unfinished data.

    The public ``cognify`` API intentionally schedules every data item independently. With a
    local Ladybug/Kuzu backend that turns a 4,704-document corpus into thousands of tiny native
    write transactions. The task implementations themselves accept lists, so this path keeps
    the same classification, chunking, graph extraction, summarization, and storage tasks while
    allowing their existing batch-size boundary to span documents. The outer window is bounded
    too, so classification cannot materialize the whole corpus in memory before doing useful work.

    ``ctx`` is intentionally omitted. The stock per-item runner uses it to stamp the first
    document's content hash onto every DataPoint in a cross-document batch. Provenance tracking is
    disabled for this arm, and omitting the context avoids manufacturing incorrect provenance.
    """

    from sqlalchemy import select

    from cognee.api.v1.cognify.cognify import get_default_tasks
    from cognee.modules.data.methods.get_dataset_ids import get_dataset_ids
    from cognee.infrastructure.databases.relational import get_relational_engine
    from cognee.modules.data.models import Data
    from cognee.modules.pipelines.models.DataItemStatus import DataItemStatus
    from cognee.modules.pipelines.operations.run_tasks_base import run_tasks_base
    from cognee.modules.pipelines.utils import generate_pipeline_id
    from cognee.modules.users.methods import get_default_user

    user = await get_default_user()
    dataset_ids = await get_dataset_ids([dataset_name], user)
    if len(dataset_ids) != 1:
        raise SystemExit(f"expected exactly one dataset named {dataset_name!r}")
    dataset_id = dataset_ids[0]
    from cognee.modules.data.methods.get_dataset import get_dataset

    dataset = await get_dataset(user.id, dataset_id)
    if dataset is None:
        raise SystemExit(f"dataset {dataset_name!r} was not found for the default user")

    pipeline_id = generate_pipeline_id(user.id, dataset.id, "cognify_pipeline")
    pipeline_key = str(pipeline_id)
    db_engine = get_relational_engine()
    completed = 0
    offset = 0
    while True:
        async with db_engine.get_async_session() as session:
            result = await session.execute(
                select(Data)
                .where(Data.dataset_id == dataset.id, Data.name.in_(source_names))
                .order_by(Data.id)
                .offset(offset)
                .limit(documents_per_batch)
            )
            page = result.scalars().all()
        if not page:
            break
        offset += len(page)
        batch = [
            item
            for item in page
            if item.pipeline_status.get("cognify_pipeline", {}).get(pipeline_key)
            != DataItemStatus.DATA_ITEM_PROCESSING_COMPLETED
        ]
        if not batch:
            continue

        tasks = await get_default_tasks(
            user=user,
            chunks_per_batch=chunks_per_batch,
        )
        async for _ in run_tasks_base(tasks, batch, user, None):
            pass

        async with db_engine.get_async_session() as session:
            result = await session.execute(select(Data).where(Data.id.in_([item.id for item in batch])))
            for item in result.scalars().all():
                status = dict(item.pipeline_status or {})
                cognify_status = dict(status.get("cognify_pipeline", {}))
                cognify_status[pipeline_key] = DataItemStatus.DATA_ITEM_PROCESSING_COMPLETED
                status["cognify_pipeline"] = cognify_status
                item.pipeline_status = status
                session.add(item)
            await session.commit()
        completed += len(batch)

    return completed


def _configure_local_backend_limits() -> dict[str, int]:
    """Avoid oversubscribing the local graph and vector backends.

    Cognee's local Kuzu default uses one thread per CPU.  The pipeline also runs many data-item
    tasks concurrently, so leaving that default in place multiplies native worker threads and
    makes the single local graph store the bottleneck.  These are safe defaults, while explicit
    environment values remain authoritative for a deliberate tuning run.
    """

    try:
        kuzu_threads = int(os.environ.get("KUZU_NUM_THREADS", "1"))
        embedding_points = int(
            os.environ.get("EMBEDDING_MAX_CONCURRENT_DATA_POINTS", "32")
        )
    except ValueError as error:
        raise SystemExit(
            "KUZU_NUM_THREADS and EMBEDDING_MAX_CONCURRENT_DATA_POINTS must be integers"
        ) from error
    if kuzu_threads < 1 or embedding_points < 1:
        raise SystemExit(
            "KUZU_NUM_THREADS and EMBEDDING_MAX_CONCURRENT_DATA_POINTS must be >= 1"
        )
    os.environ.setdefault("KUZU_NUM_THREADS", str(kuzu_threads))
    os.environ.setdefault(
        "EMBEDDING_MAX_CONCURRENT_DATA_POINTS", str(embedding_points)
    )
    for variable in (
        "OMP_NUM_THREADS",
        "MKL_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "ORT_INTRA_OP_NUM_THREADS",
        "ORT_INTER_OP_NUM_THREADS",
    ):
        os.environ.setdefault(variable, "1")
    return {
        "kuzu_num_threads": kuzu_threads,
        "embedding_max_concurrent_data_points": embedding_points,
    }


def _configure_fastembed_cache() -> str:
    """Put FastEmbed's model cache in a writable namespace-owned directory."""

    configured = os.environ.get("FASTEMBED_CACHE_PATH", "").strip()
    if configured:
        cache = Path(configured)
    else:
        data_root = os.environ.get("DATA_ROOT_DIRECTORY")
        if not data_root:
            raise SystemExit("DATA_ROOT_DIRECTORY is required to place the FastEmbed cache")
        cache = Path(data_root).parent / "fastembed-cache"
        os.environ["FASTEMBED_CACHE_PATH"] = str(cache)
    try:
        cache.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise SystemExit(f"cannot create FastEmbed cache directory {cache}: {error}") from error

    cached_model = (
        cache
        / "models--qdrant--bge-small-en-v1.5-onnx-q"
        / "snapshots"
        / "52398278842ec682c6f32300af41344b1c0b0bb2"
        / "model_optimized.onnx"
    )
    if cached_model.is_file() and cached_model.stat().st_size > 1_000_000:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
    return str(cache)


def _configure_request_timeout() -> int:
    """Ensure every provider request has a finite timeout."""

    try:
        timeout_seconds = int(
            os.environ.get("AMB_COGNEE_LLM_REQUEST_TIMEOUT_SECONDS", "120")
        )
    except ValueError as error:
        raise SystemExit("AMB_COGNEE_LLM_REQUEST_TIMEOUT_SECONDS must be an integer") from error
    if timeout_seconds < 1:
        raise SystemExit("AMB_COGNEE_LLM_REQUEST_TIMEOUT_SECONDS must be >= 1")

    raw_args = os.environ.get("LLM_ARGS", "").strip()
    if raw_args:
        try:
            llm_args = json.loads(raw_args)
        except json.JSONDecodeError as error:
            raise SystemExit("LLM_ARGS must contain a JSON object") from error
        if not isinstance(llm_args, dict):
            raise SystemExit("LLM_ARGS must contain a JSON object")
    else:
        llm_args = {}
    llm_args.setdefault("timeout", timeout_seconds)
    os.environ["LLM_ARGS"] = json.dumps(llm_args)
    return int(llm_args["timeout"])


def _configure_tolerant_summaries() -> dict[str, object]:
    """Keep one malformed summary response from aborting the whole cognify run.

    Cognee runs graph extraction and chunk summarization together.  A validation failure in the
    optional summary branch currently propagates through ``asyncio.gather`` and fails every
    remaining data item.  For this benchmark, retain the chunk as a deterministic fallback only
    for JSON/schema validation errors, and count each fallback in the final report.  Transport,
    quota, and provider errors remain fatal.
    """

    from json import JSONDecodeError

    from pydantic import ValidationError

    import importlib

    graph_task_module = importlib.import_module(
        "cognee.tasks.graph.extract_graph_and_summarize"
    )
    from cognee.infrastructure.llm.extraction import extract_summary
    from cognee.modules.cognify.config import get_cognify_config
    from cognee.tasks.summarization.models import TextSummary

    fallback_count = 0
    original_summarize_text = graph_task_module.summarize_text

    async def summarize_text_tolerant(data_chunks, summarization_model=None):
        nonlocal fallback_count
        if summarization_model is None:
            summarization_model = get_cognify_config().summarization_model

        async def summarize_one(chunk):
            nonlocal fallback_count
            try:
                result = await extract_summary(chunk.text, summarization_model)
                summary_text = result.summary
            except (ValidationError, JSONDecodeError) as error:
                fallback_count += 1
                print(
                    "COGNEE_SUMMARY_FALLBACK "
                    + json.dumps(
                        {
                            "chunk_id": str(chunk.id),
                            "error": type(error).__name__,
                        }
                    ),
                    flush=True,
                )
                summary_text = chunk.text

            return TextSummary(
                id=uuid5(chunk.id, "TextSummary"),
                made_from=chunk,
                source_chunk_id=str(chunk.id),
                belongs_to_set=chunk.belongs_to_set,
                text=summary_text,
                importance_weight=chunk.importance_weight,
            )

        return await asyncio.gather(*(summarize_one(chunk) for chunk in data_chunks))

    graph_task_module.summarize_text = summarize_text_tolerant
    return {
        "enabled": True,
        "fallbacks": lambda: fallback_count,
        "original": getattr(original_summarize_text, "__name__", "summarize_text"),
    }


async def _run(
    feed: Path, dataset: str, ceiling: float, token_ceiling: int, estimate_only: bool
) -> dict:
    request_timeout = _configure_request_timeout()
    backend_limits = _configure_local_backend_limits()
    fastembed_cache = _configure_fastembed_cache()
    import cognee
    from cognee.modules.search.types import SearchType

    retry_policy = _configure_bounded_retries()
    data_per_batch = _configured_data_per_batch()
    chunks_per_batch = _configured_chunks_per_batch()
    documents_per_batch = _configured_documents_per_batch()
    summary_policy = _configure_tolerant_summaries()
    bulk_pipeline = os.environ.get("AMB_COGNEE_BULK_PIPELINE", "true").lower() not in {
        "0",
        "false",
        "no",
        "off",
    }

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
        "execution_mode": "bulk_standard_tasks" if bulk_pipeline else "cognee_cognify",
        "data_per_batch": data_per_batch,
        "chunks_per_batch": chunks_per_batch,
        "documents_per_batch": documents_per_batch,
        **backend_limits,
        "fastembed_cache": fastembed_cache,
        "request_timeout_seconds": request_timeout,
        "summary_policy": {
            "enabled": summary_policy["enabled"],
            "fallbacks": 0,
        },
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

    if bulk_pipeline:
        report["bulk_items"] = await _run_bulk_standard_pipeline(
            dataset_name=dataset,
            chunks_per_batch=chunks_per_batch,
            documents_per_batch=documents_per_batch,
            source_names={path.stem for path in files},
        )
    else:
        await cognee.cognify(datasets=[dataset], data_per_batch=data_per_batch)
    report["cognified"] = True
    report["summary_policy"]["fallbacks"] = summary_policy["fallbacks"]()

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
