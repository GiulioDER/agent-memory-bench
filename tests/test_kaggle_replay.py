"""The replay tasks (preregistration 098, Deviation 3) reproduce the preregistered scores exactly.

Invariant: for every scored model, the replay task's score equals the trust or restraint that the
frozen analysis reported (`results/kaggle-memory-discipline-001/report.json`), with errored items
left out of the denominators exactly as the analysis left them out, and a model with no recorded
run raises instead of being scored. Failure modes caught: an errored item replayed as a wrong
answer (lowers gpt-oss-120b's trust), a lookup that returns the wrong model, and a replay file
that is stale against the generator.

Red proof, 2026-10-09, fresh PYTHONPYCACHEPREFIX each run, each mutation in
scripts/build_kaggle_replay.py or its template, files regenerated, then restored and regenerated
(6 passed after restore). Each failed in the score or identity assertion of
test_replay_reproduces_report, observed:
- `encode` writes an errored item as "0" instead of "-": restraint of
  qwen/qwen3-235b-a22b-instruct-2507 0.8403 against 0.8650.
- template drops `if mark != "-"` (errored items replayed as wrong): trust of openai/gpt-oss-120b
  0.7135 against 0.7446.
- template `_key` returns the first model: key anthropic/claude-haiku-4-5@20251001 returned for
  anthropic/claude-opus-4-5@20251101.
"""

import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
REPORT = json.loads(
    (REPO / "results" / "kaggle-memory-discipline-001" / "report.json").read_text(encoding="utf-8"))
sys.path.insert(0, str(REPO / "scripts"))
import build_kaggle_replay  # noqa: E402

CONDITIONS = {"trust": "TRUST_CONDITIONS", "restraint": "RESTRAINT_CONDITIONS"}


class _Task:
    def __init__(self, fn):
        self.fn = fn

    def __call__(self, *args, **kwargs):
        return self.fn(*args, **kwargs)

    def run(self, llm):  # the notebook's own run line; scoring is checked directly below
        return None


def load(family):
    """Import the generated replay file against a stub kaggle_benchmarks; return (source, module)."""
    stub = types.ModuleType("kaggle_benchmarks")
    stub.task = lambda **kwargs: _Task
    stub.llm = types.SimpleNamespace(model=next(iter(REPORT)))
    path = REPO / "kaggle_memory" / "tasks" / f"replay_{family}.py"
    sys.modules["kaggle_benchmarks"] = stub
    try:
        spec = importlib.util.spec_from_file_location(f"replay_{family}", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        del sys.modules["kaggle_benchmarks"]
    return path.read_text(encoding="utf-8"), module


@pytest.mark.parametrize("family", ["trust", "restraint"])
def test_replay_reproduces_report(family):
    _, mod = load(family)
    conditions = getattr(mod, CONDITIONS[family])
    task = getattr(mod, f"memory_discipline_{family}")
    size = sum(i["family"] == family for i in build_kaggle_replay.ITEMS)
    assert len(REPORT) == 39
    for model, entry in REPORT.items():
        key, results = mod.replay_results(model)
        assert key == model
        assert mod.family_score(results, conditions) == pytest.approx(entry[family], abs=1e-12), model
        assert task(types.SimpleNamespace(model=model)) == pytest.approx(entry[family], abs=1e-12)
        assert size - len(results) == entry["errored"][family] + entry["missing"][family], model


@pytest.mark.parametrize("family", ["trust", "restraint"])
def test_unknown_model_raises_and_tolerant_lookup_works(family):
    _, mod = load(family)
    with pytest.raises(KeyError):
        mod.replay_results("anthropic/claude-sonnet-4-5-20250929-not-run")
    key, _ = mod.replay_results("claude-haiku-4-5-20251001")
    assert key == "anthropic/claude-haiku-4-5@20251001"


@pytest.mark.parametrize("family", ["trust", "restraint"])
def test_replay_file_is_current_and_ends_with_choose(family):
    source, mod = load(family)
    expected = json.loads(json.dumps(build_kaggle_replay.encode(REPORT, family)))
    assert mod.REPLAY == expected
    tail = source.rstrip("\n").splitlines()
    assert tail[-1] == f"# %choose memory_discipline_{family}"
    run_at = source.index(f"memory_discipline_{family}.run(kbench.llm)")
    assert run_at < source.rindex(f"# %choose memory_discipline_{family}")
    assert "llm.prompt" not in source  # the replay never calls the model
