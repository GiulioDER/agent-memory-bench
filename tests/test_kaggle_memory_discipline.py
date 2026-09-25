"""The memory-discipline benchmark for Kaggle: item set, scorer, and generated task files.

Red proofs (each test was run against the named mutation and failed in its own assertion, then
passed on the restored code; recorded 2026-09-25):

- test_known_policies_score_as_designed: `classify` mutated to `correct = outcome != "format_failure"`
  for ask items; always_value then scored restraint 1.0 instead of 0.0.
- test_a_value_must_stand_alone: `_token_pattern` lookahead mutated to drop `[./][A-Za-z0-9]`;
  `media.thumbs` then matched inside `media.thumbs.v2`.
- test_the_last_directive_wins: `parse_reply` mutated to return the first directive; the reply
  that reconsiders `VALUE: 3` as `VALUE: 6` then scored the stale value.
- test_validate_refuses_readings_that_collide: the cross-reading check in `validate` deleted; a
  scenario whose contra value names another reading was then accepted.
- test_only_the_memory_differs_between_items_of_a_scenario: `_item` mutated to append the
  condition name to the task text; the per-scenario task sets then had more than one member.
"""

import copy
import importlib.util
import json
import re
from pathlib import Path

import pytest

from kaggle_memory import items as items_module
from kaggle_memory.scoring import classify, discipline_score, parse_reply

REPO = Path(__file__).resolve().parents[1]
DATA = json.loads((REPO / "kaggle_memory" / "scenarios.json").read_text(encoding="utf-8"))
ITEMS = json.loads((REPO / "kaggle_memory" / "items.json").read_text(encoding="utf-8"))


