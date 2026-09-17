"""Deterministic, source-backed graph metadata for AMB corpus renders.

The benchmark must never infer semantic relations from transcript prose.  This module exposes
only structure already present in the corpus layout: adjacent sessions belonging to the same task
are linked in both directions.  The resulting relation targets are the exact Markdown filenames
that ``render_corpus`` writes, so the production graph builder can resolve them without guessing.
"""

from __future__ import annotations

import json
from collections import defaultdict
from itertools import pairwise
from pathlib import Path
from typing import Any

GRAPH_METADATA_MODE = "structural_session_order"


def _rendered_name(path: Path, root: Path) -> str:
    return path.relative_to(root).with_suffix(".md").as_posix().replace("/", "__")


def structural_graph_metadata(
    session_paths: list[Path], root: Path
) -> dict[Path, dict[str, str]]:
    """Return explicit ``recall_graph`` frontmatter for adjacent sessions of each task.

    A relation is emitted only when two files share the same parent directory and are adjacent
    after the corpus renderer's stable path sort.  This is a structural benchmark relation, not a
    claim that either transcript semantically supports the other.  It is intentionally represented
    as ``references`` because that is the production graph's conservative directional vocabulary.
    """

    groups: dict[Path, list[Path]] = defaultdict(list)
    for source in sorted(session_paths):
        groups[source.parent].append(source)

    relations: dict[Path, list[dict[str, Any]]] = defaultdict(list)
    for members in groups.values():
        for left, right in pairwise(members):
            left_name = _rendered_name(left, root)
            right_name = _rendered_name(right, root)
            relations[left].append(
                {
                    "relation": "references",
                    "subject": left_name,
                    "object": right_name,
                    "confidence": 1.0,
                    "structural_type": "session_order",
                }
            )
            relations[right].append(
                {
                    "relation": "references",
                    "subject": right_name,
                    "object": left_name,
                    "confidence": 1.0,
                    "structural_type": "session_order",
                }
            )

    return {
        source: {
            "recall_graph": json.dumps(
                {
                    "schema_version": 1,
                    "relations": sorted(
                        values,
                        key=lambda item: (str(item["object"]), str(item["structural_type"])),
                    ),
                },
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            )
        }
        for source, values in relations.items()
    }


__all__ = ["GRAPH_METADATA_MODE", "structural_graph_metadata"]
