"""Idempotently finish a Graphiti condition feed through graphiti-core.

This is an operational recovery helper for the VPS2 Graphiti queue stall. It uses the same
Graphiti client, model, embedder, database, episode text, and typed extraction configuration as
the official MCP server, but calls ``Graphiti.add_episode`` directly so an already completed
episode can be skipped and a stalled queue cannot force a whole-condition replay.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from pydantic import create_model

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from harness.adapters.base import CorpusManifest
from harness.transcripts import render_transcript

GRAPHITI_SRC = Path("$HOME/graphiti/mcp_server/src")


async def _episode_names(client, namespace: str) -> set[str]:
    """Return the completed episode names for one namespace."""

    # graphiti-core treats a supplied group_id as the FalkorDB graph/database name.
    # The server starts on the shared base graph, so the preflight lookup must use
    # the condition graph explicitly before the first add_episode mutates the client
    # driver to that graph.
    driver = client.driver.clone(database=namespace)

    query = (
        "MATCH (n:Episodic) "
        f"WHERE n.group_id = '{namespace}' "
        "RETURN n.name"
    )
    names: set[str] = set()
    rows, _header, _metadata = await driver.execute_query(query)
    for record in rows:
        name = record.get("n.name")
        if isinstance(name, str):
            names.add(name)
    return names


def _recovery_entity_types(entity_types: dict[str, type]) -> dict[str, type]:
    """Keep provider nulls from aborting an otherwise valid recovery episode.

    OpenRouter can return a JSON null for optional document metadata even when the
    requested schema declares a string.  Graphiti-core validates the merged result
    again and aborts the whole episode.  Only the recovery copy is relaxed, so the
    upstream server and benchmark scoring path remain unchanged.
    """

    document_type = entity_types.get("Document")
    if document_type is None:
        return entity_types
    tolerant_document = create_model(
        "DocumentRecovery",
        __base__=document_type,
        description=(str | None, None),
    )
    return {**entity_types, "Document": tolerant_document}


async def _run(args: argparse.Namespace) -> int:
    if not GRAPHITI_SRC.is_dir():
        raise RuntimeError(f"Graphiti source checkout is missing: {GRAPHITI_SRC}")
    sys.path.insert(0, str(GRAPHITI_SRC))

    import graphiti_mcp_server as server
    from graphiti_core.nodes import EpisodeType

    corpus_root = Path(args.corpus_root).resolve()
    corpus = CorpusManifest.load(corpus_root)
    corpus.verify()
    if not corpus.sessions:
        raise RuntimeError(f"the verified corpus is empty: {corpus_root}")

    # Reuse the upstream server's configuration and factories, including its custom entity and
    # edge types. initialize_server also initializes the same FalkorDB driver used by MCP.
    os.environ["CONFIG_PATH"] = str(args.config)
    # The benchmark keeps Graphiti settings namespaced, while graphiti-core's settings source
    # reads these upstream names directly when it is initialized in-process.
    if os.environ.get("GRAPHITI_FALKORDB_URI"):
        os.environ["FALKORDB_URI"] = os.environ["GRAPHITI_FALKORDB_URI"]
    if os.environ.get("GRAPHITI_FALKORDB_DATABASE"):
        os.environ["FALKORDB_DATABASE"] = os.environ["GRAPHITI_FALKORDB_DATABASE"]
    sys.argv = [
        "recover_graphiti_condition",
        "--config",
        str(args.config),
        "--transport",
        "stdio",
        "--llm-provider",
        os.environ.get("GRAPHITI_LLM_PROVIDER", "openai"),
        "--model",
        os.environ.get("GRAPHITI_MODEL_NAME", "gpt-5.5"),
        "--embedder-provider",
        os.environ.get("GRAPHITI_EMBEDDER_PROVIDER", "openai"),
        "--embedder-model",
        os.environ.get("GRAPHITI_EMBEDDER_MODEL", "text-embedding-3-small"),
        "--database-provider",
        os.environ.get("GRAPHITI_DATABASE_PROVIDER", "falkordb"),
        "--group-id",
        args.namespace,
    ]
    await server.initialize_server()
    service = server.graphiti_service
    if service is None:
        raise RuntimeError("Graphiti service did not initialize")
    client = await service.get_client()
    entity_types = _recovery_entity_types(service.entity_types)

    existing = await _episode_names(client, args.namespace)
    pending = [name for name in sorted(corpus.sessions) if name not in existing]
    print(
        f"[recovery] {args.namespace}: {len(existing)}/{len(corpus.sessions)} episodes already "
        f"complete; {len(pending)} pending",
        flush=True,
    )

    for index, rel_path in enumerate(pending, start=1):
        source = corpus.root / rel_path
        for attempt in range(1, 4):
            try:
                await client.add_episode(
                    name=rel_path,
                    episode_body=render_transcript(source),
                    source_description=f"agent-memory-bench transcript {rel_path}",
                    source=EpisodeType.text,
                    group_id=args.namespace,
                    reference_time=datetime.now(timezone.utc),
                    entity_types=entity_types,
                    edge_types=service.edge_types,
                    edge_type_map=service.edge_type_map,
                )
                break
            except Exception as exc:
                if attempt == 3:
                    raise
                print(
                    f"[recovery] {args.namespace}: retrying {rel_path} after "
                    f"attempt {attempt} failed with {type(exc).__name__}",
                    flush=True,
                )
                await asyncio.sleep(attempt * 2)
        print(f"[recovery] {args.namespace}: added {index}/{len(pending)} {rel_path}", flush=True)

    final_names = await _episode_names(client, args.namespace)
    if len(final_names) < len(corpus.sessions):
        raise RuntimeError(
            f"{args.namespace}: recovery ended with {len(final_names)}/{len(corpus.sessions)} "
            "episodes"
        )
    print(
        f"[recovery] {args.namespace}: verified {len(final_names)}/{len(corpus.sessions)} episodes",
        flush=True,
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus-root", required=True)
    parser.add_argument("--namespace", required=True)
    parser.add_argument(
        "--config",
        default="$HOME/graphiti/mcp_server/config/config.yaml",
    )
    return asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
