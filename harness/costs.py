"""The token and cost ledger: what one run spent, per arm, sessions and ingestion together.

Two accounting rules, both learned the expensive way:

- **The boundary is end-to-end.** Vendors report retrieval-side compression and quietly omit
  what their extraction pipeline spent at ingest time; the measured gap between claimed and
  real savings is severalfold. Here ingestion tokens sit in the same table as session tokens,
  and the per-arm total is the number that gets published.
- **No price is hard-coded.** A price rots silently and then gets trusted precisely because
  it is specific. Estimation takes an explicit :class:`ModelPricing` (or a ``pricing.json``
  the caller maintains, dated); with no pricing given you get tokens, not dollars, and that
  is an answer rather than a placeholder zero.

Token counts come from :class:`~harness.schema.SessionRecord` (``input_tokens`` /
``output_tokens``, ``None`` when unobserved, never zero) and from adapter
:class:`~harness.adapters.base.IngestReport` rows. Records with unobserved counts are counted
in ``sessions_unmetered`` instead of being averaged in as zeros.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .adapters.base import IngestReport
from .schema import SessionRecord


@dataclass(frozen=True)
class ModelPricing:
    """USD per million tokens, with the date the price was read and where from."""

    model: str
    usd_per_mtok_input: float
    usd_per_mtok_output: float
    as_of: str
    source: str = ""
    #: Rate for tokens served from the provider's prompt cache, which is the cheap class. Left
    #: None when the provider publishes no separate rate, in which case cache reads are charged
    #: at the fresh-input rate and `priced_cache_separately` reports False, so an artifact can
    #: say which of the two it is rather than leaving the reader to assume.
    usd_per_mtok_cache_read: float | None = None
    #: Rate for writing the cache, which several providers charge at a PREMIUM over fresh input.
    usd_per_mtok_cache_creation: float | None = None

    @property
    def priced_cache_separately(self) -> bool:
        return (
            self.usd_per_mtok_cache_read is not None
            or self.usd_per_mtok_cache_creation is not None
        )

    def usd(
        self,
        input_tokens: int,
        output_tokens: int,
        *,
        cache_read_tokens: int = 0,
        cache_creation_tokens: int = 0,
    ) -> float:
        """Dollars for one bundle of tokens.

        ``input_tokens`` is the TOTAL input, the sum of the three classes, because that is what
        `SessionRecord.input_tokens` holds. The two cache counts are subtracted back out and
        repriced, so a caller that knows the split gets it charged correctly and a caller that
        does not gets exactly the old answer.

        This split is not cosmetic. Measured on `results/pilot-003-deepseek`, cache reads are
        68.2% of the recall arm's input against 48.6% of claude_md's, so charging one rate for
        all three both overstates the total and overstates it UNEVENLY between the arms being
        compared. The harness has recorded the split per session since the beginning; only the
        pricing ignored it.
        """

        fresh = input_tokens - cache_read_tokens - cache_creation_tokens
        if fresh < 0:
            raise ValueError(
                f"cache tokens ({cache_read_tokens} read + {cache_creation_tokens} creation) "
                f"exceed the total input {input_tokens}"
            )
        cache_read_rate = (
            self.usd_per_mtok_input
            if self.usd_per_mtok_cache_read is None
            else self.usd_per_mtok_cache_read
        )
        cache_creation_rate = (
            self.usd_per_mtok_input
            if self.usd_per_mtok_cache_creation is None
            else self.usd_per_mtok_cache_creation
        )
        return (
            fresh * self.usd_per_mtok_input
            + cache_read_tokens * cache_read_rate
            + cache_creation_tokens * cache_creation_rate
            + output_tokens * self.usd_per_mtok_output
        ) / 1_000_000.0


def load_pricing(path: str | Path) -> dict[str, ModelPricing]:
    """Load a ``pricing.json`` of ``{model: {usd_per_mtok_input, ..., as_of, source}}``."""

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    pricing: dict[str, ModelPricing] = {}
    for model, entry in data.items():
        pricing[model] = ModelPricing(
            model=model,
            usd_per_mtok_input=float(entry["usd_per_mtok_input"]),
            usd_per_mtok_output=float(entry["usd_per_mtok_output"]),
            usd_per_mtok_cache_read=(
                float(entry["usd_per_mtok_cache_read"])
                if entry.get("usd_per_mtok_cache_read") is not None
                else None
            ),
            usd_per_mtok_cache_creation=(
                float(entry["usd_per_mtok_cache_creation"])
                if entry.get("usd_per_mtok_cache_creation") is not None
                else None
            ),
            as_of=str(entry["as_of"]),
            source=str(entry.get("source", "")),
        )
    return pricing


@dataclass
class ArmCosts:
    """One arm's ledger over a run. Mutable accumulator; serialise with ``to_dict``."""

    arm: str
    sessions: int = 0
    sessions_unmetered: int = 0
    session_input_tokens: int = 0
    session_output_tokens: int = 0
    #: The input split, summed from each record's metadata where the provider reported it. These
    #: are a PARTITION of session_input_tokens, not additions to it.
    session_cache_read_tokens: int = 0
    session_cache_creation_tokens: int = 0
    session_wall_time_ms: float = 0.0
    ingest_input_tokens: int = 0
    ingest_output_tokens: int = 0
    ingest_unmetered: int = 0
    ingest_wall_time_ms: float = 0.0
    ingest_items_stored: int = 0
    #: Set when this arm ingested with a model running on the benchmark host rather than a hosted
    #: API. Its token columns are then truthfully zero and misleadingly comparable; see `tally`.
    ingest_local_model: str | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def total_input_tokens(self) -> int:
        return self.session_input_tokens + self.ingest_input_tokens

    @property
    def total_output_tokens(self) -> int:
        return self.session_output_tokens + self.ingest_output_tokens

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens

    def estimate_usd(self, pricing: ModelPricing) -> float:
        # Ingest tokens carry no cache split, so only the session half contributes cache counts.
        return pricing.usd(
            self.total_input_tokens,
            self.total_output_tokens,
            cache_read_tokens=self.session_cache_read_tokens,
            cache_creation_tokens=self.session_cache_creation_tokens,
        )

    def to_dict(self, pricing: ModelPricing | None = None) -> dict[str, Any]:
        out: dict[str, Any] = {
            "arm": self.arm,
            "sessions": self.sessions,
            "sessions_unmetered": self.sessions_unmetered,
            "session_input_tokens": self.session_input_tokens,
            "session_output_tokens": self.session_output_tokens,
            "session_wall_time_ms": self.session_wall_time_ms,
            "ingest_input_tokens": self.ingest_input_tokens,
            "ingest_output_tokens": self.ingest_output_tokens,
            "ingest_unmetered": self.ingest_unmetered,
            "ingest_wall_time_ms": self.ingest_wall_time_ms,
            "ingest_items_stored": self.ingest_items_stored,
            "ingest_local_model": self.ingest_local_model,
            "total_tokens": self.total_tokens,
            "notes": list(self.notes),
        }
        if pricing is not None:
            out["estimated_usd"] = round(self.estimate_usd(pricing), 4)
            out["pricing_as_of"] = pricing.as_of
            out["pricing_model"] = pricing.model
            # The prices themselves, not just their date. Recovering which rates produced a
            # published dollar figure previously meant reverse-solving a linear system from two
            # arms' rounded totals, which is not a thing an artifact should require of a reader.
            out["usd_per_mtok_input"] = pricing.usd_per_mtok_input
            out["usd_per_mtok_output"] = pricing.usd_per_mtok_output
            out["usd_per_mtok_cache_read"] = pricing.usd_per_mtok_cache_read
            out["usd_per_mtok_cache_creation"] = pricing.usd_per_mtok_cache_creation
            out["priced_cache_separately"] = pricing.priced_cache_separately
            out["session_cache_read_tokens"] = self.session_cache_read_tokens
            out["session_cache_creation_tokens"] = self.session_cache_creation_tokens
        return out


