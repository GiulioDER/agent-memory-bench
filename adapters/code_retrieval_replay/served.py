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

TS-1 amendment A1 adds two arms read from a SECOND collect, served with LW-1 on (each retrieved
session's last window appended after the top 10):

* ``c9_raw2`` shows that collect's top 10 exactly as ``c9_raw`` shows its own;
* ``c9_lw`` shows the same top 10 and then the appended windows, so the two differ only in those.

The service does not say how many windows it appended, so the arm takes that from a manifest
written by the collect's apparatus check, which recomputed LW-1 from the corpus and found the
served items at ranks 11 onward equal to it. The manifest names the collect it describes by
digest, and every listed id must be the served item at its rank, or nothing loads.

RE-call's CD-1 Stage 1 (pre-registered 2026-09-27) adds two arms read from a CD-1 Stage 0 collect,
which kept all 100 served items and each task's top-1 dense cosine. Its rule G(0.25) returns only
the top 10 when that cosine is below 0.25, so:

* ``cd1_full`` shows the 100 items in served order, rendered exactly as ``c9_raw`` renders;
* ``cd1_gated`` shows the first 10 of them.

Only the tasks G gates run: on every other task the two arms' input is identical by construction.
The collect is bound by its full digest and its own arm label, and the gated set recomputed from it
must equal the one the pre-registration lists, or nothing loads.
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
LW_ARMS = ("c9_raw2", "c9_lw")
LW_MODEL = "re-call-c9-last-window"
LW_MANIFEST_SCHEMA = "ts1-a1-last-windows-v1"
CD1_ARMS = ("cd1_full", "cd1_gated")
CD1_MODEL = "re-call-c9-cd1-g025"
CD1_ITEMS = 100
CD1_TAU = 0.25


@dataclass(frozen=True)
class Cd1Collect:
    """One CD-1 Stage 0 collect as the pre-registration fixed it: file digest, arm label, gated set."""

    sha256: str
    arm: str
    gated: frozenset[str]


#: RE-call recall-lab ``research/preregistrations/2026-09-27-cd1-coding-return-size-stage1.md``; the
#: digests as corrected in the Stage 0 record the same evening (its prefixes were swapped).
CD1_REGISTERED = {
    "present": Cd1Collect(
        sha256="c5dde73e17b799f3412eaf9fb9f16c4fd83236a4667d302a2c466ff0b8d2c95d",
        arm="CD1P",
        gated=frozenset({"ts-ignore-gen", "ts-natural-order", "ts-nfc-count", "ts-quote-shell",
                         "ts-semver-pin", "xs-join-batch"}),
    ),
    "absent": Cd1Collect(
        sha256="f463677024753e6f14577dc09bf8aacdcf8abd9e99bf55527a08fff12fd2e4d6",
        arm="CD1A",
        gated=frozenset({"ts-dedup-order", "ts-ignore-gen", "ts-mig-name", "ts-natural-order",
                         "ts-nfc-count", "ts-quote-shell", "ts-semver-pin", "xs-join-batch"}),
    ),
}


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


@dataclass(frozen=True)
class LastWindowEvidence:
    """One task's LW-1 collect: its top ``SERVED_K`` and the windows LW-1 appended after them."""

    top: tuple[ServedItem, ...]
    appended: tuple[ServedItem, ...]


def _served_item(task_id: str, rank: int, item: dict) -> ServedItem:
    content = item.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError(f"{task_id}: served item at rank {rank} has no text content")
    return ServedItem(rank=rank, item_id=str(item.get("id", "")), kind=str(item.get("kind", "")),
                      session_id=str(item.get("session_id", "")), content=content)


def _served_rows(path: Path, task_ids: set[str]) -> tuple[str, dict[str, list[dict]]]:
    """The artifact's digest and each task's served items, refused unless every task has ``SERVED_K``."""
    raw = path.read_bytes()
    data = json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)
    rows = data.get("rows")
    if not isinstance(rows, list):
        raise TypeError("served evidence artifact has no rows")
    served: dict[str, list[dict]] = {}
    for row in rows:
        task_id = str(row.get("task_id", ""))
        if not task_id or task_id in served:
            raise ValueError(f"invalid or duplicate served task {task_id!r}")
        if row.get("status") != 200:
            raise ValueError(f"{task_id}: the served Search did not return 200")
        items = row.get("top_items")
        if not isinstance(items, list) or len(items) < SERVED_K:
            raise ValueError(f"{task_id}: served evidence holds fewer than {SERVED_K} items")
        served[task_id] = items
    if set(served) != task_ids:
        missing = sorted(task_ids - set(served))
        extra = sorted(set(served) - task_ids)
        raise ValueError(f"served evidence task roster mismatch: missing={missing}, extra={extra}")
    return hashlib.sha256(raw).hexdigest(), served


