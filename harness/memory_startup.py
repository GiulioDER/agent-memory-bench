"""Recovering a cell from a transient memory-server startup failure, instead of discarding it.

harness/gate.py is right that a session whose memory surface never appeared is not evidence and
must be discarded. What it cannot do is get the cell back, and in pilot-004 that cost nine of
seventy-two paired cells: eight recall sessions reported a recall server with status "failed" and
an EMPTY mcp_server_errors list, so the run knew the server had not started and could not say why.
Those eight sit at positions 4, 5, 7, 9, 13, 34, 36 and 37 of the seventy-two recall sessions in
run order, in two bursts, with none in the last thirty-four. A failure that clusters in time and
not on tasks is a transient, and a transient is worth retrying.

The arithmetic is what makes this blocking rather than tidy. Eight of seventy-two is an 11.1%
per-session startup failure rate. A cell is admitted only when EVERY arm is wired, so on an eight
arm grid carrying five memory servers, and assuming that rate holds and the failures are
independent, a cell admits with probability 0.889 ** 5 = 0.55. The competitor comparison's
admission rule is 95%. The grid cannot be widened until this number moves.

Two mechanisms, and the second one is the dangerous one to get wrong:

- A preflight probe. Speak MCP to the configured server directly, over stdio, before any session
  is launched: initialize, then tools/list. It costs no model tokens, it reproduces the exact
  command, args and env the session will use (the env block REPLACES the environment, so a probe
  that merged os.environ would be a different experiment), and it captures the server's own
  stderr, which is the thing the session record has never contained.

- A bounded retry, triggered by wiring and transport, never by an outcome. `classify_failure` NEVER
  reads record.success, the checker verdict, or anything the model produced. A retry rule that could
  see the outcome would be a rule that reruns losses until they win, and the resulting rate would be
  an artefact of the retry budget. It reads what the admission gate reads, through the gate's own
  helpers, so retry and admission cannot drift into a state where the harness retries a session the
  gate would have admitted, or leaves a discarded one unretried.

  🔁 **Corrected 2026-08-28, and the paragraph above was wrong in exactly the way it warned about.**
  It read "triggered by wiring alone", and the first line of `infrastructure_failure` retried any
  `record.error`, including `claude exceeded timeout_s=600`. A timeout IS something the model did:
  the session ran and did not finish inside a budget every arm was given. It is also arm-correlated,
  because a memory arm's sessions are longer (`pilot-004-placebo`: recall 123.7s mean and 10.1 turns
  against claude_md's 46.8s and 8.1), so the rule handed the slowest arm extra attempts on precisely
  the hard tasks. `classify_failure` now returns a KIND, and `timeout` is outside
  `DEFAULT_RETRYABLE`. The kind is recorded per attempt so the counts are publishable per arm.

Every attempt is recorded under metadata["memory_startup"], and a failed attempt's raw stream is
renamed rather than overwritten, so a recovered cell still carries the evidence of what it
recovered from. A recovered cell must be reported as recovered: it is a cell the old protocol
would have discarded, and hiding that would quietly change what the discard count means.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from .claude_exec import ClaudeExecConfig, ClaudeSessionTimeout, run_claude_case
from .gate import CONNECTED_STATUSES, matching_tools, session_tools
from .host_memory import free_memory_mb
from .schema import SessionRecord

#: The stdio handshake, in the order the specification requires it.
_INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "agent-memory-bench-preflight", "version": "1"},
    },
}
_INITIALIZED = {"jsonrpc": "2.0", "method": "notifications/initialized"}
_TOOLS_LIST = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}


@dataclass(frozen=True)
class McpProbe:
    """What one direct stdio conversation with a configured MCP server found."""

    server: str
    ok: bool
    tools: tuple[str, ...] = ()
    elapsed_ms: float = 0.0
    stderr_tail: str = ""
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "server": self.server,
            "ok": self.ok,
            "tools": list(self.tools),
            "elapsed_ms": round(self.elapsed_ms, 1),
            "stderr_tail": self.stderr_tail,
            "error": self.error,
        }


async def _drain(stream: asyncio.StreamReader, sink: list[bytes]) -> None:
    while True:
        chunk = await stream.read(4096)
        if not chunk:
            return
        sink.append(chunk)


def _tail(chunks: Sequence[bytes], limit: int = 2000) -> str:
    return b"".join(chunks).decode("utf-8", errors="replace")[-limit:]


async def _read_response(stdout: asyncio.StreamReader, wanted_id: int) -> Mapping[str, Any]:
    """Read framed JSON lines until the response with wanted_id arrives.

    Anything else on the stream (notifications, log lines, a chatty banner) is skipped rather than
    treated as an error: a server is allowed to say things we did not ask for.
    """

    while True:
        line = await stdout.readline()
        if not line:
            raise ConnectionError("the server closed stdout before answering")
        text = line.decode("utf-8", errors="replace").strip()
        if not text:
            continue
        try:
            message = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(message, dict) and message.get("id") == wanted_id:
            return message


async def probe_mcp_server(
    command: str,
    args: Sequence[str],
    env: Mapping[str, str],
    *,
    server: str = "",
    timeout_s: float = 30.0,
) -> McpProbe:
    """Start one MCP server exactly as a session would, and ask it for its tools."""

    started = time.perf_counter()
    stderr_chunks: list[bytes] = []
    process: asyncio.subprocess.Process | None = None
    drain: asyncio.Task[None] | None = None
    try:
        process = await asyncio.create_subprocess_exec(
            command,
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            # REPLACES rather than merges, because that is what the MCP client does, and a probe
            # that quietly handed the server a richer environment would pass where a session fails.
            env={str(key): str(value) for key, value in env.items()},
        )
        stdin, stdout = process.stdin, process.stdout
        if stdin is None or stdout is None or process.stderr is None:
            raise ConnectionError("the server was started without the three stdio pipes")
        drain = asyncio.create_task(_drain(process.stderr, stderr_chunks))

        async def conversation() -> tuple[str, ...]:
            for message in (_INITIALIZE, _INITIALIZED, _TOOLS_LIST):
                stdin.write((json.dumps(message) + "\n").encode("utf-8"))
                await stdin.drain()
                if "id" not in message:
                    continue
                response = await _read_response(stdout, int(message["id"]))
                if "error" in response:
                    raise ConnectionError(f"{message['method']} failed: {response['error']}")
                if message is _TOOLS_LIST:
                    listed = (response.get("result") or {}).get("tools") or []
                    return tuple(str(tool.get("name", "")) for tool in listed)
            return ()

        tools = await asyncio.wait_for(conversation(), timeout=timeout_s)
        return McpProbe(
            server=server,
            ok=True,
            tools=tools,
            elapsed_ms=(time.perf_counter() - started) * 1000.0,
            stderr_tail=_tail(stderr_chunks),
        )
    except (OSError, ValueError, ConnectionError, TimeoutError) as error:
        return McpProbe(
            server=server,
            ok=False,
            elapsed_ms=(time.perf_counter() - started) * 1000.0,
            stderr_tail=_tail(stderr_chunks),
            error=f"{type(error).__name__}: {error}",
        )
    finally:
        if process is not None and process.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                process.kill()
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(process.wait(), timeout=5.0)
        if drain is not None:
            drain.cancel()
            with contextlib.suppress(asyncio.CancelledError, TimeoutError):
                await asyncio.wait_for(drain, timeout=2.0)


async def probe_mcp_config(config_path: str | Path, *, timeout_s: float = 30.0) -> list[McpProbe]:
    """Probe every server named in one generated --mcp-config file."""

    path = Path(config_path)
    try:
        servers = json.loads(path.read_text(encoding="utf-8")).get("mcpServers") or {}
    except (OSError, json.JSONDecodeError, AttributeError) as error:
        return [McpProbe(server=str(path), ok=False, error=f"{type(error).__name__}: {error}")]
    return [
        await probe_mcp_server(
            str(entry.get("command", "")),
            [str(item) for item in entry.get("args") or ()],
            {str(key): str(value) for key, value in (entry.get("env") or {}).items()},
            server=name,
            timeout_s=timeout_s,
        )
        for name, entry in servers.items()
    ]


#: Failure kinds, and which of them a retry may act on.
#:
#: ⚠️ ``timeout`` is deliberately NOT retryable, and it used to be. This module's docstring said the
#: retry was "triggered by wiring alone" and that it "NEVER reads record.success, the checker
#: verdict, or anything the model did", while the first line of `infrastructure_failure` retried on
#: any ``record.error`` at all, including `claude exceeded timeout_s=600`. A timeout is something
#: the model did: it ran and did not finish inside the budget every arm was given. It is also not
#: evenly distributed across arms, because a memory arm's sessions are longer, so a rule that
#: retries it hands extra attempts to whichever arm is slowest, on exactly the hard tasks.
WIRING = "wiring"
TRANSPORT = "transport"
TIMEOUT = "timeout"
DEFAULT_RETRYABLE = frozenset({WIRING, TRANSPORT})


def classify_failure(
    record: SessionRecord, tool_prefixes: Sequence[str] = ()
) -> tuple[str | None, str | None]:
    """``(kind, reason)`` for one finished session, or ``(None, None)`` when it is evidence.

    Three kinds, because they deserve three different responses:

    - ``wiring``: the arm's memory surface never appeared. The experiment did not happen. Retry.
    - ``transport``: the provider refused or dropped the connection (HTTP 402, connection lost).
      The experiment did not happen either, and it is arm-independent. Retry.
    - ``timeout``: the session ran and did not finish. That is a RESULT. Do not retry it; the gate
      still discards it, and the discard is published with this kind attached so a reader can see
      which arm ran out of clock.

    None of the three reads ``record.success``, ``metadata["checker"]``, or any tool call.
    """

    if record.error:
        if record.metadata.get("timed_out") or "ClaudeSessionTimeout" in record.error:
            return TIMEOUT, f"the session ran out of its wall-clock budget: {record.error}"
        return TRANSPORT, f"the session did not complete: {record.error}"
    if not record.metadata.get("init_present", True):
        return WIRING, "no system/init event: the session's tool surface was never observed"
    if not tool_prefixes:
        return None, None
    return _wiring_reason(record, tool_prefixes)


def infrastructure_failure(record: SessionRecord, tool_prefixes: Sequence[str] = ()) -> str | None:
    """Why this session is not evidence. Kept for callers that do not need the kind."""

    _kind, reason = classify_failure(record, tool_prefixes)
    return reason


def _wiring_reason(
    record: SessionRecord, tool_prefixes: Sequence[str]
) -> tuple[str | None, str | None]:
    tools = session_tools(record)
    raw_servers = record.metadata.get("mcp_servers")
    servers = (
        raw_servers
        if isinstance(raw_servers, Sequence) and not isinstance(raw_servers, str)
        else []
    )
    raw_errors = record.metadata.get("mcp_server_errors")
    errors = (
        raw_errors
        if isinstance(raw_errors, Sequence) and not isinstance(raw_errors, str)
        else []
    )
    for prefix in tool_prefixes:
        if not matching_tools(tools, prefix):
            return WIRING, f"no tool matching {prefix!r} in the session tool list"
    if errors:
        return WIRING, f"MCP servers were skipped at startup: {list(errors)}"
    for item in servers:
        if isinstance(item, Mapping):
            status = str(item.get("status", "")).lower()
            if status not in CONNECTED_STATUSES:
                return WIRING, f"MCP server {item.get('name')!r} was {status!r}, not connected"
    return None, None


def _preserve_stream(stream_dir: str | Path | None, name: object, attempt: int) -> str | None:
    """Rename a failed attempt's raw stream so the next attempt cannot overwrite it."""

    if stream_dir is None or not isinstance(name, str) or not name:
        return None
    source = Path(stream_dir) / name
    if not source.is_file():
        return None
    kept = source.with_name(f"{name.removesuffix('.jsonl.gz')}.attempt{attempt}.jsonl.gz")
    try:
        kept.unlink(missing_ok=True)
        source.rename(kept)
    except OSError:
        return None
    return kept.name


