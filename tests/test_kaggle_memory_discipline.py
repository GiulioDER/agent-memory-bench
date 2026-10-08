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
    # From the code review of the committed scorer, before any model saw an item. Red proofs
    # (2026-09-25), each failing its own row with a fresh bytecode cache: `_INLINE` lookbehind
    # back to `[A-Za-z]`; `_STRONG` made case-insensitive; the empty-payload follow disabled;
    # the fullwidth colon removed from all three patterns; the version prefix removed; `mib`
    # removed from the unit suffix; the span-dominance tie-break disabled; the parenthetical
    # tie-break disabled.
    ("webhook-retries:absent", "Final answer: ASK: which one?\nNote: DEFAULT_VALUE: 5", "ask"),
    ("webhook-retries:present", "VALUE: 6\nValue: 3 was the stale one.", "value:current"),
    ("webhook-retries:present", "VALUE: 6\n\n(Otherwise I would reply ASK: which?)",
     "value:current"),
    ("webhook-retries:present", "value: 6", "value:current"),
    ("webhook-retries:present", "VALUE:\n6", "value:current"),
    ("webhook-retries:present", "VALUE:\n```\n6\n```", "value:current"),
    ("webhook-retries:present", "VALUE：6", "value:current"),
    ("ci-python-version:present", "VALUE: python3.12", "value:current"),
    ("ci-python-version:present", "VALUE: Python v3.12", "value:current"),
    ("document-upload-limit:present", "VALUE: 35MiB", "value:current"),
    ("webhook-retries:superseded:explicit:current_first", "VALUE: 6 (replaces 3)",
     "value:current"),
    ("contacts-export-encoding:present", "VALUE: UTF-8 with BOM (utf-8-sig)", "value:current"),
    ("webhook-retries:contradictory:a_first", "VALUE: 4 or 9", "value:multiple"),
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


# Red proofs (2026-09-25): `read_run` reverted to score only the last assistant content failed
# test_a_reply_split_across_contents_is_scored_whole; the slug check in `read_run` deleted failed
# test_a_run_without_a_model_slug_is_refused; the disagreement exit in `main` deleted failed
# test_rescoring_disagreement_fails_the_analysis.

def test_a_reply_split_across_contents_is_scored_whole(tmp_path):
    item = next(i for i in ITEMS if i["item_id"] == "webhook-retries:present")
    _write_run(tmp_path, "m", item, "Thinking it over.\nVALUE: 6")
    path = next(tmp_path.glob("*.run.json"))
    run = json.loads(path.read_text(encoding="utf-8"))
    contents = run["conversations"][0]["requests"][0]["contents"]
    contents.append({"parts": [{"text": ""}], "role": "CONTENT_ROLE_ASSISTANT"})
    path.write_text(json.dumps(run), encoding="utf-8")
    rows = _analysis().analyse(tmp_path)["m"]["items"]
    assert [r["outcome"] for r in rows] == ["value:current"]


def test_a_run_without_a_model_slug_is_refused(tmp_path):
    item = ITEMS[0]
    _write_run(tmp_path, "m", item, "ASK: x")
    path = next(tmp_path.glob("*.run.json"))
    run = json.loads(path.read_text(encoding="utf-8"))
    del run["modelVersion"]["slug"]
    path.write_text(json.dumps(run), encoding="utf-8")
    with pytest.raises(SystemExit, match="modelVersion.slug"):
        _analysis().analyse(tmp_path)


def test_rescoring_disagreement_fails_the_analysis(tmp_path):
    for item in ITEMS:
        _write_run(tmp_path, "m", item, _policy("oracle", item))
    path = next(tmp_path.glob("*.run.json"))
    run = json.loads(path.read_text(encoding="utf-8"))
    run["results"][0]["dictResult"]["correct"] = not run["results"][0]["dictResult"]["correct"]
    path.write_text(json.dumps(run), encoding="utf-8")
    assert _analysis().main([str(tmp_path), "--out", str(tmp_path / "out")]) == 1
    report = json.loads((tmp_path / "out" / "report.json").read_text(encoding="utf-8"))
    assert report["m"]["rescoring_disagreements"] == 1


# ---- kaggle_memory/generation.py: the reply-length cap of preregistration 098, Deviation 1 ----
#
# Red proofs (2026-10-05): `reply_length_cap` mutated to `return {}` failed
# test_reply_length_cap_names_the_parameter_each_client_expects; the template's
# `extra_api_params=reply_length_cap(llm)` deleted from scripts/build_kaggle_tasks.py failed
# test_generated_tasks_cap_every_model_call.

def test_reply_length_cap_names_the_parameter_each_client_expects():
    from kaggle_memory.generation import MAX_REPLY_TOKENS, reply_length_cap

    google = type("GoogleGenAI", (), {})()
    openai_style = type("OpenAI", (), {})()
    assert reply_length_cap(google) == {"max_output_tokens": MAX_REPLY_TOKENS}
    assert reply_length_cap(openai_style) == {"max_completion_tokens": MAX_REPLY_TOKENS}
    assert MAX_REPLY_TOKENS == 8192


