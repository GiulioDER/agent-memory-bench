"""Planted corpora: the four conditions of preregistration 005, as data.

The 24 `ts-*` tasks all place their governing fact IN the corpus, so the suite can only ask
whether memory helps. Preregistration 005 adds four conditions in which retrieved evidence is
absent, stale, contradictory or inapplicable. A condition is a property of **what the corpus
contains**, never of what a system does about it: every arm ingests byte-identical bytes, and
whether a product copes through supersession metadata, recency weighting, reranking or a refusal
threshold is the thing being measured.

A condition corpus is an ordinary corpus root (`sessions/`, `distractors/`, `manifest.json`), so
`CorpusManifest.build` and every adapter work against it unchanged.

## What a task declares

`tasks/<task_id>/plants.json` names, per condition, which of the task's REAL sessions the corpus
keeps and which planted sessions it adds:

    {"conditions": {"superseded": {"include_real": true, "plants": ["stale_lowercase"]}},
     "plants": {"stale_lowercase": {"wrong_terms": ["lowercase"], "rationale": "..."}}}

Planted sessions are RECORDED, not authored, by the same pipeline as the real ones
(`scripts/record_precursor.py` against a staged incident under `tasks/<id>/plants/<name>/`),
landing at `corpus/plants/<task_id>/<name>.jsonl`. That is not fastidiousness: preregistration
005 names planted-memo salience as a confound, and an authored memo among 125 recorded ones
measures writing style.

## The shapes are enforced, because a typo must not quietly produce a different condition

`superseded` without the current fact is `absent`. `contradictory` with one memo is `adjacent`.
Both would run, produce numbers, and be reported under the wrong condition name. So the shape of
each condition is checked against the frozen table rather than trusted to the author.

## "Undated" is not achievable in this format, and is approximated deliberately

The `contradictory` condition asks for "two undated memos that disagree, neither marked". Every
corpus transcript carries `ts` fields, so a system that weights by recency can always break the
tie, and whichever memo happened to be recorded second would win by an artefact of recording
order. `assign_contradiction_dates` therefore permutes which memo is dated earlier **per seed**,
so recency cannot systematically favour the right answer or the wrong one; a recency-weighted
system scores 50% on the tie by construction rather than being handed a signal.

That is a mitigation and not a fix, and the difference matters when the result is read: this
suite measures whether a conflict is SURFACED, and cannot claim to have removed every trace of
ordering. Content stays verbatim; only `ts` moves, which is the transform the corpus README
already discloses.
"""

from __future__ import annotations

import json
import random
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from .damage import CONDITIONS, PRESENT

#: Emphasis and word-joining characters that a substring test must not be fooled by.
_NOISE = re.compile(r"[*_`~]+")
_JOINERS = re.compile(r"[-‐-―/\\]+")
_SPACE = re.compile(r"\s+")


def normalise(text: str) -> str:
    """Lowercase and strip the formatting a literal fact-term check is blind to.

    A recorded agent writes prose, and prose carries emphasis. `ts-dedup-order`'s planted session
    contained "the *first* occurrence" and "first-occurrence deduplication", which state this
    task's governing fact outright, and BOTH passed a plain substring test for "first occurrence":
    the asterisks and the hyphen broke the match. The plant therefore stated the very convention
    it exists to withhold, and the condition would have answered its own question.

    Accents fold for the same reason and were added for the same kind of near-miss: a recording
    that decided app.log stamps were "Sao\u0303 Paulo local" failed the presence gate for the term
    "Sao Paulo", so a plant that had stated its wrong fact perfectly clearly read as unretrievable.
    The containment direction is where this actually bites, because there the failure is silent: a
    leaked term wearing a diacritic would have passed an audit whose whole job is to find it.

    So every fact-term and wrong-term comparison goes through here. Accents are folded to their
    base letters, markdown emphasis is removed, hyphens and slashes become spaces, and runs of
    whitespace collapse, which makes the test see what a reader sees rather than what the bytes
    happen to be.
    """

    decomposed = unicodedata.normalize("NFKD", text.lower())
    lowered = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    lowered = _NOISE.sub("", lowered)
    lowered = _JOINERS.sub(" ", lowered)
    return _SPACE.sub(" ", lowered)

