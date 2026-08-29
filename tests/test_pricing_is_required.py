"""Run prices are a required measurement input, not an argparse default.

`pilot-004-placebo` was launched without the flags, took `scripts/pilot.py`'s defaults
(0.05866/0.11732) and was published beside `pilot-003-deepseek`, which used the frozen
0.0574/0.1148. Nothing in either artifact said so. See
docs/audit/2026-08-29-protocol-change-record.md.
"""

from __future__ import annotations

import argparse

import pytest

from harness.costs import add_pricing_arguments, pricing_from_args


def _parse(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    add_pricing_arguments(parser)
    return parser.parse_args(argv)


def test_a_run_without_prices_refuses_rather_than_guessing():
    args = _parse([])
    with pytest.raises(SystemExit) as excinfo:
        pricing_from_args(args, model="m")

    message = str(excinfo.value)
    assert "--price-in" in message
    assert "--price-out" in message
    assert "--price-as-of" in message
    # The refusal must be actionable: it names the frozen rates so a protocol-matching rerun
    # can copy them instead of hunting through preregistration 002.
    assert "0.0574" in message and "0.1148" in message


@pytest.mark.parametrize(
    "argv",
    [
        ["--price-out", "0.1148", "--price-as-of", "2026-08-22"],
        ["--price-in", "0.0574", "--price-as-of", "2026-08-22"],
        ["--price-in", "0.0574", "--price-out", "0.1148"],
    ],
)
def test_a_partial_price_set_refuses_too(argv):
    """A date without prices, or prices without a date, is not a usable basis."""

    with pytest.raises(SystemExit):
        pricing_from_args(_parse(argv), model="m")


def test_explicit_prices_build_the_table():
    args = _parse(["--price-in", "0.0574", "--price-out", "0.1148", "--price-as-of", "2026-08-22"])
    pricing = pricing_from_args(args, model="deepseek/deepseek-v4-flash", source="src")

    entry = pricing["deepseek/deepseek-v4-flash"]
    assert entry.usd_per_mtok_input == 0.0574
    assert entry.usd_per_mtok_output == 0.1148
    assert entry.as_of == "2026-08-22"
    assert entry.source == "src"
    # No cache rate given, so cache reads fall back to the fresh rate AND the artifact says so.
    assert entry.priced_cache_separately is False


def test_the_cache_rates_are_reachable_from_the_cli():
    """ModelPricing grew cache-aware pricing in 63ce4b5; no runner could pass it until now."""

    args = _parse(
        [
            "--price-in", "0.0574",
            "--price-out", "0.1148",
            "--price-as-of", "2026-08-22",
            "--price-cache-read", "0.00574",
        ]
    )
    entry = pricing_from_args(args, model="m")["m"]
    assert entry.usd_per_mtok_cache_read == 0.00574
    assert entry.priced_cache_separately is True
    # 1M input of which 800k cached: 200k fresh at 0.0574 + 800k cached at 0.00574.
    assert entry.usd(1_000_000, 0, cache_read_tokens=800_000) == pytest.approx(
        (200_000 * 0.0574 + 800_000 * 0.00574) / 1_000_000
    )


def test_no_runner_still_carries_a_default_price():
    """The defaults disagreed with each other and with the frozen rates; none may come back."""

    import pathlib

    scripts = pathlib.Path(__file__).resolve().parents[1] / "scripts"
    offenders = []
    for path in sorted(scripts.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for flag in ("--price-in", "--price-out", "--price-as-of"):
            for line in text.splitlines():
                if flag in line and "default=" in line:
                    offenders.append(f"{path.name}: {line.strip()}")
    assert not offenders, "a price default came back: " + "; ".join(offenders)


def test_the_abstention_suite_forwards_prices_and_refuses_early():
    """It prices nothing itself, but each condition ingests before pilot runs.

    Letting pilot refuse would be correct and far too late: the suite would spend the embedding
    cost of every condition before dying on a missing flag.
    """

    import pathlib

    source = (
        pathlib.Path(__file__).resolve().parents[1] / "scripts" / "abstention.py"
    ).read_text(encoding="utf-8")

    assert "add_pricing_arguments(parser)" in source
    # The chosen rates reach the child, rather than the child re-deciding.
    for flag in ("--price-in", "--price-out", "--price-as-of", "--price-cache-read"):
        assert flag in source, f"{flag} is not forwarded to pilot"

    # Refusal is BEHAVIOURAL, not positional: run_condition is defined above main(), so where the
    # check sits in the file says nothing about when it runs. Drive the command instead and
    # require it to refuse before it can have assembled a corpus or ingested anything.
    import subprocess
    import sys

    repo = pathlib.Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "-m", "scripts.abstention",
         "--run-id", "pricing-refusal-probe", "--arms", "bare", "--conditions", "absent"],
        cwd=str(repo), capture_output=True, text=True, timeout=120, check=False,
    )
    output = result.stdout + result.stderr
    assert "missing required pricing" in output, output[-400:]
    assert "[absent]" not in output, "the suite began work before refusing"
    assert not (repo / "results" / "pricing-refusal-probe-absent").exists()
