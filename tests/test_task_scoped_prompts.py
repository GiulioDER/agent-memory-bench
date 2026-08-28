"""Every task gets its OWN static bundle, and a grid that breaks that is refused before it runs.

This exists because of a measured failure. `RecallAdapter.build` caches its prompt at
`staging_root/<namespace>/prompt.md` and writes it only when the file is absent. That is right for
a single-task caller and silently wrong for a grid, whose namespace is constant across tasks: the
first task's static bundle is then served to every other task.

diagnostic-001 ran 152 sessions that way before anyone noticed. All 24 recall tasks received
ts-append-only's README ("# ops metrics ledger") while claude_md, oracle_memory and
recall_prefetch each received their own, so the recall arm's static half was misdirection about a
different repository and three of the five preregistered contrasts were void. Nothing raised: the
sessions ran, the checkers scored them, and the admission gate admitted them.

Cost: $0.364 and 100 minutes of wall clock.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from adapters.recall.adapter import RecallAdapter
from scripts.diagnostic import refuse_shared_prompts

TASKS = ("ts-alpha", "ts-beta", "ts-gamma")


def _adapter(tmp_path: Path, task_id: str) -> RecallAdapter:
    """One adapter per task, exactly as scripts/diagnostic.py builds them."""

    bundle = tmp_path / "cfg" / task_id / "static.md"
    bundle.parent.mkdir(parents=True, exist_ok=True)
    bundle.write_text(f"# notes for {task_id}\n\nthe governing detail of {task_id}\n", "utf-8")
    return RecallAdapter(tmp_path / "adapter", bundle)


def _spec(tmp_path: Path, task_id: str, namespace: str = "ns"):
    return _adapter(tmp_path, task_id).build_for_task(
        tmp_path / "cfg" / task_id / "recall", namespace, task_id, "do the thing"
    )


def test_each_task_receives_its_own_bundle(tmp_path, monkeypatch):
    """Mutation: dropping the build_for_task override so it falls back to the namespace cache.
    THE bug. Every task then reads the first task's notes and nothing raises."""

    monkeypatch.setenv("RECALL_DSN", "postgresql://irrelevant/for-this-test")
    texts = {
        task: Path(_spec(tmp_path, task).append_system_prompt_file).read_text("utf-8")
        for task in TASKS
    }
    for task, text in texts.items():
        assert f"the governing detail of {task}" in text, f"{task} got another task's bundle"
    assert len({*texts.values()}) == len(TASKS)


def test_the_shared_namespace_does_not_collapse_the_prompts(tmp_path, monkeypatch):
    """All three tasks use ONE namespace, which is the condition that triggered the bug."""

    monkeypatch.setenv("RECALL_DSN", "postgresql://irrelevant/for-this-test")
    paths = {task: Path(_spec(tmp_path, task, "one-namespace").append_system_prompt_file) for task in TASKS}
    assert len({str(p) for p in paths.values()}) == len(TASKS), "prompts shared a path"


def test_the_tool_instruction_still_leads_the_prompt(tmp_path, monkeypatch):
    """The one-line instruction goes at the TOP; buried after the bundle it measured a 0% search
    rate, and then the benchmark measures prompt placement rather than retrieval."""

    monkeypatch.setenv("RECALL_DSN", "postgresql://irrelevant/for-this-test")
    text = Path(_spec(tmp_path, "ts-alpha").append_system_prompt_file).read_text("utf-8")
    assert text.startswith("You have a persistent project memory")
    assert text.index("recall_search") < text.index("# notes for ts-alpha")


def test_prompts_are_written_with_unix_line_endings(tmp_path, monkeypatch):
    """scripts/pilot.py writes newline='\\n' and the adapter did not, so diagnostic-001's prompts
    were CRLF where pilot-004's were LF: 7 to 10 bytes per file, in a benchmark that scores
    line-ending tasks."""

    monkeypatch.setenv("RECALL_DSN", "postgresql://irrelevant/for-this-test")
    raw = Path(_spec(tmp_path, "ts-alpha").append_system_prompt_file).read_bytes()
    assert b"\r\n" not in raw


def test_build_still_caches_per_namespace_for_single_task_callers(tmp_path, monkeypatch):
    """Mutation: making build() task scoped too. scripts/pilot.py and scripts/smoke.py call it and
    their behaviour must not move, or pilot-003 and pilot-004 stop being reproducible."""

    monkeypatch.setenv("RECALL_DSN", "postgresql://irrelevant/for-this-test")
    adapter = _adapter(tmp_path, "ts-alpha")
    first = adapter.build(tmp_path / "s1", "ns")
    second = adapter.build(tmp_path / "s2", "ns")
    assert first.append_system_prompt_file == second.append_system_prompt_file


# ---------------------------------------------------------------------------------------
# the grid level refusal
# ---------------------------------------------------------------------------------------


def test_distinct_prompts_per_task_are_accepted():
    refuse_shared_prompts({"recall": {"ts-a": "aaa", "ts-b": "bbb"}, "bare": {}})


def test_one_prompt_shared_by_every_task_is_refused():
    """Mutation: comparing counts with >= instead of !=, or skipping arms whose dict is small.
    This is the shape diagnostic-001 shipped: one hash, twenty four tasks."""

    with pytest.raises(SystemExit) as raised:
        refuse_shared_prompts({"recall": dict.fromkeys((f"ts-{i}" for i in range(24)), "same")})
    message = str(raised.value)
    assert "recall" in message and "1 distinct prompts across 24 tasks" in message


def test_the_refusal_names_the_tasks_that_share_a_prompt():
    with pytest.raises(SystemExit) as raised:
        refuse_shared_prompts({"recall": {"ts-a": "x", "ts-b": "x", "ts-c": "y"}})
    assert "ts-a" in str(raised.value) and "ts-b" in str(raised.value)


def test_an_arm_with_no_prompt_at_all_is_not_refused():
    """`bare` legitimately has no appended prompt; refusing it would block every run."""

    refuse_shared_prompts({"bare": {}})


def test_the_shipped_run_that_failed_is_representable():
    """A regression fixture in the literal shape of results/diagnostic-001, so the refusal cannot
    quietly stop covering the case that produced it."""

    shape = json.loads(
        json.dumps(
            {
                "claude_md": {f"ts-{i}": f"cm{i}" for i in range(24)},
                "oracle_memory": {f"ts-{i}": f"or{i}" for i in range(24)},
                "recall_prefetch": {f"ts-{i}": f"pf{i}" for i in range(24)},
                "recall": dict.fromkeys((f"ts-{i}" for i in range(24)), "one-and-only"),
            }
        )
    )
    with pytest.raises(SystemExit, match="recall"):
        refuse_shared_prompts(shape)
