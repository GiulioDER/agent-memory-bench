"""An ingest report must count what landed, not what it rendered.

`render_corpus` returns the number of files it WROTE. Publishing that as `items_stored` says
nothing about whether the index holds anything, so an ingest that renders 130 files and stores
none reports "130 items" and reads as a success. The arm then scores zero on every task, which
looks like the product failing rather than the wiring failing.

That asymmetry matters most for an arm that is not ours. We would notice recall scoring zero and
go looking; a competitor's maintainer would have to take our word for it.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from adapters.recall.adapter import RecallAdapter

SOURCE = inspect.getsource(RecallAdapter)
REPO = Path(__file__).resolve().parents[1]


def test_items_stored_is_not_the_rendered_file_count():
    """Mutation: `items_stored=count`. That is what shipped until 2026-08-28, and it is what a
    successful-looking empty ingest would have been published as."""

    ingest = inspect.getsource(RecallAdapter.ingest)
    assert "items_stored=stored" in ingest, "items_stored must be the verified row count"
    assert "items_stored=count" not in ingest, (
        "items_stored is the rendered file count again; an empty index would report as full"
    )


def test_an_empty_tenant_raises_rather_than_reporting_success():
    """The whole point. `recall index` exiting 0 is not evidence that anything was written."""

    ingest = inspect.getsource(RecallAdapter.ingest)
    assert "if stored == 0:" in ingest
    assert "RuntimeError" in ingest


def test_the_row_count_sets_the_tenant_guc():
    """THE assertion that keeps this from becoming a false alarm.

    These tables carry row-level security: without `recall.tenant_id` a plain count returns 0 for
    every tenant, indistinguishable from an empty index. Omitting it would make the new check fail
    every healthy ingest, and the fix would look like "the verification is broken, remove it".

    This project has already made that mistake once in the other direction, reading an
    RLS-suppressed zero as an empty corpus and rebuilding a healthy one.
    """

    rows = inspect.getsource(RecallAdapter._rows_for_tenant)
    assert "recall.tenant_id" in rows, "the count must set the tenant GUC or RLS hides every row"
    assert "SET LOCAL" in rows
    guc_at = rows.index("recall.tenant_id")
    count_at = rows.index("SELECT count(*)")
    assert guc_at < count_at, "the GUC must be set BEFORE the count, not after"


def test_a_missing_driver_degrades_rather_than_crashing():
    """An environment without psycopg should not fail an ingest that otherwise worked; it should
    report that the count is unavailable."""

    rows = inspect.getsource(RecallAdapter._rows_for_tenant)
    assert "ImportError" in rows
    assert "return -1" in rows


@pytest.mark.parametrize("note", ["rendered", "stored"])
def test_the_report_states_both_numbers(note):
    """Keeping both makes a divergence visible rather than hidden behind one figure."""

    assert note in inspect.getsource(RecallAdapter.ingest)
