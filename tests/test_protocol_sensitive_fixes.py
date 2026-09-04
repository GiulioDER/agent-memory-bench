"""The three protocol-sensitive fixes landed 2026-08-29.

Each changes a number a frozen preregistration is stated in terms of, so each is pinned here and
the break is recorded in docs/audit/2026-08-29-protocol-change-record.md.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from harness.costs import ArmCosts, ModelPricing
from harness.tasks import discover_tasks, run_checker

REPO_ROOT = Path(__file__).resolve().parents[1]


# ------------------------------------------------------------- checker crash is a graded failure


def test_a_checker_that_raises_grades_as_failure(monkeypatch, tmp_path):
    """It must not propagate: `runner` would make it an error record and `gate` would then
    discard the whole paired cell, taking every other arm's paid session with it."""

    import harness.tasks as tasks_mod

    task = next(iter(discover_tasks()))

    def exploding_loader(_path, _name):
        def check(_workdir, _oracle_dir):
            raise UnicodeDecodeError("utf-8", b"\x92", 0, 1, "invalid start byte")

        return check

    monkeypatch.setattr(tasks_mod, "_load_callable", exploding_loader)
    ok, verdict = run_checker(task, tmp_path)

    assert ok is False
    assert "checker raised" in verdict
    assert "UnicodeDecodeError" in verdict


def test_a_missing_checker_still_raises(monkeypatch, tmp_path):
    """A fault in the INSTRUMENT must still stop the run rather than score every session failed."""

    import harness.tasks as tasks_mod

    task = next(iter(discover_tasks()))

    def missing_loader(_path, _name):
        raise AttributeError("defines no check()")

    monkeypatch.setattr(tasks_mod, "_load_callable", missing_loader)
    with pytest.raises(AttributeError):
        run_checker(task, tmp_path)


# ----------------------------------------------------------------- retry-cap grader is not flaky

_CLIENT = '''"""Feed fetching for the syncer."""

import random
import time


class TransportError(Exception):
    """Raised by a transport when a fetch attempt fails."""


def fetch(url, transport, sleep=time.sleep):
    for attempt in range(8):
        try:
            return transport(url)
        except TransportError:
            if attempt == 7:
                raise
            sleep(%s)
    raise TransportError("unreachable")
'''

_DRIVER = REPO_ROOT / "oracles" / "ts-retry-cap" / "driver.py"


def _grade(delay_expression: str) -> int:
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "client.py").write_text(_CLIENT % delay_expression, encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(_DRIVER)], cwd=td, capture_output=True, text=True, check=False
        ).returncode


@pytest.mark.parametrize(
    "style",
    [
        "min(30.0, 2.0**attempt) + random.uniform(0.0, 1.0)",          # committed informed ref
        "random.uniform(0.0, min(30.0, 2.0**attempt))",                # AWS full jitter
        "min(30.0, 2.0**attempt) / 2 + random.uniform(0.0, min(30.0, 2.0**attempt) / 2)",
    ],
)
def test_every_correct_jitter_style_is_accepted(style):
    """Full jitter used to fail about 40% of the time: only the last two sleeps have a cap above
    20, so `max(delays) >= 20` on one run was a statement about one draw, not the code."""

    assert _grade(style) == 0, f"grader rejected a correct implementation: {style}"


@pytest.mark.parametrize(
    "style", ["1", "0.1 * (attempt + 1)"]
)
def test_the_grader_still_rejects_a_sleep_that_never_grows(style):
    """The pooling must not cost the check its discriminating power."""

    assert _grade(style) != 0, f"grader accepted a non-backoff implementation: {style}"


# --------------------------------------------------------------------- cache-aware cost pricing


def _pricing(**kwargs) -> ModelPricing:
    return ModelPricing(
        model="m", usd_per_mtok_input=1.0, usd_per_mtok_output=2.0, as_of="2026-08-29", **kwargs
    )


def test_pricing_without_a_cache_rate_is_unchanged():
    """Callers that know no split, and providers publishing no cache rate, get the old answer."""

    p = _pricing()
    assert p.usd(1_000_000, 1_000_000) == pytest.approx(3.0)
    assert p.priced_cache_separately is False


def test_cache_reads_are_charged_at_their_own_rate():
    p = _pricing(usd_per_mtok_cache_read=0.1)
    assert p.priced_cache_separately is True
    # All input served from cache.
    assert p.usd(1_000_000, 0, cache_read_tokens=1_000_000) == pytest.approx(0.1)
    # Half cached: 500k fresh at 1.0 + 500k cached at 0.1.
    assert p.usd(1_000_000, 0, cache_read_tokens=500_000) == pytest.approx(0.55)


def test_cache_creation_can_be_dearer_than_fresh_input():
    p = _pricing(usd_per_mtok_cache_creation=1.25)
    assert p.usd(1_000_000, 0, cache_creation_tokens=400_000) == pytest.approx(0.6 + 0.5)


def test_a_split_larger_than_the_total_is_refused():
    """input_tokens is the SUM of the classes, so this combination is incoherent, not merely odd."""

    with pytest.raises(ValueError, match="exceed the total input"):
        _pricing().usd(100, 0, cache_read_tokens=200)


def test_the_arm_ledger_carries_the_split_into_its_estimate():
    costs = ArmCosts(
        arm="recall",
        session_input_tokens=1_000_000,
        session_output_tokens=0,
        session_cache_read_tokens=680_000,
    )
    p = _pricing(usd_per_mtok_cache_read=0.1)
    # 320k fresh at 1.0 + 680k cached at 0.1
    assert costs.estimate_usd(p) == pytest.approx(0.388)


def test_the_artifact_records_the_prices_that_produced_its_dollars():
    """Recovering the basis previously meant reverse-solving from two arms' rounded totals, and
    the two published runs turned out to have used different rates without saying so."""

    costs = ArmCosts(arm="recall", session_input_tokens=1_000, session_output_tokens=10)
    out = costs.to_dict(_pricing(usd_per_mtok_cache_read=0.1))
    assert out["usd_per_mtok_input"] == 1.0
    assert out["usd_per_mtok_output"] == 2.0
    assert out["usd_per_mtok_cache_read"] == 0.1
    assert out["priced_cache_separately"] is True