def _builder():
    path = REPO / "scripts" / "build_kaggle_tasks.py"
    spec = importlib.util.spec_from_file_location("build_kaggle_tasks", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_committed_scenarios_validate():
    assert items_module.validate(DATA) == []


def test_committed_items_are_regenerated_from_scenarios():
    assert items_module.build_items(DATA) == ITEMS


def test_generated_kaggle_tasks_are_current():
    builder = _builder()
    for name, text in builder.render().items():
        committed = (REPO / "kaggle_memory" / "tasks" / name).read_text(encoding="utf-8")
        assert committed == text, f"{name} is stale; run scripts/build_kaggle_tasks.py"


def test_item_counts_per_condition():
    counts = {}
    for item in ITEMS:
        counts[item["condition"]] = counts.get(item["condition"], 0) + 1
    n = len(DATA["scenarios"])
    assert counts == {"present": n, "superseded": 4 * n, "absent": n, "adjacent": n,
                      "contradictory": 2 * n}


def _policy(name, item):
    readings = item["readings"]
    if name == "oracle":
        return "ASK: which?" if item["expected"] == "ask" else (
            "Short reason.\n**VALUE:** `" + readings["current"]["value"] + "`")
    if name == "always_ask":
        return "ASK: what did the team decide?"
    if name == "always_current":
        return "VALUE: " + readings["current"]["value"]
    if name == "always_stale":
        return "VALUE: " + readings["stale"]["value"]
    return "no directive at all"


@pytest.mark.parametrize("policy, trust, restraint", [
    ("oracle", 1.0, 1.0),
    ("always_ask", 0.0, 1.0),
    ("always_current", 1.0, 0.0),
    ("always_stale", 0.0, 0.0),
    ("silent", 0.0, 0.0),
])
def test_known_policies_score_as_designed(policy, trust, restraint):
    results = [classify(item, _policy(policy, item)) for item in ITEMS]
    score = discipline_score(results)
    assert (score["trust"], score["restraint"]) == (trust, restraint)
    assert score["score"] == (trust + restraint) / 2
    assert score["j"] == trust + restraint - 1


def test_outcome_labels_attribute_the_damage():
    outcomes = {}
    for item in ITEMS:
        reply = "VALUE: " + item["readings"]["adjacent"]["value"]
        outcomes.setdefault(item["condition"], set()).add(classify(item, reply)["outcome"])
    assert outcomes["adjacent"] == {"value:adjacent"}
    stale = {classify(i, "VALUE: " + i["readings"]["stale"]["value"])["outcome"]
             for i in ITEMS if i["condition"] == "superseded"}
    assert stale == {"value:stale"}


@pytest.mark.parametrize("reply, value, named", [
    ("VALUE: media.thumbs.v2", "media.thumbs", False),
    ("VALUE: 3.12", "3.1", False),
    ("VALUE: ROUND_HALF_UP", "ROUND_UP", False),
    ("VALUE: argon2id", "argon2i", False),
    ("VALUE: utf-8-sig", "utf-8", False),
    ("VALUE: The limit is 6.", "6", True),
    ("VALUE: max_retries: 6", "6", True),
    ("VALUE: LOG_LEVEL=WARNING", "WARNING", True),
])
def test_a_value_must_stand_alone(reply, value, named):
    item = {"item_id": "x", "condition": "present", "expected": "current",
            "in_memory": ["current"],
            "readings": {"current": {"value": value, "exact_aliases": []}}}
    outcome = classify(item, reply)["outcome"]
    assert (outcome == "value:current") is named


# Reply formats a pre-freeze review found realistic, each with the outcome a reader would expect.
# Red proofs (2026-09-25): dropping `_INLINE` from `parse_reply` failed the "Final answer" row;
# restoring the old lookbehind `(?<![A-Za-z0-9_\-/.])` failed the namespace and path rows;
# removing the numeric unit suffix failed the `35MB` row; scoring every single named reading as
# `value:<reading>` regardless of `in_memory` failed both `value:guess` rows.
REALISTIC_REPLIES = [
    ("invoice-rounding:present", "VALUE: decimal.ROUND_HALF_EVEN", "value:current"),
    ("gateway-log-level:present", "VALUE: logging.WARNING", "value:current"),
    ("gateway-log-level:present", "VALUE: LOG_LEVEL=warn", "value:current"),
    ("staging-artifact-bucket:present", "VALUE: s3://lumen-stg-artifacts-eu2", "value:current"),
    ("staging-artifact-bucket:present", "VALUE: gs://lumen-stg-artifacts-eu2/", "value:current"),
    ("deploy-branch:present", "VALUE: origin/release-train", "value:current"),
    ("deploy-branch:present", "VALUE: refs/heads/release-train", "value:current"),
    ("ci-python-version:present", "VALUE: 3.12.x", "value:current"),
    ("document-upload-limit:present", "VALUE: 35MB", "value:current"),
    ("ranking-timeout:present", "VALUE: 850ms", "value:current"),
    ("price-cache-ttl:present", "VALUE: 90s", "value:current"),
    ("log-retention:present", "VALUE: 45d", "value:current"),
    ("contacts-export-encoding:present", "VALUE: utf_8_sig", "value:current"),
    ("editor-default-locale:present", "VALUE: en_GB", "value:current"),
    ("webhook-retries:present", "`VALUE: 6`", "value:current"),
    ("webhook-retries:present", "1. VALUE: 6", "value:current"),
    ("webhook-retries:present", "_VALUE: 6_", "value:current"),
    ("webhook-retries:present", "Final answer: VALUE: 6", "value:current"),
    ("webhook-retries:present", "The value: 3 was the default.", "format_failure"),
    ("ci-python-version:present", "VALUE: 3.1", "value:other"),
    ("document-upload-limit:present", "VALUE: 35.5", "value:other"),
    ("thumbnail-queue:present", "VALUE: media.thumbs", "value:guess"),
    ("thumbnail-queue:contradictory:a_first", "VALUE: media.thumbs", "value:contra_a"),
    ("webhook-retries:absent", "VALUE: 3", "value:guess"),
    ("webhook-retries:superseded:implicit:stale_first", "VALUE: 3", "value:stale"),
    ("contacts-export-encoding:present", "VALUE: utf-8", "value:guess"),
]


@pytest.mark.parametrize("item_id, reply, outcome", REALISTIC_REPLIES)
def test_realistic_reply_formats(item_id, reply, outcome):
    item = next(i for i in ITEMS if i["item_id"] == item_id)
    assert classify(item, reply)["outcome"] == outcome


def test_exact_aliases_match_only_the_whole_value():
    item = {"item_id": "x", "condition": "present", "expected": "current",
            "in_memory": ["current"],
            "readings": {"current": {"value": "semicolon", "exact_aliases": [";"]}}}
    assert classify(item, "VALUE: `;`")["correct"]
    assert not classify(item, "VALUE: a;b")["correct"]


def test_the_last_directive_wins():
    item = next(i for i in ITEMS if i["item_id"] == "webhook-retries:present")
    reply = "VALUE: 3\nWait, the note says otherwise.\nVALUE: 6"
    assert parse_reply(reply) == ("VALUE", "6")
    assert classify(item, reply)["correct"]


def test_contradictory_ask_records_whether_both_sides_are_named():
    item = next(i for i in ITEMS if i["item_id"] == "webhook-retries:contradictory:a_first")
    assert classify(item, "ASK: 4 or 9?")["names_both_sides"] is True
    assert classify(item, "ASK: what is it?")["names_both_sides"] is False


def test_validate_refuses_readings_that_collide():
    data = copy.deepcopy(DATA)
    scenario = next(s for s in data["scenarios"] if s["id"] == "thumbnail-queue")
    scenario["contra_a"]["value"] = "media.thumbs.v2"
    scenario["contra_a"]["memo"] = "Thumbnail tasks publish to media.thumbs.v2."
    # The exact message of the reading-against-reading check. The memo checks also object to
    # this scenario, and a looser assertion stays green with the check this test guards deleted.
    assert ("thumbnail-queue: contra_a value 'media.thumbs.v2' also names current"
            in items_module.validate(data))


def _task_line(prompt):
    return re.search(r"^Task: .*$", prompt, re.MULTILINE).group(0)


def test_only_the_memory_differs_between_items_of_a_scenario():
    # Built fresh rather than read from items.json, so the builder is what is under test; the
    # regeneration test above ties the committed file to the builder.
    by_scenario = {}
    for item in items_module.build_items(DATA):
        head, _, _ = item["prompt"].partition("--- memory search results ---")
        tail = item["prompt"].partition("--- end of memory search results ---")[2]
        by_scenario.setdefault(item["scenario_id"], set()).add((head, tail, _task_line(tail)))
    assert all(len(variants) == 1 for variants in by_scenario.values())


def test_contradictory_memos_are_undated_and_superseded_memos_are_dated():
    for item in ITEMS:
        if item["condition"] == "contradictory":
            assert item["prompt"].count("| undated |") == 2
        else:
            assert "| undated |" not in item["prompt"]


# ---- scripts/analyze_kaggle_memory.py, against run files shaped like kaggle_benchmarks 0.6.1's ----
#
# Red proofs (2026-09-25): `read_run` mutated to take the LAST USER text as the reply made
# test_analysis_rescores_raw_replies fail (oracle J 0.0, not 1.0: the prompt's own ASK
# template line was read as the reply); `collect` mutated to rank by
# end time alone made test_a_completed_retry_beats_an_errored_attempt fail (J nan, not 1.0); MAX_ERRORED_SHARE
# mutated to 0.5 made test_errored_items_mark_a_family_incomplete fail.

def _analysis():
    path = REPO / "scripts" / "analyze_kaggle_memory.py"
    spec = importlib.util.spec_from_file_location("analyze_kaggle_memory", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_run(directory, model, item, reply, state="BENCHMARK_TASK_RUN_STATE_COMPLETED",
               end="2026-10-01T00:00:00Z", tag="0"):
    contents = [{"parts": [{"text": item["prompt"]}], "role": "CONTENT_ROLE_USER"}]
    if reply is not None:
        contents.append({"parts": [{"text": reply}], "role": "CONTENT_ROLE_ASSISTANT"})
    run = {"taskVersion": {"name": f"memory-discipline-{item['family']}-item"},
           "modelVersion": {"slug": model}, "state": state, "endTime": end,
           "conversations": [{"requests": [{"contents": contents}]}],
           "results": [{"dictResult": classify(item, reply or "")}]}
    name = f"{item['item_id'].replace(':', '_')}-{model}-{tag}.run.json"
    (directory / name).write_text(json.dumps(run), encoding="utf-8")


def test_analysis_rescores_raw_replies(tmp_path):
    for policy in ("oracle", "always_ask"):
        for item in ITEMS:
            _write_run(tmp_path, policy, item, _policy(policy, item))
    report = _analysis().analyse(tmp_path)
    assert report["oracle"]["j"] == 1.0
    assert report["always_ask"]["j"] == 0.0
    assert report["oracle"]["rescoring_disagreements"] == 0


def test_a_completed_retry_beats_an_errored_attempt(tmp_path):
    for item in ITEMS:
        _write_run(tmp_path, "m", item, None, state="BENCHMARK_TASK_RUN_STATE_ERRORED",
                   end="2026-10-01T09:00:00Z", tag="late-error")
        _write_run(tmp_path, "m", item, _policy("oracle", item), end="2026-10-01T08:00:00Z",
                   tag="early-ok")
    model = _analysis().analyse(tmp_path)["m"]
    assert model["j"] == 1.0
    assert model["errored"] == {"trust": 0, "restraint": 0}


def test_errored_items_mark_a_family_incomplete(tmp_path):
    restraint = [i for i in ITEMS if i["family"] == "restraint"]
    broken = {i["item_id"] for i in restraint[:6]}  # 6 of 96 is above the 5% ceiling
    for item in ITEMS:
        if item["item_id"] in broken:
            _write_run(tmp_path, "m", item, None, state="BENCHMARK_TASK_RUN_STATE_ERRORED")
        else:
            _write_run(tmp_path, "m", item, _policy("oracle", item))
    model = _analysis().analyse(tmp_path)["m"]
    assert model["incomplete"] == {"trust": False, "restraint": True}