#: The frozen table in preregistration 005, as a machine-checkable shape. ``include_real`` is
#: whether the task's own true precursor stays in the corpus; a condition that gets this wrong is
#: a different condition wearing the right name.
CONDITION_SHAPE: dict[str, dict[str, object]] = {
    # the governing fact, correct and unambiguous: the real session and nothing else. The
    # identity transform, which is why it needs no plant and no author. It is the only condition
    # in which ABSTAINING is a loss, and without it abstinence is a dominant strategy across the
    # whole suite. See `harness.damage.PRESENT`.
    "present": {"include_real": True, "min_plants": 0, "max_plants": 0},
    # no governing fact for this task: the real session is withheld and nothing replaces it
    "absent": {"include_real": False, "min_plants": 0, "max_plants": 0},
    # the old fact AND the newer one: the real session IS the newer one
    "superseded": {"include_real": True, "min_plants": 1, "max_plants": None},
    # two memos that disagree, neither of them the marked truth
    "contradictory": {"include_real": False, "min_plants": 2, "max_plants": None},
    # a confident memo governing a DIFFERENT subsystem, with this task's fact absent
    "adjacent": {"include_real": False, "min_plants": 1, "max_plants": None},
}

#: Session dates the contradictory permutation draws from. Fixed here so a corpus is reproducible
#: from its seed alone, and far enough apart that a recency weighting has something to bite on.
CONTRADICTION_DATES = ("2026-05-06", "2026-06-17")


class PlantSpecError(ValueError):
    """A plants.json that would produce a corpus other than the one it names."""


@dataclass(frozen=True)
class Plant:
    """One planted session: a recording that lands on a fact the repository cannot support."""

    name: str
    wrong_terms: tuple[str, ...]
    rationale: str

    @property
    def filename(self) -> str:
        return f"{self.name}.jsonl"


@dataclass(frozen=True)
class ConditionPlan:
    """What one condition's corpus holds for one task."""

    condition: str
    include_real: bool
    plants: tuple[Plant, ...]


@dataclass(frozen=True)
class PlantSpec:
    task_id: str
    conditions: dict[str, ConditionPlan] = field(default_factory=dict)

    def plan(self, condition: str) -> ConditionPlan | None:
        if condition == PRESENT:
            return present_plan()
        return self.conditions.get(condition)


def present_plan() -> ConditionPlan:
    """The `present` condition, which is the same for every task and is never authored.

    Every other condition is a claim about what somebody planted, so it has to be declared per
    task in ``plants.json`` and validated. `present` is the identity transform: the task's real
    precursor session and nothing else. There is nothing to declare, nothing to record and
    nothing that can be got wrong, which is why a task needs no ``plants.json`` at all to be
    assembled in it. That matters practically: most tasks have no ``plants.json``, and under the
    four adversarial conditions they were therefore unassemblable and invisible to the suite.
    """

    return ConditionPlan(condition=PRESENT, include_real=True, plants=())


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise PlantSpecError(message)


