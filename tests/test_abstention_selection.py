"""The screen that decides which tasks carry which of preregistration 005's endpoints.

The boundaries are the whole content here. A task at exactly `bare` = 1.00 can show harm and
(asymptotically) not benefit; at exactly 0.00 the reverse. Getting either boundary inclusive in
the wrong direction would put tasks into a stratum whose endpoint they cannot carry, and the
resulting number would look ordinary.

The drift test is the other half: preregistration 007 lists the three strata by name, and that
record is frozen. If the script and the record ever disagree, one of them has moved and the
selection is no longer the one that was preregistered.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from scripts.select_abstention_tasks import (
    BENEFIT_ONLY,
    DAMAGE_ONLY,
    MIN_OBSERVATIONS,
    SAME_MODEL_RUNS,
    TOO_FEW,
    TWO_SIDED,
    bare_outcomes,
    stratify,
)

REPO = Path(__file__).resolve().parents[1]
RECORD = REPO / "preregistration" / "007-abstention-task-selection.md"


# ---------------------------------------------------------------------------------------
# boundaries
# ---------------------------------------------------------------------------------------


def test_a_task_bare_always_solves_is_damage_only():
    """Mutation: `rate >= 1.0` to `rate > 1.0`. Every ceiling task then lands in TWO_SIDED, whose
    net harm estimate they bias positive without being able to contribute a benefit."""

    assert stratify([True] * 6) == DAMAGE_ONLY


def test_a_task_bare_never_solves_is_benefit_only():
    """Mutation: `rate <= 0.0` to `rate < 0.0`. Floor tasks then bias net harm negative."""

    assert stratify([False] * 6) == BENEFIT_ONLY


def test_a_task_bare_sometimes_solves_carries_the_primary_endpoint():
    assert stratify([True, False, True, False]) == TWO_SIDED
    assert stratify([True] * 5 + [False]) == TWO_SIDED
    assert stratify([False] * 5 + [True]) == TWO_SIDED


def test_too_few_observations_is_not_a_stratum():
    """Mutation: dropping the MIN_OBSERVATIONS guard. One lucky observation would then place a
    task in a stratum, and a rate over n=1 is not a screen."""

    assert stratify([True] * (MIN_OBSERVATIONS - 1)) == TOO_FEW
    assert stratify([]) == TOO_FEW
    assert stratify([True] * MIN_OBSERVATIONS) != TOO_FEW


# ---------------------------------------------------------------------------------------
# drift against the frozen record
# ---------------------------------------------------------------------------------------


def _record_tasks(stratum: str) -> set[str]:
    """Every task id preregistration 007 assigns to one stratum, frozen table plus updates.

    Two row shapes, because the record grows by appending rather than by editing:

        frozen   | `TWO_SIDED` | **5** | ts-atomic-write (0.50), ... |
        update   | `TWO_SIDED` | 5 | **6** | ts-idempotent-run (0.17) |

    Reading only the first would make this test fail the moment a calibration adds a task, which
    would push whoever hit it toward editing the frozen table. Reading both is what lets the
    record stay append-only.
    """

    text = RECORD.read_text(encoding="utf-8")
    frozen = re.search(rf"^\| `{stratum}` \| \*\*\d+\*\* \| (.+?) \|$", text, re.MULTILINE)
    assert frozen, f"007 has no frozen table row for {stratum}"
    tasks = set(re.findall(r"\bts-[a-z0-9\-]+", frozen.group(1)))
    for update in re.finditer(
        rf"^\| `{stratum}` \| \d+ \| \*\*\d+\*\* \| (.+?) \|$", text, re.MULTILINE
    ):
        tasks |= set(re.findall(r"\bts-[a-z0-9\-]+", update.group(1)))
    return tasks


@pytest.mark.skipif(
    not all((REPO / "results" / run / "records.final.jsonl").is_file() for run in SAME_MODEL_RUNS),
    reason="the pilot runs the screen reads are not present in this checkout",
)
def test_the_screen_still_produces_the_strata_the_record_froze():
    """If this fails, the script and preregistration 007 disagree. 007 is frozen, so the script
    has moved, and the selection is no longer the preregistered one."""

    pooled = bare_outcomes(SAME_MODEL_RUNS)
    computed: dict[str, set[str]] = {TWO_SIDED: set(), DAMAGE_ONLY: set(), BENEFIT_ONLY: set()}
    for task_id, outcomes in pooled.items():
        stratum = stratify(outcomes)
        if stratum in computed:
            computed[stratum].add(task_id)

    for stratum in (TWO_SIDED, DAMAGE_ONLY, BENEFIT_ONLY):
        assert computed[stratum] == _record_tasks(stratum), (
            f"{stratum} drifted from preregistration 007: "
            f"script has {sorted(computed[stratum])}, record has {sorted(_record_tasks(stratum))}"
        )


@pytest.mark.skipif(
    not all((REPO / "results" / run / "records.final.jsonl").is_file() for run in SAME_MODEL_RUNS),
    reason="the pilot runs the screen reads are not present in this checkout",
)
def test_the_two_sided_rates_match_the_frozen_record():
    """Preregistration 007 prints a rate beside every TWO_SIDED task, and a committed record's
    numbers are never edited. Mutation: ignoring admission discards, which changes n for seven
    tasks and moves ts-atomic-write's rate off 0.50 while leaving every stratum intact. The strata
    tests would stay green and the record would quietly no longer describe the screen."""

    expected = {
        "ts-atomic-write": 0.50,
        "ts-dedup-order": 0.83,
        "ts-golden-regen": 0.50,
        "ts-manifest-rel": 0.50,
        "ts-mig-name": 0.83,
    }
    pooled = bare_outcomes(SAME_MODEL_RUNS)
    for task_id, stated in expected.items():
        outcomes = pooled[task_id]
        actual = round(sum(outcomes) / len(outcomes), 2)
        assert actual == stated, (
            f"{task_id}: the screen now says {actual}, preregistration 007 says {stated}"
        )


@pytest.mark.skipif(
    not all((REPO / "results" / run / "records.final.jsonl").is_file() for run in SAME_MODEL_RUNS),
    reason="the pilot runs the screen reads are not present in this checkout",
)
def test_the_primary_endpoint_is_known_to_be_underpowered():
    """A tripwire, deliberately pinned to today's number so that it FAILS when the suite improves.

    Adding the mid-band tasks that fix the underpowered primary will turn this red. That is the
    intent: preregistration 007 states the consequence as a measured fact, so the suite growing out
    of it is an event that must reach the record rather than pass unnoticed. Update this number
    only together with a result appended below 007's marker, never on its own.
    """

    pooled = bare_outcomes(SAME_MODEL_RUNS)
    two_sided = [t for t, o in pooled.items() if stratify(o) == TWO_SIDED]
    # 5 on 2026-08-27, then 6 once midband-001 added ts-idempotent-run. Raised here only because
    # the matching result is appended below 007's marker, which is the condition this test's
    # docstring sets. Still short of the 8 that preregistration 005 requires.
    assert len(two_sided) == 6, (
        f"the TWO_SIDED stratum has moved to {len(two_sided)} tasks. If it reached 8, "
        f"preregistration 005's primary endpoint is deliverable and 007's consequence section "
        f"needs a result appended below its marker."
    )