def _failure_record(row: Mapping[str, Any], arm: str, error: BaseException) -> SessionRecord:
    return SessionRecord(
        task_id=str(row["task_id"]),
        arm=arm,
        seed=int(row.get("seed", 0)),
        success=False,
        user_input=str(row.get("user_input", "")),
        error=f"{type(error).__name__}: {error}",
        # Read by classify_failure, so a timeout is recognised as an outcome rather than as
        # infrastructure even when the error text is reformatted later.
        metadata={"timed_out": isinstance(error, ClaudeSessionTimeout)},
    )


async def run_with_memory_startup_retry(
    row: Mapping[str, Any],
    arm: str,
    config: ClaudeExecConfig,
    *,
    tool_prefixes: Sequence[str] = (),
    attempts: int = 3,
    backoff_s: float = 2.0,
    probe_config: str | Path | None = None,
    probe_min_free_mb: float = 0.0,
    retryable: frozenset[str] = DEFAULT_RETRYABLE,
    runner: Callable[..., Awaitable[SessionRecord]] = run_claude_case,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> SessionRecord:
    """Run one session, retrying only while its treatment failed to wire up.

    attempts=1 is the pre-existing behaviour exactly: one session, no probe, no retry.

    ``retryable`` names which failure KINDS earn another attempt. The default excludes ``timeout``,
    which is an outcome rather than a wiring fault; pass ``DEFAULT_RETRYABLE | {TIMEOUT}`` only with
    a preregistration that says so and an arm-by-arm count of how often it fired, because a session
    budget binds the slowest arm first.
    """

    if attempts < 1:
        raise ValueError("attempts must be at least one")
    history: list[dict[str, Any]] = []
    last: SessionRecord | None = None
    for attempt in range(1, attempts + 1):
        try:
            record = await runner(row, arm, config)
            kind, reason = classify_failure(record, tool_prefixes)
        except Exception as error:  # noqa: BLE001 - a crashed session becomes an error record; the
            # gate, not the scheduler, decides what the final error means.
            record = _failure_record(row, arm, error)
            kind, reason = classify_failure(record, tool_prefixes)
        stream_name = record.metadata.get("stream_path")
        entry: dict[str, Any] = {
            "attempt": attempt,
            "outcome": reason or "wired",
            "kind": kind,
            "retryable": kind in retryable if kind else False,
        }
        if reason is None:
            if isinstance(stream_name, str):
                entry["stream"] = stream_name
        else:
            if probe_config is not None:
                # The probe starts another server. Below the threshold that is the
                # last thing a starved host needs, so say so instead of doing it.
                free_mb = free_memory_mb()
                if probe_min_free_mb and free_mb is not None and free_mb < probe_min_free_mb:
                    entry["probe_skipped"] = {
                        "reason": "host below the memory threshold",
                        "free_mb": round(free_mb, 1),
                        "required_mb": probe_min_free_mb,
                    }
                else:
                    probes = await probe_mcp_config(probe_config)
                    entry["probe"] = [probe.to_dict() for probe in probes]
            kept = _preserve_stream(config.stream_dir, stream_name, attempt)
            entry["stream"] = kept or (stream_name if isinstance(stream_name, str) else None)
        history.append(entry)
        last = record
        if reason is None:
            break
        if kind not in retryable:
            # Recorded and left alone. The gate still discards it; what changes is that the discard
            # is not quietly converted into another draw of the same arm's dice.
            break
        if attempt < attempts:
            await sleep(backoff_s * attempt)
    if last is None:  # pragma: no cover - the loop body runs at least once
        raise RuntimeError("no attempt was made")
    return replace(
        last,
        metadata={
            **last.metadata,
            "memory_startup": {
                "retry_limit": attempts,
                "attempts_used": len(history),
                "recovered": len(history) > 1 and history[-1]["outcome"] == "wired",
                # Published per arm. An arm that draws extra attempts more often than another is
                # being run under a condition the other is not, whatever the rule says.
                "retryable_kinds": sorted(retryable),
                "final_kind": history[-1]["kind"] if history else None,
                "attempts": history,
            },
        },
    )