def load_plants(task_dir: str | Path) -> PlantSpec | None:
    """Load and validate ``<task_dir>/plants.json``, or None for a task with no plants."""

    path = Path(task_dir) / "plants.json"
    if not path.is_file():
        return None
    task_id = Path(task_dir).name
    data = json.loads(path.read_text(encoding="utf-8"))

    declared = data.get("plants", {})
    _require(isinstance(declared, dict), f"{task_id}: 'plants' must be an object")
    catalog: dict[str, Plant] = {}
    for name, body in declared.items():
        _require(isinstance(body, dict), f"{task_id}: plant {name!r} must be an object")
        terms = tuple(str(t) for t in body.get("wrong_terms", ()))
        _require(
            bool(terms),
            f"{task_id}: plant {name!r} declares no wrong_terms, so the leakage audit cannot "
            f"check it and endpoint 4 cannot attribute anything to it",
        )
        catalog[name] = Plant(
            name=str(name), wrong_terms=terms, rationale=str(body.get("rationale", ""))
        )

    conditions_raw = data.get("conditions", {})
    _require(isinstance(conditions_raw, dict), f"{task_id}: 'conditions' must be an object")
    conditions: dict[str, ConditionPlan] = {}
    for condition, body in conditions_raw.items():
        _require(
            condition != PRESENT,
            f"{task_id}: plants.json declares {PRESENT!r}. That condition is the identity "
            f"transform and is never authored: it is the task's real session and nothing else. "
            f"Declaring it would let a plant into the one condition whose whole purpose is that "
            f"the evidence is correct.",
        )
        _require(
            condition in CONDITIONS,
            f"{task_id}: unknown condition {condition!r}; expected one of {CONDITIONS}",
        )
        _require(isinstance(body, dict), f"{task_id}: condition {condition!r} must be an object")
        shape = CONDITION_SHAPE[condition]
        names = [str(n) for n in body.get("plants", ())]
        for name in names:
            _require(
                name in catalog,
                f"{task_id}: condition {condition!r} names plant {name!r}, which is not declared",
            )
        _require(
            len(set(names)) == len(names),
            f"{task_id}: condition {condition!r} names the same plant twice",
        )

        include_real = bool(body.get("include_real", shape["include_real"]))
        _require(
            include_real == shape["include_real"],
            f"{task_id}: condition {condition!r} sets include_real={include_real}, but the "
            f"preregistered shape requires {shape['include_real']}. A {condition!r} corpus of "
            f"the other shape is a different condition reported under the wrong name.",
        )
        minimum = shape["min_plants"]
        maximum = shape["max_plants"]
        _require(
            len(names) >= minimum,
            f"{task_id}: condition {condition!r} needs at least {minimum} plant(s), "
            f"got {len(names)}",
        )
        _require(
            maximum is None or len(names) <= maximum,
            f"{task_id}: condition {condition!r} allows at most {maximum} plant(s), "
            f"got {len(names)}",
        )
        conditions[condition] = ConditionPlan(
            condition=condition,
            include_real=include_real,
            plants=tuple(catalog[name] for name in names),
        )

    _require(bool(conditions), f"{task_id}: plants.json declares no conditions")
    return PlantSpec(task_id=task_id, conditions=conditions)


def assign_contradiction_dates(plants: tuple[Plant, ...], seed: int) -> dict[str, str]:
    """Which contradictory memo is dated earlier, permuted per seed.

    Recording order is an artefact. Without this, whichever memo was recorded second is newer in
    every seed, and a recency-weighted system is handed a constant answer that the design never
    intended to give it. See the module docstring for why this is a mitigation, not a fix.
    """

    dates = list(CONTRADICTION_DATES)
    while len(dates) < len(plants):
        dates.append(dates[-1])
    order = list(plants)
    random.Random(f"contradiction:{seed}").shuffle(order)
    return {plant.name: dates[index] for index, plant in enumerate(order)}


def sources_for(plan: ConditionPlan, task_id: str, corpus_root: str | Path) -> list[Path]:
    """The session files this task contributes to one condition's corpus, in corpus order.

    Raises rather than returning an empty list for a condition that expected plants: a silently
    empty task scores as `absent` while being reported as something else.
    """

    root = Path(corpus_root)
    chosen: list[Path] = []
    if plan.include_real:
        real = sorted((root / "sessions" / task_id).glob("*.jsonl"))
        if not real:
            raise PlantSpecError(
                f"{task_id}: condition {plan.condition!r} keeps the real session, but "
                f"{root / 'sessions' / task_id} holds none"
            )
        chosen.extend(real)
    for plant in plan.plants:
        path = root / "plants" / task_id / plant.filename
        if not path.is_file():
            raise PlantSpecError(
                f"{task_id}: condition {plan.condition!r} needs planted session {path}, which "
                f"has not been recorded yet (scripts/record_plant.py)"
            )
        chosen.append(path)
    return chosen
