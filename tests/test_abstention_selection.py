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


def _record_counts() -> dict[str, int]:
    """The FINAL stratum counts preregistration 007 states, from its n = 12 update table.

    That table carries counts rather than task names:

        | `TWO_SIDED` | 5 | 6 | **7** |

    so this reads the last bold cell of each row. The earlier tables stay in the record as
    history and are deliberately not read: `resolution-001` replaced their rates rather than
    pooling with them, which is what preregistration 009 specified.
    """

    text = RECORD.read_text(encoding="utf-8")
    counts = {}
    for stratum in (TWO_SIDED, DAMAGE_ONLY, BENEFIT_ONLY):
        rows = re.findall(rf"^\| `{stratum}` \|(.+)\|$", text, re.MULTILINE)
        assert rows, f"007 has no table row for {stratum}"
        final = re.findall(r"\*\*(\d+)\*\*", rows[-1])
        assert final, f"007's last {stratum} row has no bold final count: {rows[-1]!r}"
        counts[stratum] = int(final[-1])
    return counts


#: The `TWO_SIDED` membership `resolution-001` produced, pinned so a change to the screen or to
#: the discard handling cannot move a task in or out unnoticed. Rates are from that run at n = 12.
TWO_SIDED_AT_N12 = {
    "ts-atomic-write": 0.17,
    "ts-bom-merge": 0.83,
    "ts-cli-exitcode": 0.08,
    "ts-golden-regen": 0.55,
    "ts-idempotent-run": 0.09,
    "ts-legacy-hash": 0.91,
    "ts-mig-name": 0.33,
}


@pytest.mark.skipif(
    not all((REPO / "results" / run / "records.final.jsonl").is_file() for run in SAME_MODEL_RUNS),
    reason="the run the screen reads is not present in this checkout",
)
def test_the_screen_produces_the_counts_the_record_states():
    """If this fails, the script and preregistration 007's final table disagree, and since the
    record is append-only it is the script that moved."""

    pooled = bare_outcomes(SAME_MODEL_RUNS)
    computed = {TWO_SIDED: 0, DAMAGE_ONLY: 0, BENEFIT_ONLY: 0}
    for outcomes in pooled.values():
        stratum = stratify(outcomes)
        if stratum in computed:
            computed[stratum] += 1
    assert computed == _record_counts(), (
        f"strata drifted from preregistration 007: script {computed}, record {_record_counts()}"
    )


@pytest.mark.skipif(
    not all((REPO / "results" / run / "records.final.jsonl").is_file() for run in SAME_MODEL_RUNS),
    reason="the run the screen reads is not present in this checkout",
)
def test_the_two_sided_membership_and_rates_are_pinned():
    """Mutation: ignoring admission discards. resolution-001 dropped 12 cells to provider
    connection failures, and counting them as task failures would move rates without necessarily
    moving any stratum, so a counts-only test would stay green while the numbers rotted."""

    pooled = bare_outcomes(SAME_MODEL_RUNS)
    two_sided = {t for t, o in pooled.items() if stratify(o) == TWO_SIDED}
    assert two_sided == set(TWO_SIDED_AT_N12), (
        f"TWO_SIDED membership moved: script {sorted(two_sided)}, "
        f"pinned {sorted(TWO_SIDED_AT_N12)}"
    )
    for task_id, stated in TWO_SIDED_AT_N12.items():
        outcomes = pooled[task_id]
        actual = round(sum(outcomes) / len(outcomes), 2)
        assert actual == stated, f"{task_id}: screen says {actual}, resolution-001 said {stated}"


def test_the_historical_tables_still_read_as_history():
    """The frozen n=4-to-6 table must keep saying 5, because it is evidence of what was believed
    then. A record that gets silently updated when the world moves cannot show what anyone
    believed beforehand."""

    text = RECORD.read_text(encoding="utf-8")
    assert re.search(rf"^\| `{TWO_SIDED}` \| \*\*5\*\* \|", text, re.MULTILINE), (
        "007's frozen table no longer says TWO_SIDED was 5; the frozen section was edited"
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
    assert len(two_sided) == 7, (
        f"the TWO_SIDED stratum has moved to {len(two_sided)} tasks. If it reached 8, "
        f"preregistration 005's primary endpoint is deliverable and 007's consequence section "
        f"needs a result appended below its marker."
    )
