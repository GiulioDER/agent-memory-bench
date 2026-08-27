"""The leakage audit for planted corpora, which is `audit_corpus.py` run inside out.

`scripts/audit_corpus.py` asserts every governing fact lives exactly where it claims to. A planted
corpus needs the same discipline applied to facts that are deliberately WRONG, and it needs three
checks the fact-present audit has no reason to make.

Per plant:

1. **Presence**: every `wrong_terms` entry appears in the planted session. A plant nobody can
   retrieve cannot damage anything, and would be scored as an ordinary miss.
2. **Containment**: no `wrong_terms` entry appears in the fixture tree, the CLAUDE.md bundle, the
   distractors, or any other task's sessions. Same rule as the real corpus, same reason.
3. **The plant is not pre-refuted**: no `wrong_terms` entry appears in the task's own REAL session
   either. This is the check with teeth, and it exists because of how `superseded` fails: if the
   current memo says "ids are no longer lowercase", the stale memo is marked stale by the very
   evidence it is meant to compete with, one memo answers the question, and the condition is
   strictly easier than the one preregistered while still being reported under its name.

Per condition:

4. **The fact really is missing**: for every condition whose shape withholds the real session
   (`absent`, `contradictory`, `adjacent`), the task's own `fact_terms` must not survive anywhere
   in that condition's assembled corpus. This is assembled and checked rather than reasoned about,
   because the composition is where an off-by-one silently leaves the answer in the feed.
5. **Attributability**: a condition that plants anything needs `damage.py` and a
   `reference/damaged_<condition>.py`, which is what `tests/test_damage_detection.py` proves fires
   on the plant and stays silent on the factless failure. `absent` is exempt: its damage signature
   is "invents a convention", which is not attributable to any planted string, so it is measured by
   the primary endpoint alone.

Per planted session, once recorded:

6. **Salience**: preregistration 005 names planted-memo salience as a confound. Length must sit
   inside the real corpus range, and lexical novelty must not exceed the most novel real session's.
   That floor is computed from the corpus rather than chosen, so it cannot be tuned to admit a
   plant that was going to fail it.

A plant that has not been recorded yet is reported PENDING, not passed. Running this before any
recording exists is the intended first use.

## What this audit cannot see

Containment is a SUBSTRING test, so it catches a term two documents share and is blind to two
documents that mean the same thing in different words. Retrieval is semantic, so a plant can be
lexically clean and still compete with a real memo it never quotes. Nothing here rules that out,
and no static check can; what bounds it is the `bare` arm and the per-condition damage detector,
which attributes a failure to the planted string rather than to retrieval in general.

The first run of this audit is the worked example: it rejected the bare word `lowercase` for
`ts-base36-id` because `ts-casefold-sort` and two distractors also contain it. That collision was
lexical, on a word used incidentally in an explanation about sorting names, and the fix was a more
distinctive term. Had it been semantic, this audit would have said nothing.

    python -m scripts.audit_plants
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from harness.plants import CONDITION_SHAPE, load_plants
from harness.tasks import discover_tasks
from scripts.assemble_condition_corpus import assemble

BASE_CORPUS = REPO / "corpus"
BUNDLES = [BASE_CORPUS / "claude_md_bundle_smoke.md"]
WORD = re.compile(r"[a-z][a-z0-9_\-]{2,}")


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace").lower()


def _words(text: str) -> set[str]:
    return set(WORD.findall(text))


def real_session_paths() -> list[Path]:
    return sorted((BASE_CORPUS / "sessions").rglob("*.jsonl")) + sorted(
        (BASE_CORPUS / "distractors").glob("*.jsonl")
    )


def salience_envelope() -> tuple[int, int, int, int, float]:
    """Length and novelty limits, computed from the 125 real sessions rather than chosen.

    Novelty is the fraction of a session's word types that appear in NO other session. The
    threshold is the most novel real session, so a plant is only rejected for being more unlike
    the corpus than anything the corpus already contains.
    """

    paths = real_session_paths()
    texts = {path: _text(path) for path in paths}
    vocab = {path: _words(text) for path, text in texts.items()}
    chars = [len(text) for text in texts.values()]
    turns = [text.count("\n") for text in texts.values()]

    worst = 0.0
    for path, own in vocab.items():
        if not own:
            continue
        others: set[str] = set()
        for other_path, other in vocab.items():
            if other_path != path:
                others |= other
        worst = max(worst, len(own - others) / len(own))
    return min(chars), max(chars), min(turns), max(turns), worst


def corpus_vocabulary() -> set[str]:
    words: set[str] = set()
    for path in real_session_paths():
        words |= _words(_text(path))
    return words


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=1, help="seed used for the assembly checks")
    args = parser.parse_args()

    tasks = {task.task_id: task for task in discover_tasks()}
    specs = {
        task_id: spec
        for task_id, task in tasks.items()
        if (spec := load_plants(task.path)) is not None
    }
    if not specs:
        print("no task declares plants.json; nothing to audit")
        return 0

    violations: list[str] = []
    pending: list[str] = []

    min_chars, max_chars, min_turns, max_turns, max_novelty = salience_envelope()
    vocabulary = corpus_vocabulary()

    for task_id, spec in sorted(specs.items()):
        task = tasks[task_id]
        real_sessions = sorted((BASE_CORPUS / "sessions" / task_id).glob("*.jsonl"))
        real_text = " ".join(_text(path) for path in real_sessions)

        outside: dict[Path, str] = {}
        for other_id in tasks:
            if other_id != task_id:
                for path in sorted((BASE_CORPUS / "sessions" / other_id).glob("*.jsonl")):
                    outside[path] = _text(path)
        for path in sorted((BASE_CORPUS / "distractors").glob("*.jsonl")):
            outside[path] = _text(path)
        for path in (task.path / "tree").rglob("*"):
            if path.is_file():
                outside[path] = _text(path)
        for path in BUNDLES:
            if path.is_file():
                outside[path] = _text(path)

        seen_plants = {
            plant.name: plant
            for plan in spec.conditions.values()
            for plant in plan.plants
        }

        for name, plant in sorted(seen_plants.items()):
            recording = BASE_CORPUS / "plants" / task_id / plant.filename
            if not recording.is_file():
                pending.append(f"{task_id}/{name}: not recorded yet ({recording.relative_to(REPO)})")
                # Containment and pre-refutation do not need the recording, so they still run.
            else:
                planted_text = _text(recording)
                for term in plant.wrong_terms:
                    if term.lower() not in planted_text:
                        violations.append(
                            f"{task_id}/{name}: wrong term {term!r} appears in NONE of its own "
                            f"planted session; nothing can retrieve it"
                        )
                chars, turns = len(planted_text), planted_text.count("\n")
                if not (min_chars <= chars <= max_chars):
                    violations.append(
                        f"{task_id}/{name}: {chars} chars is outside the real corpus range "
                        f"[{min_chars}, {max_chars}]; length is a salience confound"
                    )
                if not (min_turns <= turns <= max_turns):
                    violations.append(
                        f"{task_id}/{name}: {turns} turns is outside the real corpus range "
                        f"[{min_turns}, {max_turns}]"
                    )
                own = _words(planted_text)
                if own:
                    novelty = len(own - vocabulary) / len(own)
                    if novelty > max_novelty:
                        violations.append(
                            f"{task_id}/{name}: {novelty:.1%} of its vocabulary appears nowhere "
                            f"in the real corpus, above the most novel real session "
                            f"({max_novelty:.1%}); it would read as a different kind of document"
                        )

            for term in plant.wrong_terms:
                needle = term.lower()
                for path, text in outside.items():
                    if needle in text:
                        violations.append(
                            f"{task_id}/{name}: wrong term {term!r} leaked into "
                            f"{path.relative_to(REPO)}"
                        )
                if real_sessions and needle in real_text:
                    violations.append(
                        f"{task_id}/{name}: wrong term {term!r} also appears in the task's own "
                        f"REAL session. The plant is pre-refuted by the evidence it is meant to "
                        f"compete with, so the condition is easier than the one preregistered."
                    )

        for condition, plan in sorted(spec.conditions.items()):
            if plan.plants:
                if not (task.path / "damage.py").is_file():
                    violations.append(
                        f"{task_id}/{condition}: plants a wrong fact but has no damage.py, so "
                        f"endpoint 4 cannot attribute any failure to it"
                    )
                reference = task.reference_dir / f"damaged_{condition}.py"
                if not reference.is_file():
                    violations.append(
                        f"{task_id}/{condition}: no {reference.name}; nothing proves the detector "
                        f"fires on the plant and stays silent on the factless failure"
                    )

    # The composition check needs a built corpus, and building it is cheap and disposable.
    for condition, shape in sorted(CONDITION_SHAPE.items()):
        selection = [t for t, spec in specs.items() if spec.plan(condition)]
        if not selection:
            continue
        if shape["include_real"]:
            continue
        recorded = all(
            (BASE_CORPUS / "plants" / task_id / plant.filename).is_file()
            for task_id in selection
            for plant in specs[task_id].conditions[condition].plants
        )
        if not recorded:
            pending.append(f"{condition}: composition unchecked until its plants are recorded")
            continue
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / condition
            assemble(condition, args.seed, selection, root)
            for task_id in selection:
                remaining = sorted((root / "sessions" / task_id).glob("*.jsonl"))
                text = " ".join(_text(path) for path in remaining)
                for term in tasks[task_id].fact_terms:
                    if term.lower() in text:
                        violations.append(
                            f"{condition}/{task_id}: the TRUE fact {term!r} survives in the "
                            f"assembled corpus, so this condition still answers the question"
                        )

    print(f"plants audited: {sum(len(s.conditions) for s in specs.values())} condition(s) "
          f"across {len(specs)} task(s)")
    if pending:
        print(f"\nPENDING: {len(pending)} plant(s) not yet recorded")
        for note in pending:
            print(f"  {note}")
    if violations:
        print(f"\nLEAKAGE: {len(violations)} violation(s)")
        for violation in violations:
            print(f"  {violation}")
        return 1
    # PENDING is not a failure: auditing a spec before its recordings exist is the intended first
    # use, and the pending lines above say exactly which checks did not run.
    print("\nclean: no wrong term outside its own plant, no true fact left in a withheld condition")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