def load_served(path: Path, task_ids: set[str]) -> tuple[str, dict[str, tuple[ServedItem, ...]]]:
    """The artifact's digest and each task's top ``SERVED_K`` items, refused unless complete."""
    digest, rows = _served_rows(path, task_ids)
    return digest, {
        task_id: tuple(_served_item(task_id, rank, item) for rank, item in enumerate(items[:SERVED_K], start=1))
        for task_id, items in rows.items()
    }


def load_last_window_served(
    path: Path, manifest_path: Path, task_ids: set[str]
) -> tuple[str, str, dict[str, LastWindowEvidence]]:
    """The LW-1 collect's digest, its manifest's digest, and each task's top 10 and appended windows.

    Refused unless the manifest names this collect by digest, covers exactly the tasks, and every id
    it lists is the served item at ranks 11 onward, in order.
    """
    digest, rows = _served_rows(path, task_ids)
    manifest_raw = manifest_path.read_bytes()
    manifest = json.loads(manifest_raw)
    if manifest.get("schema") != LW_MANIFEST_SCHEMA:
        raise ValueError(f"last-window manifest must use schema {LW_MANIFEST_SCHEMA!r}")
    if manifest.get("served_sha256") != digest:
        raise ValueError("last-window manifest does not describe this served artifact")
    appended_ids = manifest.get("tasks")
    if not isinstance(appended_ids, dict) or set(appended_ids) != task_ids:
        raise ValueError("last-window manifest task roster does not match the tasks")
    evidence: dict[str, LastWindowEvidence] = {}
    for task_id, items in rows.items():
        wanted = appended_ids[task_id]
        if not isinstance(wanted, list) or not all(isinstance(item_id, str) for item_id in wanted):
            raise TypeError(f"{task_id}: last-window manifest entry is not a list of ids")
        tail = items[SERVED_K:SERVED_K + len(wanted)]
        if [str(item.get("id", "")) for item in tail] != wanted:
            raise ValueError(f"{task_id}: served items after rank {SERVED_K} are not the manifest's last windows")
        ranked = [_served_item(task_id, rank, item) for rank, item in enumerate(items[:SERVED_K + len(wanted)], start=1)]
        evidence[task_id] = LastWindowEvidence(top=tuple(ranked[:SERVED_K]), appended=tuple(ranked[SERVED_K:]))
    return digest, hashlib.sha256(manifest_raw).hexdigest(), evidence


def load_cd1(
    path: Path,
    condition: str,
    task_ids: set[str],
    registered: dict[str, Cd1Collect] | None = None,
) -> tuple[str, frozenset[str], dict[str, tuple[ServedItem, ...]]]:
    """A CD-1 collect's digest, its gated tasks, and each task's 100 served items in order.

    Refused unless the file is the registered collect for ``condition`` (digest and arm label),
    every task holds exactly ``CD1_ITEMS`` items and a top-1 cosine, and the tasks whose top-1 is
    below ``CD1_TAU`` are exactly the registered gated set.
    """
    registered = CD1_REGISTERED if registered is None else registered
    if condition not in registered:
        raise ValueError(f"unknown CD-1 condition {condition!r}; expected one of {sorted(registered)}")
    expected = registered[condition]
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected.sha256:
        raise ValueError(f"CD-1 {condition} collect digest {digest[:16]} is not the registered one")
    data = json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)
    if data.get("arm") != expected.arm:
        raise ValueError(f"CD-1 {condition} collect is arm {data.get('arm')!r}, not {expected.arm!r}")
    _, rows = _served_rows(path, task_ids)
    top1 = {str(row["task_id"]): row.get("dense_top1") for row in data["rows"]}
    evidence: dict[str, tuple[ServedItem, ...]] = {}
    for task_id, items in rows.items():
        if len(items) != CD1_ITEMS:
            raise ValueError(f"{task_id}: CD-1 collect holds {len(items)} items, not {CD1_ITEMS}")
        if not isinstance(top1.get(task_id), (int, float)):
            raise TypeError(f"{task_id}: CD-1 collect has no top-1 dense cosine")
        evidence[task_id] = tuple(_served_item(task_id, rank, item) for rank, item in enumerate(items, start=1))
    gated = frozenset(task_id for task_id, value in top1.items() if task_id in rows and value < CD1_TAU)
    if gated != expected.gated:
        raise ValueError(
            f"CD-1 {condition} gated set differs from the registered one: "
            f"extra={sorted(gated - expected.gated)}, missing={sorted(expected.gated - gated)}"
        )
    return digest, gated, evidence


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
