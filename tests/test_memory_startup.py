"""The retry that turns a wiring failure back into a measurable cell, and its safety property.

Every test below has been watched go red against the named mutation. The one that matters most is
test_a_wired_session_that_failed_the_task_is_never_retried: the whole design rests on the retry
being blind to the outcome, and a mutation that lets it see success would still pass every other
test in this file while quietly turning the benchmark into a machine for rerunning losses.
"""

from __future__ import annotations

import asyncio
import gzip
import json
import sys

import pytest

from harness.claude_exec import ClaudeExecConfig
from harness.memory_startup import (
    infrastructure_failure,
    probe_mcp_config,
    probe_mcp_server,
    run_with_memory_startup_retry,
)
from harness.schema import SessionRecord

PREFIXES = ("mcp__recall__",)
ROW = {"task_id": "ts-demo", "seed": 0, "user_input": "do the thing"}


def _wired(**kwargs) -> SessionRecord:
    metadata = {
        "init_present": True,
        "session_tools": ["Read", "mcp__recall__recall_search"],
        "mcp_servers": [{"name": "recall", "status": "connected"}],
        "mcp_server_errors": [],
        **kwargs.pop("metadata", {}),
    }
    return SessionRecord(
        task_id="ts-demo", arm="recall", seed=0, success=True, metadata=metadata, **kwargs
    )


def _unwired(**kwargs) -> SessionRecord:
    metadata = {
        "session_tools": ["Read"],
        "mcp_servers": [{"name": "recall", "status": "failed"}],
        **kwargs.pop("metadata", {}),
    }
    return _wired(metadata=metadata, **kwargs)


def _config(tmp_path) -> ClaudeExecConfig:
    return ClaudeExecConfig(strict_mcp_config=False, stream_dir=tmp_path)


# ---------------------------------------------------------------------------------------
# infrastructure_failure: the only thing the retry is allowed to see
# ---------------------------------------------------------------------------------------


def test_a_wired_session_is_not_an_infrastructure_failure():
    assert infrastructure_failure(_wired(), PREFIXES) is None


def test_missing_memory_tools_are_an_infrastructure_failure():
    """Mutation: returning None here. The pilot-004 failure stops being detected at all."""

    reason = infrastructure_failure(_unwired(), PREFIXES)
    assert reason is not None and "mcp__recall__" in reason


def test_a_failed_server_with_the_tools_listed_is_still_a_failure():
    """Mutation: checking only the tool list. A server can report failed while a tool name
    survives in the session's declared surface, and that session has no memory layer."""

    record = _wired(metadata={"mcp_servers": [{"name": "recall", "status": "failed"}]})
    assert infrastructure_failure(record, PREFIXES) is not None


def test_skipped_servers_are_a_failure():
    record = _wired(metadata={"mcp_server_errors": ["recall: spawn ENOENT"]})
    assert infrastructure_failure(record, PREFIXES) is not None


def test_a_session_that_never_completed_is_a_failure():
    assert infrastructure_failure(_wired(error="TimeoutError: 600s"), PREFIXES) is not None


def test_a_missing_init_event_is_a_failure_but_an_armless_session_is_not():
    """Mutation: defaulting init_present to False. Then every arm without MCP is retried three
    times for nothing, at three times the cost."""

    assert infrastructure_failure(_wired(metadata={"init_present": False}), PREFIXES) is not None
    assert infrastructure_failure(_wired(), ()) is None


def test_an_unsuccessful_but_wired_session_is_not_an_infrastructure_failure():
    """Mutation: adding `if not record.success: return ...`. This is the p-hacking guard, written
    as a unit test so the mutation cannot land quietly."""

    losing = SessionRecord(
        task_id="ts-demo",
        arm="recall",
        seed=0,
        success=False,
        metadata={
            "init_present": True,
            "session_tools": ["mcp__recall__recall_search"],
            "mcp_servers": [{"name": "recall", "status": "connected"}],
            "checker": "the deliverable is wrong",
        },
    )
    assert infrastructure_failure(losing, PREFIXES) is None


# ---------------------------------------------------------------------------------------
# the retry loop
# ---------------------------------------------------------------------------------------


