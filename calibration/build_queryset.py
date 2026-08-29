"""Build the labelled query set that calibrates the recall arm's abstention threshold.

## The contamination problem this file exists to solve

Calibration fits a threshold by measuring how well retrieval scores separate answerable queries
from unanswerable ones. Fit it on the benchmark's own tasks and the threshold is tuned to the test
items, which would make endpoint 3 a measurement of its own calibration.

The corpus makes a clean split available for free. Thirty-one task session sets are in the feed and
only **ten** are ever a benchmark subject; the other twenty-one are present in EVERY condition,
because `assemble_condition_corpus` keeps a non-selected task's real session. So a query set drawn
from those is:

* **disjoint from the test items**, since none of those tasks ever runs as a cell;
* **valid across all four conditions**, since the same sessions are in each feed;
* **fitted to this corpus's statistics**, which is the part calibration legitimately needs.

## What the negatives must avoid, and why it is not obvious

A mislabelled negative, a query the corpus can actually answer, depresses separability and lowers
the threshold, which makes the arm answer where it should abstain. So the unanswerable set has to
steer clear of three domains, and the third one is easy to forget:

1. the twenty held-out tasks, which are the positives;
2. the ten planted tasks, whose conventions appear in three of the four condition corpora;
3. the **distractors**, which are 99 files drawn from about eleven repeated housekeeping chores:
   README edits, DATA.md, line counts, `.editorconfig`, CHANGELOG, TODO collection, docstrings,
   typos, trailing whitespace, a getting-started section and a repository overview.

⚠️ `ts-manifest-rel` is used as a positive and is worth naming. It WAS a planted task until its
plant was retired on 2026-08-28 for firing on a memoryless session. It declares no conditions now,
so `selection_for` never selects it and it cannot run as a cell, which makes it held-out in the only
sense that matters here.

Rebuild with:

    python calibration/build_queryset.py
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "calibration" / "abstention-queryset-v1.json"

#: One question per held-out task, phrased the way a developer asks a colleague rather than the way
#: the task prompt is written. The answer lives in that task's recorded session, which is in every
#: condition's feed.
ANSWERABLE: list[tuple[str, str]] = [
    ("ts-atomic-write", "how do we write a file so a crash cannot leave it half written"),
    ("ts-bom-merge", "why do some of our CSV exports start with a stray invisible character"),
    ("ts-casefold-sort", "how are names with accents supposed to sort in our rosters"),
    ("ts-cli-exitcode", "does printing an error count as reporting failure from a CLI here"),
    ("ts-config-layer", "which wins when a setting is in both the config file and the environment"),
    ("ts-crlf-export", "what happened when an export had windows line endings"),
    ("ts-dedup-order", "when we deduplicate events which copy do we keep"),
    ("ts-empty-input", "what should a report do when there is nothing in the inbox that week"),
    ("ts-golden-regen", "are the golden files safe to edit by hand"),
    ("ts-idempotent-run", "what happens if the deploy step runs twice"),
    ("ts-json-sorted", "why do we sort the keys when writing generated json"),
    ("ts-legacy-hash", "is the short fast_hash safe to use as a cache key"),
    ("ts-log-mask", "how much of an auth token may appear in our logs"),
    ("ts-manifest-rel", "should the paths in a generated manifest be absolute or relative"),
    ("ts-mig-name", "is there a length limit on migration file names"),
    ("ts-nfc-count", "why do the same word forms count separately in the glossary"),
    ("ts-quote-shell", "what breaks in the deploy script when a directory has a space in it"),
    ("ts-retry-cap", "how long may a retry backoff grow before it is capped"),
    ("ts-round-money", "how are invoice totals rounded to cents"),
    ("ts-stable-sort", "what do we tiebreak on so a regenerated report does not churn"),
]

#: Deliberately far from every domain the corpus covers. Each is a question a real team would ask
#: and this repository has never discussed: no session, plant or distractor touches any of them.
UNANSWERABLE: list[str] = [
    "what is our kubernetes pod eviction policy",
    "which oauth grant type do our first party clients use",
    "who renews the TLS certificates and how often",
    "what is our DNS failover arrangement between regions",
    "how is the load balancer health check configured",
    "which message broker do we use for asynchronous work",
    "do we expose a graphql endpoint to partners",
    "what percentage of users see a new feature flag first",
    "how does the on call paging rota escalate overnight",
    "how long do we retain personal data before deletion",
    "which container registry do our images come from",
    "how are GPU jobs scheduled and prioritised",
    "what is the release process for the mobile app",
    "how do we decide when an A/B test has finished",
    "what powers the customer facing search index",
    "what is the per customer request rate limit",
    "do we deploy blue green or with a rolling restart",
    "how is the primary database sharded across tenants",
    "what are the connection pool sizes in production",
    "who owns the translation and localisation workflow",
    "what accessibility standard do our interfaces target",
    "which open source licences may we depend on",
    "how are secrets rotated in the staging environment",
    "what is the disaster recovery point objective",
    "how do we bill customers who exceed their plan",
    "what is the policy on running untrusted third party code",
]


def build() -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for index, (task_id, query) in enumerate(ANSWERABLE, start=1):
        entries.append(
            {
                "id": f"a{index:02d}",
                "query": query,
                "answerable": True,
                "source_task": task_id,
            }
        )
    for index, query in enumerate(UNANSWERABLE, start=1):
        entries.append({"id": f"u{index:02d}", "query": query, "answerable": False})
    return entries


def main() -> int:
    entries = build()
    # `relevant_ids` is optional and feeds precision/recall reporting, not the threshold. It is
    # omitted rather than guessed: an id is `<source>:<chunk ordinal>` and the ordinal depends on
    # how the chunker split a session, so a hand-written one would be a plausible-looking lie in a
    # file whose whole purpose is honest labels.
    payload = json.dumps(entries, indent=2, sort_keys=True) + "\n"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(payload, encoding="utf-8", newline="\n")
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    answerable = sum(1 for e in entries if e["answerable"])
    print(f"wrote {OUT.relative_to(REPO)}")
    print(f"  {len(entries)} queries: {answerable} answerable, {len(entries) - answerable} not")
    print(f"  sha256 {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
