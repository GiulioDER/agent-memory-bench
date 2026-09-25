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

# Three strengths of directive, and the LAST of the strongest kind present wins:
#   strong  a line that starts with upper-case VALUE: or ASK:, after list markers, quote marks,
#           numbering or emphasis ("1. VALUE: 6", "> ASK: ...");
#   weak    the same in any other case ("Value: 6");
#   inline  upper-case VALUE: or ASK: later in a line ("Final answer: VALUE: 6").
# So an afterthought such as "Value: 3 was the stale one" or "(otherwise I would reply ASK: ...)"
# cannot override a strong "VALUE: 6" above it, and an identifier such as DEFAULT_VALUE: is never
# a directive. A fullwidth colon counts. An empty payload takes the next non-empty line.
_LEAD = r"^[\s>#*\-_]*(?:\d+[.)]\s*)?"
_STRONG = re.compile(_LEAD + r"(VALUE|ASK)\s*[:：]\s*(.*)$")
_WEAK = re.compile(_LEAD + r"(VALUE|ASK)\s*[:：]\s*(.*)$", re.IGNORECASE)
_INLINE = re.compile(r"(?<![A-Za-z0-9_])(VALUE|ASK)\s*[:：]\s*(.*)$")
_WRAPPERS = " \t`'\"*_"
_VERSION = re.compile(r"^\d+(?:\.\d+)+$")


def parse_reply(text):
    """Return (kind, payload) from the reply's directive; kind is "VALUE", "ASK" or None."""
    lines = [raw.replace("**", "").replace("`", "").strip().strip("_")
             for raw in (text or "").splitlines()]
    for pattern in (_STRONG, _WEAK, _INLINE):
        found = None
        for index, line in enumerate(lines):
            match = pattern.match(line) if pattern is not _INLINE else pattern.search(line)
            if match:
                found = (index, match)
        if found:
            index, match = found
            payload = match.group(2).strip().strip(_WRAPPERS)
            if not payload:
                payload = next((ln.strip(_WRAPPERS) for ln in lines[index + 1:]
                                if ln.strip(_WRAPPERS)), "")
            return match.group(1).upper(), payload
    return None, ""


def _token_pattern(value):
    # A value must stand alone: `3.1` must not match inside `3.12`, `media.thumbs` must not match
    # inside `media.thumbs.v2`, and `ROUND_UP` must not match inside `ROUND_HALF_UP`. It may follow
    # a namespace or a path (`decimal.ROUND_HALF_EVEN`, `s3://bucket`, `origin/main`), a number
    # may carry a unit glued on (`35MB`, `850ms`), a version a `python` or `v` prefix and a patch or
    # wildcard (`python3.12`, `v3.12`, `3.12.x`), and a full stop that ends a sentence is allowed.
    prefix, suffix = "", ""
    if value.isdigit():
        suffix = r"(?:ms|s|sec|d|mb|mib)?"
    elif _VERSION.match(value):
        prefix, suffix = r"(?:python|py|v)?", r"(?:\.(?:x|\d+))?"
    return re.compile(
        r"(?<![A-Za-z0-9_\-])" + prefix + re.escape(value) + suffix
        + r"(?![A-Za-z0-9_\-]|[./][A-Za-z0-9])",
        re.IGNORECASE,
    )


def _spans(text, reading):
    return [m.span() for token in [reading["value"], *reading.get("aliases", [])]
            for m in _token_pattern(token).finditer(text or "")]


def names_value(text, reading):
    """True when `text` names this reading: its value or an alias as a token, or an exact alias
    as the whole text (for punctuation such as `;`, which cannot be matched as a token)."""
    bare = (text or "").strip(_WRAPPERS)
    if bare.lower() in {alias.lower() for alias in reading.get("exact_aliases", [])}:
        return True
    return any(_token_pattern(token).search(text or "")
               for token in [reading["value"], *reading.get("aliases", [])])


def named_readings(payload, readings):
    """The readings a VALUE payload names, after two tie-breaks that follow what a reader would
    conclude: a reading matched only inside a longer match of another is dropped ("UTF-8 with BOM"
    names utf-8-sig, not utf-8), and if several remain, a parenthetical aside is ignored ("6
    (replaces 3)" names 6)."""
    named = [name for name, reading in readings.items() if names_value(payload, reading)]
    if len(named) > 1:
        spans = {name: _spans(payload, readings[name]) for name in named}
        named = [name for name in named if not spans[name] or not all(
            any(a <= s and e <= b and (a, b) != (s, e)
                for other in named if other != name for a, b in spans[other])
            for s, e in spans[name])]
    if len(named) > 1:
        bare = re.sub(r"\([^()]*\)", " ", payload)
        remaining = [name for name in named if names_value(bare, readings[name])]
        if len(remaining) == 1:
            named = remaining
    return named


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
        named = named_readings(payload, readings)
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
