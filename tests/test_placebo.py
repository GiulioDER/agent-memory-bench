from harness.placebo import length_metadata, lexical_token_count, render_placebo
from harness.tasks import discover_tasks
from scripts.pilot import build_bundles, recall_instruction


def test_placebo_matches_line_and_whitespace_token_shape():
    reference = "# Project notes\n\nKeep changes small and inspect the result.\n- item detail\n"
    placebo = render_placebo(reference)
    metadata = length_metadata(reference, placebo)

    assert metadata["match"] is True
    assert lexical_token_count(placebo) == lexical_token_count(reference)
    assert len(placebo.splitlines()) == len(reference.splitlines())
    assert "Keep changes small" not in placebo


def test_placebo_preserves_markdown_line_markers_without_task_content():
    placebo = render_placebo("# Task-specific title\n- run the command now\n")

    assert placebo.startswith("# project project\n- project")
    assert "Task-specific" not in placebo
    assert "command" not in placebo


def test_placebo_preflight_passes_the_arm_instruction_mapping(tmp_path):
    task = next(task for task in discover_tasks() if task.task_id.startswith("ts-"))

    bundles = build_bundles(
        task,
        tmp_path,
        {"recall": recall_instruction("skill")},
    )

    assert bundles["recall"].is_file()