def _run(**kwargs) -> SessionRecord:
    async def sleep(_seconds: float) -> None:
        return None

    kwargs.setdefault("sleep", sleep)
    return asyncio.run(run_with_memory_startup_retry(**kwargs))


def test_a_wired_first_attempt_runs_exactly_once(tmp_path):
    calls = []

    async def runner(row, arm, config):
        calls.append(arm)
        return _wired()

    record = _run(
        row=ROW, arm="recall", config=_config(tmp_path), tool_prefixes=PREFIXES, runner=runner
    )
    assert len(calls) == 1
    assert record.metadata["memory_startup"]["attempts_used"] == 1
    assert record.metadata["memory_startup"]["recovered"] is False


def test_a_wiring_failure_is_retried_and_the_recovery_is_recorded(tmp_path):
    """Mutation: breaking out of the loop unconditionally. The cell is lost exactly as it was in
    pilot-004, and nothing in the artifact says a retry had been available."""

    outcomes = iter([_unwired(), _wired()])

    async def runner(row, arm, config):
        return next(outcomes)

    record = _run(
        row=ROW, arm="recall", config=_config(tmp_path), tool_prefixes=PREFIXES, runner=runner
    )
    startup = record.metadata["memory_startup"]
    assert startup["attempts_used"] == 2
    assert startup["recovered"] is True
    assert startup["attempts"][0]["outcome"] != "wired"
    assert startup["attempts"][1]["outcome"] == "wired"
    assert infrastructure_failure(record, PREFIXES) is None


def test_a_wired_session_that_failed_the_task_is_never_retried(tmp_path):
    """Mutation: retrying while `not record.success`. THE property this module exists to keep."""

    calls = []

    async def runner(row, arm, config):
        calls.append(arm)
        return SessionRecord(
            task_id="ts-demo",
            arm="recall",
            seed=0,
            success=False,
            metadata={
                "init_present": True,
                "session_tools": ["mcp__recall__recall_search"],
                "mcp_servers": [{"name": "recall", "status": "connected"}],
            },
        )

    record = _run(
        row=ROW, arm="recall", config=_config(tmp_path), tool_prefixes=PREFIXES, runner=runner
    )
    assert len(calls) == 1, "a losing but wired session is evidence, not a rerun"
    assert record.success is False


def test_an_exhausted_budget_returns_the_last_failure_rather_than_a_success(tmp_path):
    """Mutation: returning the first attempt, or inventing a success. Either hides a cell the
    gate must still discard."""

    async def runner(row, arm, config):
        return _unwired()

    record = _run(
        row=ROW,
        arm="recall",
        config=_config(tmp_path),
        tool_prefixes=PREFIXES,
        attempts=3,
        runner=runner,
    )
    startup = record.metadata["memory_startup"]
    assert startup["attempts_used"] == 3
    assert startup["recovered"] is False
    assert infrastructure_failure(record, PREFIXES) is not None


def test_a_raising_runner_becomes_a_retryable_failure_not_a_lost_row(tmp_path):
    attempts = []

    async def runner(row, arm, config):
        attempts.append(1)
        if len(attempts) == 1:
            raise TimeoutError("claude exceeded timeout_s=600")
        return _wired()

    record = _run(
        row=ROW, arm="recall", config=_config(tmp_path), tool_prefixes=PREFIXES, runner=runner
    )
    assert record.metadata["memory_startup"]["attempts_used"] == 2
    assert record.metadata["memory_startup"]["recovered"] is True


def test_attempts_must_be_at_least_one(tmp_path):
    async def runner(row, arm, config):
        return _wired()

    with pytest.raises(ValueError, match="at least one"):
        _run(
            row=ROW,
            arm="recall",
            config=_config(tmp_path),
            tool_prefixes=PREFIXES,
            attempts=0,
            runner=runner,
        )


