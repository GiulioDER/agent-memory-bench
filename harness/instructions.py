"""One memory-use protocol, identical for every arm, plus a capped per-vendor schema appendix.

## The problem this exists to fix

`harness/adapters/base.py` has always required that a memory arm's system prompt be the shared
CLAUDE.md bundle plus a short integration sentence. Every run from `pilot-002` onward broke that
rule in one direction only: the `recall` arm carried the 5,428-character
`adapters/recall/skill.md`, `fs_grep` carried a 231-character sentence, and `claude_md`, `placebo`
and `bare` carried nothing.

Most of that 5,428 characters is not about any product. It is generic agent coaching: search before
your first write, search by operation and symptom rather than by goal, two short queries beat one
long one. The skill says so about itself ("the gain came from *searching at all*, not from better
queries"). Coaching that would help any retrieval arm, given to one arm, is a treatment confounded
with the thing under test, and a competitor is entitled to say the measured delta is partly prompt
engineering.

So the instruction is split in two:

- **The portable protocol** (`adapters/_shared/memory_protocol.md`), byte-identical for every arm
  that has a memory surface at all, with one placeholder for the sentence naming that arm's search
  mechanism.
- **A vendor appendix** (`adapters/<arm>/instruction_appendix.md`), which may describe only how to
  read THAT product's result schema, and is capped at :data:`APPENDIX_MAX_BYTES`. Every vendor
  writes their own; a vendor that writes none gets none, and the arm still gets the protocol.

⛔ `adapters/recall/skill.md` is NOT edited by this module and must not be. It is the provenance
anchor for `pilot-002` through `pilot-004` (`tests/test_recall_instruction.py` pins its sha256), and
a run is only comparable to those if it carries that exact text. `recall_instruction("skill")`
therefore still returns it verbatim. The fair variant is a NEW one, and which variant a run used is
recorded in `environment.json`.

## The abstention-sensitive block

Two sentences of the protocol pre-answer conditions the abstention suite (preregistration 005) is
built to measure: "when they disagree, the code wins" is the `superseded` answer, and "do not search
once, find nothing, and conclude the project has no opinion" is the `absent` answer. Telling every
arm the answer is fairer than telling one arm, but it still measures instruction-following rather
than retrieval behaviour.

Those sentences sit between `<!-- abstention-sensitive -->` markers and are stripped by
:func:`portable_protocol` when ``neutral=True``. The abstention suite runs neutral; the fact-present
suite does not. The choice is recorded per run, because the two are not comparable.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Mapping
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PROTOCOL_PATH = REPO / "adapters" / "_shared" / "memory_protocol.md"

#: An appendix explains one product's result schema. It is not a second protocol, and a cap is the
#: only thing that stops it becoming one. 1,200 bytes is about a third more than recall's own
#: "Reading the answer" section needs, so it is generous rather than tight.
APPENDIX_MAX_BYTES = 1200

#: The placeholder the protocol carries exactly once, filled with the arm's own search sentence.
SEARCH_SLOT = "{search_instruction}"

_ABSTENTION_BLOCK = re.compile(
    r"[ \t]*<!-- abstention-sensitive -->.*?<!-- /abstention-sensitive -->[ \t]*\n?",
    re.DOTALL,
)


class InstructionError(ValueError):
    """An arm's instruction is malformed, oversized, or missing its search sentence."""


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def protocol_template(*, neutral: bool = False) -> str:
    """The shared protocol text, before the search sentence is filled in."""

    text = _read(PROTOCOL_PATH)
    if SEARCH_SLOT not in text:
        raise InstructionError(
            f"{PROTOCOL_PATH} no longer contains {SEARCH_SLOT!r}; every arm's search "
            f"mechanism is named through that slot and nowhere else"
        )
    if neutral:
        text = _ABSTENTION_BLOCK.sub("", text)
        if "abstention-sensitive" in text:
            raise InstructionError(
                "an abstention-sensitive marker survived the strip; the block is unbalanced"
            )
    return text


def portable_protocol(search_instruction: str, *, neutral: bool = False) -> str:
    """The protocol every memory arm receives, with this arm's search sentence substituted.

    The substituted sentence is the ONLY per-arm difference in this half of the instruction, and it
    is one sentence because naming a mechanism takes one.
    """

    sentence = search_instruction.strip()
    if not sentence:
        raise InstructionError("an arm with a memory surface must name how to search it")
    if "\n\n" in sentence:
        raise InstructionError(
            "the search instruction is one sentence, not a section; put anything longer in the "
            "arm's instruction_appendix.md, where it is capped and reviewable"
        )
    return protocol_template(neutral=neutral).replace(SEARCH_SLOT, sentence)


def appendix_path(arm: str) -> Path:
    return REPO / "adapters" / arm / "instruction_appendix.md"