def tally(
    records: Iterable[SessionRecord],
    ingest_reports: Iterable[IngestReport] = (),
) -> dict[str, ArmCosts]:
    """Aggregate a run's records and ingest reports into one ledger per arm.

    Every attempted session is counted, admitted or not: the money was spent either way,
    and a run whose discards were expensive should say so.
    """

    ledger: dict[str, ArmCosts] = {}

    for record in records:
        costs = ledger.setdefault(record.arm, ArmCosts(arm=record.arm))
        costs.sessions += 1
        if record.input_tokens is None or record.output_tokens is None:
            costs.sessions_unmetered += 1
        else:
            costs.session_input_tokens += record.input_tokens
            costs.session_output_tokens += record.output_tokens
            usage = record.metadata.get("token_usage") or record.metadata or {}
            costs.session_cache_read_tokens += int(
                usage.get("cache_read_input_tokens") or 0
            )
            costs.session_cache_creation_tokens += int(
                usage.get("cache_creation_input_tokens") or 0
            )
        if record.wall_time_ms is not None:
            costs.session_wall_time_ms += record.wall_time_ms

    for report in ingest_reports:
        costs = ledger.setdefault(report.arm, ArmCosts(arm=report.arm))
        if report.local_model:
            # Zero hosted tokens is the TRUE answer here, and it is also the misleading one if it
            # is printed beside a competitor's LLM-extraction bill with nothing to say the two
            # numbers measure different resources. Name the model and keep the wall clock.
            costs.ingest_local_model = report.local_model
            costs.notes.append(
                f"ingest into {report.namespace!r} spent NO hosted tokens: it ran the local model "
                f"{report.local_model!r} on the benchmark host. The zero in the token column is a "
                f"real zero and is not a zero cost; compare it against another arm's extraction "
                f"tokens only alongside ingest_wall_time_ms"
            )
        elif report.llm_input_tokens is None or report.llm_output_tokens is None:
            costs.ingest_unmetered += 1
            costs.notes.append(
                f"ingest into {report.namespace!r} was not token-metered "
                f"(vendor-side extraction); its cost is missing from the totals, not zero"
            )
        else:
            costs.ingest_input_tokens += report.llm_input_tokens
            costs.ingest_output_tokens += report.llm_output_tokens
        if report.wall_time_ms is not None:
            costs.ingest_wall_time_ms += report.wall_time_ms
        if report.items_stored is not None:
            costs.ingest_items_stored += report.items_stored

    return ledger


