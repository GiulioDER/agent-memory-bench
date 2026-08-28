"""The corpus leakage audit: every governing fact lives exactly where it claims to.

Four assertions, per task that declares ``fact_terms``:

1. **Presence**: each term appears in at least one of that task's own precursor sessions
   (``corpus/sessions/<task_id>/``). A fact no session states cannot be retrieved by anyone.
2. **Containment**: no term appears in any OTHER session directory, in any distractor, or in any
   planted session. A fact reachable from two tasks makes their results dependent, and dependence
   is invisible in the per-task analysis.
3. **Locus**: no term appears in the task's fixture tree, in the shared CLAUDE.md bundle, or in the
   TASK PROMPT. A fact derivable without memory measures nothing.
4. **Distinctness**: no two tasks' fact-term vocabularies overlap enough to be one convention wearing
   two names. Reported, not enforced; see below.

## What changed on 2026-08-28, and why a green run before that date proved less than it looked

Three defects, all of the same shape: the test saw the bytes rather than what a reader sees.

- **Markdown defeated it.** A recorded agent writes prose, and prose carries emphasis.
  ``ts-dedup-order``'s planted session contained "the *first* occurrence" and
  "first-occurrence deduplication", both of which state that task's governing fact, and BOTH passed
  a plain substring test for ``first occurrence``. ``scripts/audit_plants.py`` was fixed with
  ``harness.plants.normalise``; this audit, which guards the REAL corpus rather than the plants,
  was not. It is now.
- **JSON escaping defeated it.** Every corpus file is JSONL, so a phrase spanning a line break in a
  recorded message sits in the bytes as an escaped newline, two characters, which no whitespace
  normalisation collapses. Text fields are decoded before comparison.
- **The scope missed a directory.** ``corpus/sessions/smoke/`` holds two transcripts that belong to
  no task. ``CorpusManifest.build`` globs ``sessions/**/*.jsonl``, so every published run ingested
  them, while this audit iterated discovered TASK ids and therefore never opened them.
  ``scripts/assemble_condition_corpus.py`` was fixed for exactly this and the audits were not.

⚠️ **The re-check was run and the real corpus was clean.** Across all 30 tasks, 26 sessions, 99
distractors, 11 planted sessions and every fixture tree, decoding and normalising surfaced **zero**
leaks that the old byte-level test had missed. The published fact-present results are not affected
by any of the three defects above. That is worth stating explicitly, because "we hardened the gate"
and "the gate was wrong about the data" are different claims and only the first one is true here.

## What this audit still cannot see

Containment is a SUBSTRING test over a hand-written term list, so it catches a phrase two documents
share and is blind to two documents that mean the same thing in different words. Retrieval is
semantic; nothing here rules that out and no static check can. What bounds it is the ``bare`` arm:
a fact rediscoverable from the repository shows up as a high ``bare`` rate, and that rate is
measured (0.463 pooled over 30 tasks at n = 12, `resolution-001`).

    python -m scripts.audit_corpus
"""

from __future__ import annotations

import json
import sys
from itertools import combinations
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from harness.plants import normalise
from harness.tasks import discover_tasks

BUNDLES = [REPO / "corpus" / "claude_md_bundle_smoke.md"]

#: The JSONL fields a session's reader actually sees. Compared decoded, never as raw bytes.
TEXT_FIELDS = ("content", "tool_result", "tool_input")

#: Above this Jaccard overlap of content words, two tasks' fact terms are reported as possibly one
#: convention. Not a failure: the check cannot tell a shared abstraction from a shared word, and the
#: one real pair it finds (`ts-golden-regen` / `ts-ignore-gen`, "generated file, never hand-edit")
#: does NOT show correlated outcomes in any published run. It is a prompt to look, not a verdict.
OVERLAP_REPORT_THRESHOLD = 0.25

#: Words too common to make two conventions the same convention.
_STOP = frozenset(
    (
        "the", "a", "an", "is", "are", "to", "of", "in", "on", "and", "or", "not", "never",
        "no", "for", "with", "as", "it", "be", "by", "at", "one", "must", "always", "every",
        "this", "that", "these", "those", "from", "into", "out", "up", "down",
    )
)


