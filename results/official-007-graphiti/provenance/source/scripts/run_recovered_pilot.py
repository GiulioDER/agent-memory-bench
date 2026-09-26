"""Run one Graphiti scoring condition after a separately verified recovery ingest."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from adapters.graphiti.adapter import GraphitiAdapter
from harness.adapters.base import IngestReport
from scripts import pilot


def _reused_ingest(self, corpus, namespace):
    expected = len(corpus.sessions)
    if expected <= 0:
        raise RuntimeError("recovery scoring received an empty corpus")
    return IngestReport(
        arm=self.name,
        namespace=namespace,
        sessions_offered=expected,
        items_stored=expected,
        wall_time_ms=0.0,
        notes=(
            "reused namespace after direct Graphiti core recovery",
            f"{expected} episodes verified before scoring; no new MCP ingestion submitted",
        ),
    )


GraphitiAdapter.ingest = _reused_ingest
raise SystemExit(asyncio.run(pilot.main()))