def efficiency(
    records: Iterable[SessionRecord], *, admitted_cells: Mapping[tuple[str, int], bool] | None = None
) -> dict[str, Any]:
    """Success per unit of spend, per arm. The number a buyer actually asks for.

    A success rate alone cannot separate "this layer is better" from "this layer was given four
    times the budget". Measured on `pilot-004-placebo`, the recall arm used 4.5x the input tokens of
    every other arm for +17.4 points, and no arm in that grid was budget-matched. Publishing the
    ratio does not fix the missing control arm, but it does stop the headline being quoted without
    it.

    ``admitted_cells`` restricts the numerator to the cells the gate admitted, which is the same
    denominator the success rate uses; the token totals stay over every attempted session, because
    the money was spent either way.
    """

    per_arm: dict[str, dict[str, Any]] = {}
    for record in records:
        entry = per_arm.setdefault(
            record.arm,
            {"sessions": 0, "successes": 0, "input_tokens": 0, "output_tokens": 0, "wall_ms": 0.0},
        )
        entry["sessions"] += 1
        counted = admitted_cells is None or admitted_cells.get(record.cell, False)
        if counted and record.success:
            entry["successes"] += 1
        entry["input_tokens"] += record.input_tokens or 0
        entry["output_tokens"] += record.output_tokens or 0
        entry["wall_ms"] += record.wall_time_ms or 0.0

    out: dict[str, Any] = {}
    for arm, entry in sorted(per_arm.items()):
        tokens = entry["input_tokens"] + entry["output_tokens"]
        out[arm] = {
            **entry,
            "successes_per_mtok_input": (
                round(entry["successes"] / (entry["input_tokens"] / 1e6), 2)
                if entry["input_tokens"]
                else None
            ),
            "successes_per_mtok_total": (
                round(entry["successes"] / (tokens / 1e6), 2) if tokens else None
            ),
            "mean_input_tokens_per_session": (
                round(entry["input_tokens"] / entry["sessions"], 1) if entry["sessions"] else None
            ),
            "mean_wall_s_per_session": (
                round(entry["wall_ms"] / 1000.0 / entry["sessions"], 1) if entry["sessions"] else None
            ),
        }
    return out


def summarize(
    records: Iterable[SessionRecord],
    ingest_reports: Iterable[IngestReport] = (),
    *,
    pricing: Mapping[str, ModelPricing] | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """The run-level cost artifact: per-arm ledgers plus a grand total.

    ``model`` selects the pricing entry for the session model; with no pricing the summary
    carries tokens only and says why the dollars are absent.
    """

    ledger = tally(records, ingest_reports)
    selected = pricing.get(model) if pricing and model else None
    arms = {
        arm: costs.to_dict(selected) for arm, costs in sorted(ledger.items())
    }
    total_tokens = sum(costs.total_tokens for costs in ledger.values())
    summary: dict[str, Any] = {
        "arms": arms,
        "total_tokens": total_tokens,
        "total_sessions": sum(costs.sessions for costs in ledger.values()),
    }
    if selected is not None:
        summary["estimated_usd"] = round(
            sum(costs.estimate_usd(selected) for costs in ledger.values()), 4
        )
        summary["pricing_as_of"] = selected.as_of
    else:
        summary["estimated_usd"] = None
        summary["pricing_note"] = (
            "no pricing supplied: totals are tokens, not dollars; pass a dated "
            "pricing.json to estimate spend"
        )
    return summary