def vendor_appendix(arm: str) -> str:
    """One product's result-schema appendix, or empty when it ships none.

    Absent is not an error. A vendor who wants no appendix gets the protocol alone, and that is a
    legitimate configuration rather than a broken one.
    """

    path = appendix_path(arm)
    if not path.is_file():
        return ""
    text = _read(path).strip()
    size = len(text.encode("utf-8"))
    if size > APPENDIX_MAX_BYTES:
        raise InstructionError(
            f"{path.relative_to(REPO).as_posix()} is {size} bytes, over the "
            f"{APPENDIX_MAX_BYTES}-byte cap. The appendix describes how to read this product's "
            f"result schema; anything else belongs in the shared protocol, where every arm gets it."
        )
    return text


def compose(arm: str, search_instruction: str, *, neutral: bool = False) -> str:
    """The complete memory instruction for one arm: shared protocol, then its own appendix."""

    protocol = portable_protocol(search_instruction, neutral=neutral).rstrip()
    appendix = vendor_appendix(arm)
    if not appendix:
        return protocol + "\n"
    return protocol + "\n\n" + appendix + "\n"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def instruction_manifest(instructions: Mapping[str, str]) -> dict[str, dict[str, object]]:
    """Per-arm instruction sizes and digests, for the run artifact.

    Published beside the success rate so a reader can see the instruction budget each arm was given
    without re-deriving it. An arm with no memory surface appears with 0 bytes rather than being
    omitted, because "this arm was told nothing" is the fact that matters.
    """

    return {
        arm: {
            "bytes": len(text.encode("utf-8")),
            "chars": len(text),
            "sha256": sha256_text(text),
        }
        for arm, text in sorted(instructions.items())
    }


def assert_shared_protocol(instructions: Mapping[str, str], *, neutral: bool = False) -> None:
    """Refuse a roster where the memory arms do not share the protocol byte for byte.

    This is the check the old contract only stated. It compares the protocol half of each nonempty
    instruction (everything up to the appendix) against the rendered template with the arm's own
    search sentence removed, so an arm cannot quietly carry extra coaching.
    """

    template = protocol_template(neutral=neutral)
    head, _, tail = template.partition(SEARCH_SLOT)
    offenders: list[str] = []
    for arm, text in sorted(instructions.items()):
        if not text.strip():
            continue
        if not text.startswith(head) or tail.rstrip() not in text:
            offenders.append(arm)
    if offenders:
        raise InstructionError(
            f"arm(s) {offenders} do not carry the shared memory protocol verbatim. Every arm with "
            f"a memory surface receives adapters/_shared/memory_protocol.md unchanged; per-product "
            f"text goes in adapters/<arm>/instruction_appendix.md under the "
            f"{APPENDIX_MAX_BYTES}-byte cap."
        )


def excess_over_protocol(instructions: Mapping[str, str], *, neutral: bool = False) -> dict[str, int]:
    """Bytes each arm carries beyond the shared protocol. The fairness number, published per run."""

    base = len(portable_protocol("x", neutral=neutral).encode("utf-8")) - 1
    return {
        arm: max(0, len(text.encode("utf-8")) - base) if text.strip() else 0
        for arm, text in sorted(instructions.items())
    }


def arms_with_appendices(arms: Iterable[str]) -> dict[str, int]:
    """Which arms ship an appendix and how big it is. For the vendor-review record."""

    return {arm: len(vendor_appendix(arm).encode("utf-8")) for arm in sorted(arms)}


def refuse_shared_prompts(prompt_hashes: Mapping[str, Mapping[str, str]]) -> None:
    """Refuse a grid in which any arm serves one task's static bundle to another task.

    ``RecallAdapter`` cached one prompt per NAMESPACE and wrote it only when absent, so a grid,
    whose namespace is constant across tasks, served the first task's bundle to all 24 with nothing
    raising. Measured on ``diagnostic-001``: one distinct prompt across 24 recall sessions against
    24 for every other arm, which turned that arm's static half into misdirection about a different
    repository and voided three of five preregistered contrasts.

    Lives here rather than in one runner because it was in one runner: `scripts/diagnostic.py` had
    it and `scripts/pilot.py` did not, so the check that caught the defect once could not catch it
    in the script that produced every published pilot result.
    """

    for arm, by_task in sorted(prompt_hashes.items()):
        if not by_task or len(set(by_task.values())) == len(by_task):
            continue
        shared: dict[str, list[str]] = {}
        for task_id, digest in by_task.items():
            shared.setdefault(digest, []).append(task_id)
        worst = max(shared.values(), key=len)
        raise InstructionError(
            f"arm {arm!r} has {len(set(by_task.values()))} distinct prompts across "
            f"{len(by_task)} tasks; {len(worst)} of them share one, starting {sorted(worst)[:4]}. "
            f"Every task must receive its own static bundle or the arm is not comparable."
        )


def refuse_shared_prompts_or_exit(prompt_hashes: Mapping[str, Mapping[str, str]]) -> None:
    """The runner-facing form: a grid misconfiguration exits with a message, not a traceback.

    Both spellings exist on purpose. A library raises a typed error a caller can catch; a runner
    that is about to spend 288 sessions should stop with one readable line. The tests pin the
    runner contract, because that is the one a person sees at 2am.
    """

    try:
        refuse_shared_prompts(prompt_hashes)
    except InstructionError as error:
        raise SystemExit(str(error)) from None
