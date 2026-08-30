"""Report how findable each planted memo is. Ranks candidates; authorises nothing.

    python -m scripts.audit_findability
    python -m scripts.audit_findability --condition adjacent

No model, no network, no spend. Reads the assembled condition corpora and asks, for each task, at
what rank a BM25 ranker puts that task's planted session when queried with the task's own prompt.

## Why this exists

Every other gate here checks a plant is CORRECT. `audit_plants` checks it leaks no true fact and
that its wrong terms survive recording; `test_damage_detection` checks its signature fires on the
plant and stays silent on a factless session. **None of them checks that anything RETRIEVES it.**

A plant nothing retrieves cannot mislead anybody. Its condition then measures nothing for that
task while every gate stays green, which is the quietest way for a cell to become decorative.

## ⚠️ Why this is a REPORT and not a gate, which is the finding that built it

Two independent BM25 implementations were run over the same corpus and disagreed by up to 51 rank
positions, on exactly the plants a gate would act on:

    task               probe A   probe B
    ts-ignore-gen            1         1
    ts-schema-additive       4         4
    ts-tz-utc                4         8
    ts-bom-merge            32        15
    ts-dedup-order          59        17
    ts-glob-hidden          45         1
    ts-golden-regen         61        10

🔁 **Updated 2026-08-30: that disagreement is RESOLVED, and knowing why strengthens the case for
a report rather than weakening it.** The two implementations were merged under finding F-24, so
there is one BM25 now (`harness.retrieval.Bm25Index`) and this file uses it. The 51 positions were
not mysterious variance between equally good rankers: probe B differed in `k1`, in the tokenizer,
in carrying no stoplist, in windowing at a different stride over a different text, and in scoring
`set(tokenize(query))`. That last one is a defect rather than a parameter, and it alone moves
hit@1 by 0.147 over 4,900 documents.

**So the original evidence for "do not gate" is gone, and the conclusion still stands on a better
reason.** One ranker cannot disagree with itself, but a term ranker is a PROXY for what the
products under test actually do, and they retrieve with embeddings. `docs/RETRIEVAL_DIFFICULTY.md`
measures BM25 and voyage-4 failing on different corpora: volume is a lever for the embedder and
none for the term ranker. A gate built on this number would act on a signal the thing it guards
does not use. The table above is kept because it is evidence of what was believed and why, not
because either column is still produced.

They agree on the head and diverge on the tail. Windowing the documents (160 words, as probe A
does) closed most of the head gap and none of the tail. Neither is ground truth: the products
under test retrieve with embeddings, not BM25, so this whole measurement is a proxy for the thing
that matters.

**A hard threshold on a number two implementations cannot agree on would fail builds arbitrarily.**
So this prints a ranking and names its retriever, and a human decides. That is the same conclusion
`scripts/task_admission.py` reached about retirement, for the same reason.

Two cheaper proxies were tried before BM25 and both failed outright; the reasoning is in
`harness/retrieval.py`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from harness.plants import load_plants
from harness.retrieval import WINDOW_WORDS, Bm25Index, read_corpus
from harness.tasks import discover_tasks

CONDITIONS = ("absent", "superseded", "contradictory", "adjacent")

#: The rank past which a plant is reported as a candidate for review. Not a pass mark: it is the
#: depth beyond which the two probes stopped agreeing, so it is the point where the measurement
#: itself becomes unreliable rather than the point where a plant becomes bad.
CANDIDATE_DEPTH = 10

#: Windowing now lives in `harness.retrieval`, with the size and stride this file used to define
#: privately. ⚠️ It did NOT match the retrieval probe's, though the comment here said it did: this
#: file strode 160 (non-overlapping) over the TOKENIZED text while the probe strode 120
#: (overlapping) over the RAW text, so a "160-word window" meant two different spans and the two
#: numbers were never comparable. Found while merging the two BM25s on 2026-08-30 (F-24).


def rank_plants(condition: str) -> tuple[list[tuple[str, int | None, int]], list[str]]:
    """`(rows, skipped)`: a rank per task that HAS something placed here, plus those that do not.

    A task appears in `skipped` when its plan for this condition places nothing at all
    (`include_real=False` with no plants), which is the whole of the `absent` condition. Those are
    not findable and are not supposed to be.
    """

    skipped: list[str] = []
    root = REPO / "corpus" / "conditions" / condition / "seed-1"
    if not root.is_dir():
        return [], skipped
    documents = read_corpus(root)
    if not documents:
        return [], skipped
    index = Bm25Index(documents, window_words=WINDOW_WORDS)

    rows = []
    for task in discover_tasks():
        spec = load_plants(task.path)
        plan = spec.plan(condition) if spec is not None else None
        if plan is None:
            continue
        # ⚠️ Nothing is placed for this task in this condition, by design: `absent` sets
        # include_real=False with no plants, because ABSENCE is what it measures. Asking at what
        # rank a ranker finds the thing that was deliberately not put there produced 12 of the 16
        # candidates this tool reported, and a report that is three-quarters false alarm is one a
        # reader stops believing. Counted separately so the omission is visible, not silent.
        if not plan.include_real and not plan.plants:
            skipped.append(task.task_id)
            continue
        prefix = f"sessions/{task.task_id}/"
        if not any(name.startswith(prefix) for name in documents):
            rows.append((task.task_id, None, len(documents)))
            continue
        # `ranking` speaks DOCUMENTS now, windowed or not, so the fold that used to live here
        # is inside the index and cannot be got wrong twice.
        rank = next(
            (
                i
                for i, (doc, _s) in enumerate(index.ranking(task.prompt), 1)
                if doc.startswith(prefix)
            ),
            None,
        )
        rows.append((task.task_id, rank, len(documents)))
    return rows, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--condition", default="", help="one condition, default every assembled")
    parser.add_argument("--json", dest="as_json", action="store_true")
    args = parser.parse_args()

    wanted = [args.condition] if args.condition else list(CONDITIONS)
    report: dict[str, list[dict]] = {}
    candidates: list[tuple[str, str, int | None]] = []

    for condition in wanted:
        rows, skipped = rank_plants(condition)
        if skipped and not args.as_json:
            print(
                f"\n  {condition}: {len(skipped)} task(s) place nothing here by design, so "
                f"findability does not apply to them"
            )
        if not rows:
            continue
        report[condition] = [
            {"task": t, "rank": r, "corpus": n} for t, r, n in rows
        ]
        if not args.as_json:
            print(f"\n  {condition}  ({rows[0][2]} documents, BM25 over {WINDOW_WORDS}-word windows)")
            for task_id, rank, _n in sorted(rows, key=lambda r: (r[1] is None, r[1] or 0)):
                shown = str(rank) if rank else "not present"
                flag = "  <-- candidate" if rank is None or rank > CANDIDATE_DEPTH else ""
                print(f"    {task_id:24}{shown:>12}{flag}")
        for task_id, rank, _n in rows:
            if rank is None or rank > CANDIDATE_DEPTH:
                candidates.append((condition, task_id, rank))

    if args.as_json:
        print(json.dumps(report, indent=2))
        return 0

    print()
    print("  retriever: BM25, fixed k1=1.5 b=0.75, 160-word windows at stride 120, stopwords in")
    print("             harness.retrieval.STOPWORDS. The products under test retrieve with")
    print("             embeddings, so this is a PROXY for what they would find.")
    print("             It indexes the RAW file text, JSONL envelope included, not the decoded")
    print("             message content. Measured 2026-08-30 against a second implementation:")
    print("             that reading choice moves ranks more than k1, the stopword list, the")
    print("             token pattern and the stride combined, so it is the first thing to")
    print("             check when two probes disagree.")
    print("             Document frequency is counted per WINDOW rather than per document")
    print("             (853 windows over 205 documents in `contradictory`). Substituting")
    print("             document-level df moves 15 of 46 rows and one across the candidate")
    print("             depth. It is left as it is because no true DIRECTION for that bias")
    print("             could be measured: corr(plant length, rank shift) is +0.04 / -0.36 /")
    print("             -0.07 across the three conditions.")
    if candidates:
        print()
        print(f"  {len(candidates)} candidate(s) ranked past {CANDIDATE_DEPTH} or absent:")
        for condition, task_id, rank in candidates:
            print(f"    {condition:14} {task_id:24} {rank if rank else 'not present'}")
        print()
        print("  A candidate is not a verdict. BM25 is a PROXY for what the products under")
        print("  test retrieve, and they retrieve with embeddings; BM25 and voyage-4 fail on")
        print("  different corpora. Treat these as worth a look and nothing more.")
    else:
        print("\n  no candidates: every planted session ranks inside the top "
              f"{CANDIDATE_DEPTH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
