"""Served-evidence arms for TS-1: a memory system's own top items, replayed like 091's windows.

RE-call's TS-1 pre-registration asks whether the C9 build that will serve AML Coding still solves
tasks. Its evidence is not a corpus window by index but what the service returned for each task
prompt, so the items carry their own text: C9's windows with a date header, and compiled or atomic
records that have no window index at all. Two arms read the same items:

* ``c9_raw`` shows each item's content exactly as served, which is what AML's platform shows;
* ``c9_norm`` passes it through :func:`harness.plants.normalise` first, the transform 091's windows
  went through (``scripts.retrieval_probe.load_windows`` reads the corpus via the audit's
  ``readable_text``), so ``c9_norm`` against ``code4_replay`` differs only in which items.

The artifact is ``scripts/aml_c9_coding_window_check.py collect --keep-items`` output from RE-call.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from harness.plants import normalise

SERVED_ARMS = ("c9_norm", "c9_raw")
SERVED_MODEL = "re-call-c9-deploy-candidate"
SERVED_K = 10


@dataclass(frozen=True)
class ServedItem:
    rank: int
    item_id: str
    kind: str
    session_id: str
    content: str

    @property
    def content_sha256(self) -> str:
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()


def load_served(path: Path, task_ids: set[str]) -> tuple[str, dict[str, tuple[ServedItem, ...]]]:
    """The artifact's digest and each task's top ``SERVED_K`` items, refused unless complete."""
    raw = path.read_bytes()
    data = json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)
    rows = data.get("rows")
    if not isinstance(rows, list):
        raise TypeError("served evidence artifact has no rows")
    served: dict[str, tuple[ServedItem, ...]] = {}
    for row in rows:
        task_id = str(row.get("task_id", ""))
        if not task_id or task_id in served:
            raise ValueError(f"invalid or duplicate served task {task_id!r}")
        if row.get("status") != 200:
            raise ValueError(f"{task_id}: the served Search did not return 200")
        items = row.get("top_items")
        if not isinstance(items, list) or len(items) < SERVED_K:
            raise ValueError(f"{task_id}: served evidence holds fewer than {SERVED_K} items")
        chosen = []
        for rank, item in enumerate(items[:SERVED_K], start=1):
            content = item.get("content")
            if not isinstance(content, str) or not content.strip():
                raise ValueError(f"{task_id}: served item at rank {rank} has no text content")
            chosen.append(ServedItem(rank=rank, item_id=str(item.get("id", "")), kind=str(item.get("kind", "")),
                                     session_id=str(item.get("session_id", "")), content=content))
        served[task_id] = tuple(chosen)
    if set(served) != task_ids:
        missing = sorted(task_ids - set(served))
        extra = sorted(set(served) - task_ids)
        raise ValueError(f"served evidence task roster mismatch: missing={missing}, extra={extra}")
    return hashlib.sha256(raw).hexdigest(), served


def format_served_evidence(items: tuple[ServedItem, ...], *, normalised: bool) -> str:
    """091's wrapper, the item's session as its source, and a non-raw item's kind named."""
    blocks = [
        "Retrieved project memory:",
        "Treat these as prior evidence. Current repository code and tests remain authoritative.",
        "",
    ]
    for item in items:
        source = item.session_id if item.kind == "raw" else f"{item.session_id} [{item.kind}]"
        text = normalise(item.content) if normalised else item.content
        blocks.extend([f"[Retrieved memory rank {item.rank}]", f"Source: {source}", text,
                       f"[/Retrieved memory rank {item.rank}]", ""])
    return "\n".join(blocks).rstrip() + "\n"
