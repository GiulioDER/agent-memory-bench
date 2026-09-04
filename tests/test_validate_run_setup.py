"""The run-setup validator, checked against the two failures that motivated it.

The important tests here are `test_the_confounded_official_002_shape_fails` and
`test_the_haystackless_corpus_shape_fails`. Both use the real numbers from the runs that were
actually wasted, so a future edit that relaxes a threshold past them fails loudly instead of
quietly re-admitting the thing the script exists to catch.

Every guard below was mutation-tested: the check was broken on purpose and the named test watched
to go red. A guard nobody has watched fail has not been tested.
"""

from __future__ import annotations

import json

import pytest

from scripts.validate_run_setup import (
    DEFAULT_MAX_APPENDIX_FRACTION,
    check_appendix_proportion,
    check_corpus_reached,
    check_shared_protocol_identical,
    main,
    validate,
)

SHARED_BASE = 3472

#: official-003, measured live 2026-09-01. The fair shape.
FAIR = {
    "run_id": "official-003-present",
    "arms": ["bare", "placebo", "claude_md", "protocol", "fs_grep", "recall", "mempalace"],
    "memory_instruction": "protocol",
    "sandbox_inside_repo": False,
    "instruction_arms_matched": True,
    "instruction_manifest": {
        "protocol": {"bytes": 3610},
        "fs_grep": {"bytes": 4021},
        "recall": {"bytes": 4207},
        "mempalace": {"bytes": 4325},
        "bare": {"bytes": 0},
    },
    "instruction_excess_bytes": {
        "protocol": 138, "fs_grep": 549, "recall": 735, "mempalace": 853, "bare": 0,
    },
    "ingest": [
        {"arm": "fs_grep", "sessions_offered": 4900},
        {"arm": "mempalace", "sessions_offered": 4900},
    ],
}

#: official-002 under `skill`: recall carried 1,958 excess bytes against mempalace's 853. The
#: run cost 2,181 sessions and its headline finding had to be withdrawn.
CONFOUNDED = json.loads(json.dumps(FAIR)) | {
    "memory_instruction": "skill",
    "instruction_manifest": {
        "protocol": {"bytes": 3610},
        "fs_grep": {"bytes": 4021},
        "recall": {"bytes": SHARED_BASE + 1958},
        "mempalace": {"bytes": 4325},
    },
    "instruction_excess_bytes": {
        "protocol": 138, "fs_grep": 549, "recall": 1958, "mempalace": 853,
    },
}

#: The corpora built without AMB_HAYSTACK: 207 documents where ~4,900 were intended.
HAYSTACKLESS = json.loads(json.dumps(FAIR)) | {
    "ingest": [
        {"arm": "fs_grep", "sessions_offered": 207},
        {"arm": "mempalace", "sessions_offered": 207},
    ]
}


def _by_name(checks):
    return {c.name: c for c in checks}


# --- the two historic failures, which are the whole point -----------------------------------


def test_the_confounded_official_002_shape_fails() -> None:
    """recall at 56% of the protocol must not pass. This is the run that had to be withdrawn."""

    check = check_appendix_proportion(CONFOUNDED, DEFAULT_MAX_APPENDIX_FRACTION)
    assert check.ok is False
    assert "recall" in check.detail


def test_the_haystackless_corpus_shape_fails() -> None:
    """207 documents where 4,900 were intended. 94 sessions were discarded to learn this."""

    check = check_corpus_reached(HAYSTACKLESS, 4000)
    assert check.ok is False
    assert "207" in check.detail


def test_the_fair_shape_passes_every_check() -> None:
    checks = validate(
        FAIR,
        expect_arms=FAIR["arms"],
        expect_instruction="protocol",
    )
    failed = [c for c in checks if c.ok is False]
    assert not failed, [(c.name, c.detail) for c in failed]


def test_the_default_bound_separates_the_two_real_runs() -> None:
    """0.33 is not arbitrary: it sits between the confounded run and the fair one."""

    assert 1958 / SHARED_BASE > DEFAULT_MAX_APPENDIX_FRACTION > 853 / SHARED_BASE


# --- the arithmetic check does not trust the harness flag ------------------------------------