def readable_text(path: Path) -> str:
    """Everything a reader of this file would see, normalised.

    A ``.jsonl`` transcript is decoded field by field, so an escaped newline inside a recorded
    message cannot hide a phrase that spans it. Anything else is read whole.
    """

    raw = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix != ".jsonl":
        return normalise(raw)
    parts: list[str] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            # A malformed line is compared raw rather than skipped: skipping is how a leak hides.
            parts.append(line)
            continue
        for field in TEXT_FIELDS:
            value = event.get(field)
            if isinstance(value, str):
                parts.append(value)
            elif value is not None:
                parts.append(json.dumps(value, ensure_ascii=False))
    return normalise(" ".join(parts))


def _read_all(paths: list[Path]) -> dict[Path, str]:
    return {path: readable_text(path) for path in paths if path.is_file()}


def content_words(terms: tuple[str, ...]) -> set[str]:
    out: set[str] = set()
    for term in terms:
        out |= {w for w in normalise(term).split() if w not in _STOP and len(w) > 2}
    return out


def main() -> int:
    sessions_root = REPO / "corpus" / "sessions"
    # EVERY session directory, not only the ones whose name is a task id. corpus/sessions/smoke/
    # is in the manifest and therefore in every arm's feed.
    all_sessions = sorted(sessions_root.rglob("*.jsonl"))
    distractors = sorted((REPO / "corpus" / "distractors").glob("*.jsonl"))
    planted = sorted((REPO / "corpus" / "plants").rglob("*.jsonl"))
    violations: list[str] = []
    audited = 0

    tasks = [task for task in discover_tasks() if task.fact_terms]
    corpus_text = _read_all(all_sessions + distractors + planted + BUNDLES)

    for task in tasks:
        own_sessions = sorted((sessions_root / task.task_id).glob("*.jsonl"))
        own_text = " ".join(corpus_text.get(path, "") for path in own_sessions)
        own_plants = {path for path in planted if path.parent.name == task.task_id}
        fixture_files = [path for path in (task.path / "tree").rglob("*") if path.is_file()]
        outside = {
            path: text
            for path, text in corpus_text.items()
            if path not in set(own_sessions) and path not in own_plants
        }
        outside.update(_read_all(fixture_files))
        # The prompt is the one piece of text every arm receives and no audit read it.
        outside[task.path / "task.json#prompt"] = normalise(task.prompt)

        for term in task.fact_terms:
            needle = normalise(term)
            if own_sessions and needle not in own_text:
                violations.append(
                    f"{task.task_id}: term {term!r} appears in NONE of its own sessions"
                )
            for path, text in outside.items():
                if needle in text:
                    where = (
                        path.name
                        if path.name.endswith("#prompt")
                        else path.relative_to(REPO).as_posix()
                    )
                    violations.append(f"{task.task_id}: term {term!r} leaked into {where}")
        if not own_sessions:
            print(f"  note: {task.task_id} has no recorded sessions yet; presence unchecked")
        audited += 1

    vocab = {task.task_id: content_words(task.fact_terms) for task in tasks}
    overlaps = []
    for a, b in combinations(sorted(vocab), 2):
        shared = vocab[a] & vocab[b]
        if not shared:
            continue
        union = vocab[a] | vocab[b]
        jaccard = len(shared) / len(union)
        if jaccard >= OVERLAP_REPORT_THRESHOLD:
            overlaps.append((jaccard, a, b, sorted(shared)))
    overlaps.sort(reverse=True)

    if overlaps:
        print(
            f"\nOVERLAP: {len(overlaps)} task pair(s) share enough of their fact vocabulary to be "
            f"worth a look. Two tasks encoding ONE convention are not two independent units, and "
            f"the per-task cluster bootstrap assumes they are."
        )
        for jaccard, a, b, shared in overlaps:
            print(f"  {jaccard:.2f}  {a} / {b}  shared={shared}")

    if violations:
        print(f"\nLEAKAGE: {len(violations)} violation(s) across {audited} task(s)")
        for violation in violations:
            print(f"  {violation}")
        return 1
    print(
        f"clean: {audited} task(s) audited against {len(corpus_text)} corpus file(s), decoded and "
        f"normalised; no term outside its own sessions, fixture clean, prompt clean"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