def test_a_failed_attempts_raw_stream_is_kept_rather_than_overwritten(tmp_path):
    """Mutation: leaving the stream in place. The second attempt writes to the same name, so the
    evidence of what the recovery recovered FROM is silently destroyed."""

    stream = tmp_path / "ts-demo.s0.recall.jsonl.gz"
    seen = []

    async def runner(row, arm, config):
        seen.append(1)
        with gzip.open(stream, "wt", encoding="utf-8") as handle:
            handle.write(json.dumps({"attempt": len(seen)}) + chr(10))
        builder = _unwired if len(seen) == 1 else _wired
        return builder(metadata={"stream_path": stream.name})

    record = _run(
        row=ROW, arm="recall", config=_config(tmp_path), tool_prefixes=PREFIXES, runner=runner
    )
    kept = tmp_path / "ts-demo.s0.recall.attempt1.jsonl.gz"
    assert kept.is_file(), "the failed attempt's stream must survive under its own name"
    assert stream.is_file(), "the recovered attempt keeps the canonical name"
    assert record.metadata["memory_startup"]["attempts"][0]["stream"] == kept.name


def test_the_probe_runs_only_when_an_attempt_failed(tmp_path):
    """Mutation: probing every attempt. That is 288 extra server spawns on a clean run, minutes of
    wall clock bought for nothing."""

    config_path = tmp_path / "recall.mcp.json"
    config_path.write_text(json.dumps({"mcpServers": {}}), encoding="utf-8")

    async def runner(row, arm, config):
        return _wired()

    record = _run(
        row=ROW,
        arm="recall",
        config=_config(tmp_path),
        tool_prefixes=PREFIXES,
        probe_config=config_path,
        runner=runner,
    )
    assert "probe" not in record.metadata["memory_startup"]["attempts"][0]


def test_a_failed_attempt_carries_the_probe_and_the_servers_own_stderr(tmp_path):
    config_path = tmp_path / "recall.mcp.json"
    noisy = "import sys; print('boom: no database', file=sys.stderr)"
    config_path.write_text(
        json.dumps(
            {"mcpServers": {"recall": {"command": sys.executable, "args": ["-c", noisy], "env": {}}}}
        ),
        encoding="utf-8",
    )

    async def runner(row, arm, config):
        return _unwired()

    record = _run(
        row=ROW,
        arm="recall",
        config=_config(tmp_path),
        tool_prefixes=PREFIXES,
        attempts=2,
        probe_config=config_path,
        runner=runner,
    )
    probe = record.metadata["memory_startup"]["attempts"][0]["probe"][0]
    assert probe["ok"] is False
    assert "boom: no database" in probe["stderr_tail"], (
        "capturing the server's own stderr is the whole point: pilot-004 recorded "
        "mcp_server_errors=[] and could not say why the server failed"
    )


# ---------------------------------------------------------------------------------------
# the probe itself
# ---------------------------------------------------------------------------------------


SERVER = """
import json, sys
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    message = json.loads(line)
    if message.get("method") == "initialize":
        print(json.dumps({"jsonrpc": "2.0", "id": message["id"], "result": {}}), flush=True)
    elif message.get("method") == "tools/list":
        result = {"tools": [{"name": "mcp__recall__recall_search"}]}
        print(json.dumps({"jsonrpc": "2.0", "id": message["id"], "result": result}), flush=True)
"""


def test_the_probe_speaks_enough_mcp_to_list_a_healthy_servers_tools():
    probe = asyncio.run(probe_mcp_server(sys.executable, ["-c", SERVER], {}, server="recall"))
    assert probe.ok is True, probe.error
    assert probe.tools == ("mcp__recall__recall_search",)


def test_a_server_that_never_answers_times_out_rather_than_hanging_the_run():
    """Mutation: dropping the wait_for. One wedged server stalls the whole grid."""

    probe = asyncio.run(
        probe_mcp_server(
            "python", ["-c", "import time; time.sleep(30)"], {}, server="recall", timeout_s=1.0
        )
    )
    assert probe.ok is False
    assert "TimeoutError" in (probe.error or "")


def test_a_server_that_cannot_be_started_reports_the_reason():
    probe = asyncio.run(probe_mcp_server("definitely-not-a-real-binary", [], {}, server="recall"))
    assert probe.ok is False
    assert probe.error


def test_an_unreadable_config_probes_to_a_single_named_failure(tmp_path):
    probes = asyncio.run(probe_mcp_config(tmp_path / "absent.json"))
    assert len(probes) == 1 and probes[0].ok is False
