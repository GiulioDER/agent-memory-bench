"""No agent-visible name may spell out the corpus condition.

Invariant: the product namespace and the session working directory carry no condition name, and
the pilot refuses a namespace that does. Failure mode: until 2026-09-26 the working directory was
`<work root>/<run_id>-<condition>/work/...` and the namespace `<namespace>-<condition>`. The
condition reached nearly every session of every arm, controls included, in every run executed on
the host (official-003, Claude Mem, cognee, supermemory), and Graphiti, run in a container, echoed
`amb-graphiti-official-007-superseded` 280 times in its superseded tool outputs. An agent told it is
in `superseded` knows what kind of trap the corpus holds.

Red proof, 2026-09-26, by reverting each production line to its dafe4c10 behaviour:

| mutation | test | intended failure |
|---|---|---|
| `condition_namespace` returns `<namespace>-<condition>` | `test_the_namespace_...` | `AssertionError: bench-superseded` |
| `session_work_root` joins the raw run id | `test_the_session_work_root_...` | `.../agent-memory-bench-work/official-003-absent` |
| the pilot guard removed | `test_the_pilot_refuses_...` | `assert 0 != 0` (the pilot accepted it) |
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from harness.corpus_names import condition_namespace, names_a_condition, work_dir_name
from harness.damage import CORPUS_CONDITIONS

REPO = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("condition", CORPUS_CONDITIONS)
def test_the_namespace_does_not_name_its_condition(condition):
    namespace = condition_namespace("bench", condition)
    assert names_a_condition(namespace, CORPUS_CONDITIONS) is None, namespace
    assert namespace.startswith("bench-")
    assert namespace == condition_namespace("bench", condition), "must be deterministic"


def test_each_condition_still_gets_its_own_namespace():
    """One tenant per condition: a shared one would let one condition's plants leak into another."""

    names = {condition_namespace("bench", c) for c in CORPUS_CONDITIONS}
    assert len(names) == len(CORPUS_CONDITIONS)


@pytest.mark.parametrize("condition", CORPUS_CONDITIONS)
def test_the_session_work_root_does_not_name_its_condition(condition):
    from scripts.pilot import session_work_root

    root = session_work_root(None, f"official-003-{condition}")
    assert names_a_condition(str(root), CORPUS_CONDITIONS) is None, root
    assert root.name == work_dir_name(f"official-003-{condition}")
    # An operator's explicit --work-root is theirs and is used as given.
    assert session_work_root("/tmp/mine", "x") == Path("/tmp/mine")


def test_the_arm_directory_does_not_name_its_arm():
    """A `placebo` session saw `placebo` in its own working directory, which weakens the control.

    Red proof, 2026-09-26: with `arm_dir_name` returning the arm unchanged, this failed on
    `AssertionError: ('bare', 'bare')`.
    """

    from harness.corpus_names import arm_dir_name
    from scripts.pilot import ARMS

    names = {arm: arm_dir_name(arm) for arm in ARMS}
    for arm, name in names.items():
        assert arm not in name, (arm, name)
        assert "placebo" not in name and "bare" not in name and "claude" not in name
    assert len(set(names.values())) == len(names), "two arms would share a working directory"


def test_the_pilot_refuses_a_namespace_that_names_its_condition():
    refused = subprocess.run(
        [sys.executable, "-m", "scripts.pilot", "--run-id", "t-1",
         "--namespace", "bench-superseded", "--dry-run"],
        cwd=REPO, capture_output=True, text=True, check=False,
    )
    assert refused.returncode != 0
    assert "names the corpus condition 'superseded'" in refused.stdout + refused.stderr
