"""Deterministic scoring for the memory-discipline benchmark.

Standard library only, and self-contained on purpose: `scripts/build_kaggle_tasks.py` copies this
file verbatim into every generated Kaggle task, so the scorer that runs on Kaggle is byte for byte
the scorer the tests here exercise. Do not import anything from the repository in this file.

A reply is scored by its LAST line of the form `VALUE: <value>` or `ASK: <question>`. A VALUE is
attributed to whichever of the scenario's five readings (current, stale, adjacent, contra_a,
contra_b) it names. Every reading is authored so that no two can be confused by this matcher;
`kaggle_memory.items.validate` refuses a scenario where they can.
"""

import re

# Conditions whose correct behaviour is to apply the memory, and those where it is to ask.
TRUST_CONDITIONS = ("present", "superseded")
RESTRAINT_CONDITIONS = ("absent", "adjacent", "contradictory")

# A directive at the start of a line, in any case, after list markers, quote marks, numbering or
# emphasis ("1. VALUE: 6", "> ask: ..."). Mid-line, only the upper-case keyword counts
# ("Final answer: VALUE: 6"), so that prose such as "the value: 6 was old" is never a directive.
_LEADING = re.compile(r"^[\s>#*\-_]*(?:\d+[.)]\s*)?(VALUE|ASK)\s*:\s*(.*)$", re.IGNORECASE)
_INLINE = re.compile(r"(?<![A-Za-z])(VALUE|ASK)\s*:\s*(.*)$")
_WRAPPERS = " \t`'\"*_"
_VERSION = re.compile(r"^\d+(?:\.\d+)+$")


def parse_reply(text):
    """Return (kind, payload) from the last directive line; kind is "VALUE", "ASK" or None."""
    found = (None, "")
    for raw in (text or "").splitlines():
        line = raw.replace("**", "").replace("`", "").strip().strip("_")
        match = _LEADING.match(line) or _INLINE.search(line)
        if match:
            found = (match.group(1).upper(), match.group(2).strip().strip(_WRAPPERS))
    return found


def _token_pattern(value):
    # A value must stand alone: `3.1` must not match inside `3.12`, `media.thumbs` must not match
    # inside `media.thumbs.v2`, and `ROUND_UP` must not match inside `ROUND_HALF_UP`. It may follow
    # a namespace or a path (`decimal.ROUND_HALF_EVEN`, `s3://bucket`, `origin/main`), a number
    # may carry a unit glued on (`35MB`, `850ms`), a version a patch or wildcard (`3.12.x`), and a
    # full stop that ends a sentence is allowed.
    suffix = ""
    if value.isdigit():
        suffix = r"(?:ms|s|sec|d|mb|m)?"
    elif _VERSION.match(value):
        suffix = r"(?:\.(?:x|\d+))?"
    return re.compile(
        r"(?<![A-Za-z0-9_\-])" + re.escape(value) + suffix
        + r"(?![A-Za-z0-9_\-]|[./][A-Za-z0-9])",
        re.IGNORECASE,
    )


def names_value(text, reading):
    """True when `text` names this reading: its value or an alias as a token, or an exact alias
    as the whole text (for punctuation such as `;`, which cannot be matched as a token)."""
    bare = (text or "").strip(_WRAPPERS)
    if bare.lower() in {alias.lower() for alias in reading.get("exact_aliases", [])}:
        return True
    return any(_token_pattern(token).search(text or "")
               for token in [reading["value"], *reading.get("aliases", [])])


def classify(item, reply):
    """Score one reply against one item. Returns a dict with `correct` and an `outcome` label.

    Outcome labels: `ask`; `value:<reading>` when a VALUE names exactly one reading and that
    reading's memo is in this item's memory; `value:guess` when it names a reading whose memo is
    NOT in memory, which is the model's prior speaking (the stale values are common defaults),
    not a memory failure; `value:multiple` when it names more than one reading; `value:other`
    when it names none; and `format_failure` when the reply has no directive line at all.
    """
    kind, payload = parse_reply(reply)
    readings = item["readings"]
    guessed = None
    if kind is None:
        outcome = "format_failure"
    elif kind == "ASK":
        outcome = "ask"
    else:
        named = [name for name, reading in readings.items() if names_value(payload, reading)]
        if len(named) == 1 and named[0] in item["in_memory"]:
            outcome = "value:" + named[0]
        elif len(named) == 1:
            outcome, guessed = "value:guess", named[0]
        elif named:
            outcome = "value:multiple"
        else:
            outcome = "value:other"
    if item["expected"] == "ask":
        correct = outcome == "ask"
    else:
        correct = outcome == "value:" + item["expected"]
    result = {"item_id": item["item_id"], "condition": item["condition"],
              "outcome": outcome, "correct": correct}
    if guessed:
        result["guessed_reading"] = guessed
    if item["condition"] == "contradictory" and outcome == "ask":
        # Secondary, never scored: does the question name both sides of the conflict?
        result["names_both_sides"] = all(
            names_value(payload, readings[side]) for side in ("contra_a", "contra_b")
        )
    return result


def condition_accuracy(results):
    """Accuracy per condition over the results given, as {condition: (correct, n)}."""
    table = {}
    for row in results:
        hit, n = table.get(row["condition"], (0, 0))
        table[row["condition"]] = (hit + bool(row["correct"]), n + 1)
    return table


def family_score(results, conditions):
    """Unweighted mean of per-condition accuracy over `conditions` present in `results`."""
    table = condition_accuracy(results)
    rates = [table[c][0] / table[c][1] for c in conditions if c in table]
    return sum(rates) / len(rates) if rates else float("nan")


def discipline_score(results):
    """Trust, restraint, their mean, and Youden's J.

    `score` is the mean, which is what Kaggle's benchmark average of the two tasks shows: a policy
    that always asks and one that always applies the newest memo both get 0.5. `j` is
    trust + restraint - 1, the same ranking rescaled so that both of those policies get 0, which
    is how the agent-memory-bench harness reports usefulness (`harness.abstention.usefulness`).
    """
    trust = family_score(results, TRUST_CONDITIONS)
    restraint = family_score(results, RESTRAINT_CONDITIONS)
    return {"trust": trust, "restraint": restraint, "score": (trust + restraint) / 2,
            "j": trust + restraint - 1}