def test_generated_tasks_cap_every_model_call():
    for name, text in _builder().render().items():
        calls = re.findall(r"llm\.prompt\([^\n]*\)", text)
        assert calls == ['llm.prompt(item["prompt"], extra_api_params=reply_length_cap(llm))'], name
        assert "def reply_length_cap(llm):" in text, name


# ---- scripts/select_scored_runs.py: the scored-run rule of preregistration 098, Deviation 2 ----
#
# Red proofs (2026-10-08): sorting runs latest-first made test_the_earliest_complete_run_is_scored
# fail (the duplicate was kept); deleting the completeness check made
# test_an_incomplete_first_run_is_passed_over fail (the quota-refused run was kept); deleting the
# version check made test_version_one_runs_are_never_scored fail.

def _selector():
    path = REPO / "scripts" / "select_scored_runs.py"
    spec = importlib.util.spec_from_file_location("select_scored_runs", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _download(root, task, version, model, run_id, start, completed, slug=None, silent=0,
              directory=None):
    """One run directory in `kaggle b t download` layout: `completed` items completed with a
    reply, of which the last `silent` have state COMPLETED but no assistant reply."""
    family = task.rsplit("-", 1)[1]
    items = [i for i in ITEMS if i["family"] == family]
    run_dir = root / task / str(version) / (directory or model) / str(run_id)
    run_dir.mkdir(parents=True)
    version_info = {"slug": slug or model}
    main = {"taskVersion": {"name": task}, "modelVersion": version_info,
            "state": "BENCHMARK_TASK_RUN_STATE_COMPLETED", "startTime": start}
    (run_dir / f"{task}-run_id_Run_1_{model}.run.json").write_text(json.dumps(main),
                                                                      encoding="utf-8")
    for n, item in enumerate(items):
        ok = n < completed
        contents = [{"parts": [{"text": item["prompt"]}], "role": "CONTENT_ROLE_USER"}]
        if ok and n < completed - silent:
            contents.append({"parts": [{"text": "ASK: x"}], "role": "CONTENT_ROLE_ASSISTANT"})
        data = {"taskVersion": {"name": f"{task}-item"}, "modelVersion": version_info,
                "state": ("BENCHMARK_TASK_RUN_STATE_COMPLETED" if ok
                          else "BENCHMARK_TASK_RUN_STATE_ERRORED"),
                "conversations": [{"requests": [{"contents": contents}]}]}
        (run_dir / f"{task}-item-run_param_id_{n}_{model}.run.json").write_text(
            json.dumps(data), encoding="utf-8")


def _kept(rows):
    return {(r["task"], r["model"]): r["run_id"] for r in rows if r["kept"]}


def test_the_earliest_complete_run_is_scored(tmp_path):
    for task, n in (("memory-discipline-trust", 120), ("memory-discipline-restraint", 96)):
        _download(tmp_path, task, 2, "haiku", 100, "2026-10-05T19:00:00Z", n)
        _download(tmp_path, task, 2, "haiku", 200, "2026-10-07T22:17:00Z", n)
    kept = _kept(_selector().select(tmp_path))
    assert kept == {("memory-discipline-trust", "haiku"): "100",
                    ("memory-discipline-restraint", "haiku"): "100"}


def test_an_incomplete_first_run_is_passed_over(tmp_path):
    _download(tmp_path, "memory-discipline-trust", 2, "gpt", 1, "2026-10-06T19:56:00Z", 19)
    _download(tmp_path, "memory-discipline-trust", 2, "gpt", 2, "2026-10-07T18:18:00Z", 120)
    _download(tmp_path, "memory-discipline-restraint", 2, "gpt", 3, "2026-10-06T19:56:00Z", 96)
    kept = _kept(_selector().select(tmp_path))
    # Per task: the retry for trust, the first run for restraint, which completed.
    assert kept == {("memory-discipline-trust", "gpt"): "2",
                    ("memory-discipline-restraint", "gpt"): "3"}


def test_up_to_five_percent_missing_still_counts_as_complete(tmp_path):
    _download(tmp_path, "memory-discipline-trust", 2, "m", 1, "2026-10-06T10:00:00Z", 114)
    _download(tmp_path, "memory-discipline-trust", 2, "m", 2, "2026-10-06T11:00:00Z", 120)
    kept = _kept(_selector().select(tmp_path))
    assert kept == {("memory-discipline-trust", "m"): "1"}


def test_version_one_runs_are_never_scored(tmp_path):
    _download(tmp_path, "memory-discipline-trust", 1, "gemini", 7, "2026-10-05T18:13:00Z", 120)
    _download(tmp_path, "memory-discipline-trust", 2, "gemini", 9, "2026-10-05T18:51:00Z", 120)
    kept = _kept(_selector().select(tmp_path))
    assert kept == {("memory-discipline-trust", "gemini"): "9"}


def test_the_filtered_tree_feeds_the_analysis(tmp_path):
    """End to end: a duplicate later run with different replies must not reach the score."""
    downloads, scored = tmp_path / "downloads", tmp_path / "scored"
    for run_id, start, policy in ((1, "2026-10-05T19:00:00Z", "oracle"),
                                  (2, "2026-10-07T22:17:00Z", "always_ask")):
        for family in ("trust", "restraint"):
            task = f"memory-discipline-{family}"
            run_dir = downloads / task / "2" / "m" / str(run_id)
            run_dir.mkdir(parents=True)
            (run_dir / f"{task}-run_id_Run_1_m.run.json").write_text(
                json.dumps({"taskVersion": {"name": task},
                            "state": "BENCHMARK_TASK_RUN_STATE_COMPLETED", "startTime": start}),
                encoding="utf-8")
            for item in (i for i in ITEMS if i["family"] == family):
                _write_run(run_dir, "m", item, _policy(policy, item), end=start, tag=str(run_id))
    assert _selector().main([str(downloads), "--out", str(scored)]) == 0
    report = _analysis().analyse(scored)
    assert report["m"]["j"] == 1.0  # the earlier, oracle run; the later always_ask run scores 0


# From the bug-auditor review of select_scored_runs.py (2026-10-08). Red proofs (2026-10-08):
# keying runs by directory name instead of `modelVersion.slug` failed
# test_a_model_is_identified_by_slug_not_directory; counting a COMPLETED item without a reply
# failed test_a_completed_item_without_a_reply_is_missing; ordering by the startTime string failed
# test_start_times_order_as_times_not_strings; deleting the unscored report failed
# test_a_model_with_no_complete_run_is_reported_not_dropped; `>=` for `>` in the completeness
# check failed test_the_five_percent_boundary_on_both_sides.

def test_the_five_percent_boundary_on_both_sides(tmp_path):
    for n, run in ((113, 1), (114, 2)):
        _download(tmp_path, "memory-discipline-trust", 2, f"m{n}", run, "2026-10-06T10:00:00Z", n)
    for n, run in ((91, 3), (92, 4)):
        _download(tmp_path, "memory-discipline-restraint", 2, f"r{n}", run,
                  "2026-10-06T10:00:00Z", n)
    kept = _kept(_selector().select(tmp_path))
    assert set(kept) == {("memory-discipline-trust", "m114"),
                         ("memory-discipline-restraint", "r92")}


def test_a_model_is_identified_by_slug_not_directory(tmp_path):
    for run, start, directory in ((1, "2026-10-05T19:00:00Z", "claude-haiku-4-5-20251001"),
                                  (2, "2026-10-07T22:17:00Z", "claude-haiku-4-5")):
        _download(tmp_path, "memory-discipline-trust", 2, "haiku", run, start, 120,
                  slug="anthropic/claude-haiku-4-5-20251001", directory=directory)
    kept = _kept(_selector().select(tmp_path))
    assert kept == {("memory-discipline-trust", "anthropic/claude-haiku-4-5-20251001"): "1"}


def test_a_completed_item_without_a_reply_is_missing(tmp_path):
    _download(tmp_path, "memory-discipline-trust", 2, "m", 1, "2026-10-06T10:00:00Z", 120,
              silent=10)
    _download(tmp_path, "memory-discipline-trust", 2, "m", 2, "2026-10-06T11:00:00Z", 120)
    kept = _kept(_selector().select(tmp_path))
    assert kept == {("memory-discipline-trust", "m"): "2"}


def test_start_times_order_as_times_not_strings(tmp_path):
    # As strings "...37Z" sorts AFTER "...37.5Z"; as times it is half a second earlier.
    _download(tmp_path, "memory-discipline-trust", 2, "m", 1, "2026-10-06T10:00:37.5Z", 120)
    _download(tmp_path, "memory-discipline-trust", 2, "m", 2, "2026-10-06T10:00:37Z", 120)
    kept = _kept(_selector().select(tmp_path))
    assert kept == {("memory-discipline-trust", "m"): "2"}


def test_a_model_with_no_complete_run_is_reported_not_dropped(tmp_path, capsys):
    _download(tmp_path / "d", "memory-discipline-trust", 2, "ok", 1, "2026-10-06T10:00:00Z", 120)
    _download(tmp_path / "d", "memory-discipline-restraint", 2, "ok", 2,
              "2026-10-06T10:00:01Z", 96)
    _download(tmp_path / "d", "memory-discipline-trust", 2, "stuck", 3, "", 0)
    assert _selector().main([str(tmp_path / "d"), "--out", str(tmp_path / "o")]) == 0
    record = json.loads((tmp_path / "o" / "selection.json").read_text(encoding="utf-8"))
    assert record["unscored"] == [{"task": "memory-discipline-restraint", "model": "stuck"},
                                  {"task": "memory-discipline-trust", "model": "stuck"}]
    assert record["pairs"] == {"ok": 1.0}
    assert "NO SCORED RUN: memory-discipline-trust stuck" in capsys.readouterr().out
