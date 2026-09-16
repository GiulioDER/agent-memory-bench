"""Consumer-boundary proof for the preregistered official-016 oracle ceiling.

Red proof, 2026-09-16: against preregistration commit ``10213c4`` the exact command below exited
2 because ``oracle_ceiling_paired`` was not an accepted instruction variant. The assertion on the
return code therefore failed before implementation at the real CLI boundary. The test protects the
frozen roster, session count, control instruction size and selected oracle catalog digest.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from adapters.oracle_memory.adapter import OracleMemoryAdapter
from scripts import pilot
from scripts.validate_run_setup import check_oracle_ceiling_pair

ROOT = Path(__file__).resolve().parents[1]
TASKS = (
    "ts-base36-id,ts-bom-merge,ts-golden-regen,ts-ignore-gen,ts-legacy-hash,"
    "ts-mig-name,ts-schema-additive,ts-semver-pin,ts-tz-utc"
)
CATALOG_SHA256 = "322cd2331c8b1c6ed0e01eb293f6dd562088a016c6b31c25d304efe46ef5dad6"
PAIRED_ARMS = ("recall_graph_fulltools_protocol", "oracle_memory")


def test_official016_dry_run_builds_the_frozen_oracle_pair() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.pilot",
            "--dry-run",
            "--run-id",
            "official-016-recall-oracle-ceiling-paired-superseded",
            "--arms",
            "recall_graph_fulltools_protocol,oracle_memory",
            "--tasks",
            TASKS,
            "--seeds",
            "5",
            "--model",
            "deepseek/deepseek-v4-flash",
            "--memory-instruction",
            "oracle_ceiling_paired",
            "--corpus-root",
            str(ROOT / "corpus" / "conditions" / "superseded" / "seed-1"),
            "--condition",
            "superseded",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "['recall_graph_fulltools_protocol', 'oracle_memory']" in output
    assert "recall_graph_fulltools_protocol instruction  3924 bytes" in output
    assert "oracle_memory instruction     0 bytes" in output
    assert f"oracle catalog {CATALOG_SHA256}" in output
    assert "tasks  9:" in output
    assert "would run 90 session(s)" in output


def test_official016_roster_guard_rejects_reordering_and_task_drift() -> None:
    frozen_tasks = [SimpleNamespace(task_id=task_id) for task_id in TASKS.split(",")]

    pilot.validate_oracle_ceiling_pair(
        "oracle_ceiling_paired",
        PAIRED_ARMS,
        tasks=frozen_tasks,
        condition="superseded",
    )
    with pytest.raises(ValueError, match="in that order"):
        pilot.validate_oracle_ceiling_pair(
            "oracle_ceiling_paired", tuple(reversed(PAIRED_ARMS))
        )
    with pytest.raises(ValueError, match="frozen nine tasks"):
        pilot.validate_oracle_ceiling_pair(
            "oracle_ceiling_paired", PAIRED_ARMS, tasks=frozen_tasks[:-1]
        )


def test_oracle_adapter_receives_the_validated_selected_catalog(tmp_path) -> None:
    wanted = set(TASKS.split(","))
    tasks = [task for task in pilot.discover_tasks() if task.task_id in wanted]
    corpus_root = ROOT / "corpus" / "conditions" / "superseded" / "seed-1"
    catalog = pilot.load_oracle_ceiling_catalog(corpus_root, tasks)
    static = tmp_path / "static.md"
    static.write_text("# Static task context\n", encoding="utf-8")

    adapter = pilot.adapter_for(
        "oracle_memory",
        {"claude_md": static},
        tmp_path / "staging",
        pilot.memory_instructions("oracle_ceiling_paired", PAIRED_ARMS),
        catalog,
    )

    assert isinstance(adapter, OracleMemoryAdapter)
    assert adapter.catalog.digest == CATALOG_SHA256


def test_setup_gate_verifies_the_frozen_oracle_identity() -> None:
    texts = pilot.memory_instructions("oracle_ceiling_paired", PAIRED_ARMS)
    wanted = set(TASKS.split(","))
    tasks = [task for task in pilot.discover_tasks() if task.task_id in wanted]
    catalog = pilot.load_oracle_ceiling_catalog(
        ROOT / "corpus" / "conditions" / "superseded" / "seed-1", tasks
    )
    env = {
        "memory_instruction": "oracle_ceiling_paired",
        "oracle_ceiling_pair": pilot.oracle_ceiling_pair_metadata(texts, catalog),
        "shared_tool_prefix_groups": [],
    }

    assert check_oracle_ceiling_pair(env).ok is True
    env["oracle_ceiling_pair"]["catalog_sha256"] = "0" * 64
    assert check_oracle_ceiling_pair(env).ok is False