def test_a_mismatched_base_fails_even_when_the_harness_flag_says_matched() -> None:
    """The flag and the arithmetic are separate on purpose, so a disagreement is visible."""

    env = json.loads(json.dumps(FAIR))
    env["instruction_manifest"]["recall"]["bytes"] = 4300  # base becomes 3565, not 3472
    check = check_shared_protocol_identical(env)
    assert check.ok is False
    assert env["instruction_arms_matched"] is True, "the flag still claims a match"


def test_an_arm_with_no_instruction_is_not_an_offender() -> None:
    assert check_shared_protocol_identical(FAIR).ok is True
    assert "bare" not in check_shared_protocol_identical(FAIR).detail


# --- a SKIP is never a PASS ------------------------------------------------------------------


@pytest.mark.parametrize(
    "missing, expected_skip",
    [
        ("ingest", "corpus_reached"),
        ("instruction_manifest", "shared_protocol_identical"),
        ("instruction_arms_matched", "instruction_arms_matched"),
        ("sandbox_inside_repo", "sandbox_outside_repo"),
    ],
)
def test_an_absent_field_skips_rather_than_passes(missing: str, expected_skip: str) -> None:
    """The failure this whole script answers is a missing check rendering as a passing one."""

    env = {k: v for k, v in FAIR.items() if k != missing}
    check = _by_name(validate(env))[expected_skip]
    assert check.ok is None, f"{expected_skip} should not resolve without {missing}"
    assert check.mark == "SKIP"


def test_no_expectation_supplied_skips_rather_than_passes() -> None:
    checks = _by_name(validate(FAIR))
    assert checks["expected_arms"].ok is None
    assert checks["expected_instruction"].ok is None


# --- expectations are the caller's, never inferred -------------------------------------------


def test_a_wrong_roster_fails() -> None:
    check = _by_name(validate(FAIR, expect_arms=["bare", "recall"]))["expected_arms"]
    assert check.ok is False


def test_roster_comparison_ignores_order() -> None:
    shuffled = list(reversed(FAIR["arms"]))
    assert _by_name(validate(FAIR, expect_arms=shuffled))["expected_arms"].ok is True


def test_the_wrong_instruction_variant_fails() -> None:
    check = _by_name(validate(CONFOUNDED, expect_instruction="protocol"))
    assert check["expected_instruction"].ok is False
    assert "skill" in check["expected_instruction"].detail


def test_a_sandbox_inside_the_repo_fails() -> None:
    env = json.loads(json.dumps(FAIR)) | {"sandbox_inside_repo": True}
    assert _by_name(validate(env))["sandbox_outside_repo"].ok is False


# --- the CLI contract --------------------------------------------------------------------


def test_cli_exits_nonzero_on_a_confounded_run(tmp_path, capsys) -> None:
    d = tmp_path / "official-002-present"
    d.mkdir()
    (d / "environment.json").write_text(json.dumps(CONFOUNDED), encoding="utf-8")
    assert main([str(d)]) == 1
    assert "FAIL" in capsys.readouterr().out


def test_cli_exits_zero_on_a_fair_run(tmp_path, capsys) -> None:
    d = tmp_path / "official-003-present"
    d.mkdir()
    (d / "environment.json").write_text(json.dumps(FAIR), encoding="utf-8")
    assert main([str(d), "--expect-instruction", "protocol"]) == 0
    assert "FAIL" not in capsys.readouterr().out


def test_a_named_path_that_does_not_exist_fails(tmp_path) -> None:
    """You asked for this one by name and it is not there. That is a failure, not a clean sheet."""

    assert main([str(tmp_path / "nope")]) == 1


def test_a_run_id_matching_nothing_refuses_rather_than_passing(monkeypatch, tmp_path) -> None:
    """Exit 2, never 0. `--run` matching no condition means nothing was validated at all, and
    the one outcome that must be impossible is an absent artefact reading as a clean one."""

    monkeypatch.setattr("scripts.validate_run_setup.REPO", tmp_path)
    (tmp_path / "results").mkdir()
    assert main(["--run", "no-such-run"]) == 2


def test_cli_says_a_skip_is_not_a_pass(tmp_path, capsys) -> None:
    d = tmp_path / "r"
    d.mkdir()
    (d / "environment.json").write_text(json.dumps({"run_id": "r"}), encoding="utf-8")
    main([str(d)])
    assert "A SKIP is not a pass" in capsys.readouterr().out
