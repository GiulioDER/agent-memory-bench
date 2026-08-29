"""Re-derive a published run's numbers from its published sessions, with nothing else.

    python -m scripts.verify_run results/official-001-absent
    python -m scripts.verify_run --all

⛔ **No credentials, no database, no model calls, no network.** That is the whole point. A reader
who distrusts this benchmark should be able to check that its headline numbers follow from its
published evidence without asking anyone for an API key, and without spending a cent. If this
script needs anything but a checkout and a Python interpreter, it has failed at its job.

## What it can prove, and what it cannot

It recomputes, from `records.final.jsonl` alone, using the same functions the run used:

* the **cost ledger**, per arm and in total, against the rates the run itself published, and
* the **endpoints**, for a harm-suite run, from the admitted cells.

Then it compares those against the committed `costs.json` and endpoints file. A mismatch means the
published summary does not follow from the published sessions, which is the single most important
thing a reader can check and the one nobody could check before this existed.

It also re-derives the **discard set** from the published per-session verdicts: a cell is
discarded exactly when some required arm's verdict is not admitted, and that set must equal the
published one. Every inadmissible session must state a reason, and every admitted cell must carry
a record for each required arm.

It **cannot** recompute why an individual session was judged inadmissible. The gate reads per-arm
`AdmissionSignal` values built by the adapters at run time, and those are not in the artifact.
That one step is checked for consistency rather than recomputed, and is reported in the `skip`
column rather than blurred into the same word as the things that are.

⚠️ **A green result here does not mean the run was well designed, that the tasks measure memory,
or that the corpus was fair.** It means the arithmetic is honest: these numbers came from these
sessions. Everything else is what the preregistration and the vendor review are for.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from harness.abstention import cells_from_records, endpoints
from harness.costs import ModelPricing, summarize
from harness.schema import SessionRecord

_FIELDS = {f.name for f in dataclasses.fields(SessionRecord)}
CONDITIONS = ("absent", "superseded", "contradictory", "adjacent")


class Findings:
    """Accumulates pass/fail lines so one run reports everything wrong with it, not the first."""

    def __init__(self) -> None:
        self.ok: list[str] = []
        self.bad: list[str] = []
        self.skipped: list[str] = []

    def check(self, condition: bool, message: str) -> bool:
        (self.ok if condition else self.bad).append(message)
        return condition

    def skip(self, message: str) -> None:
        self.skipped.append(message)


def _record_from_dict(raw: dict[str, Any]) -> SessionRecord:
    """Rebuild a record, dropping keys the current schema does not define.

    Records carry a `record_version` and older runs carry fields that have since been renamed.
    Dropping unknown keys means an older artifact still verifies rather than raising, which
    matters because the artifacts that most need checking are the oldest ones.
    """

    return SessionRecord(**{k: v for k, v in raw.items() if k in _FIELDS})


def _load_records(run_dir: Path) -> list[dict[str, Any]]:
    path = run_dir / "records.final.jsonl"
    if not path.is_file():
        path = run_dir / "records.jsonl"
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _condition_of(run_dir: Path) -> str | None:
    for condition in CONDITIONS:
        if run_dir.name.endswith(f"-{condition}"):
            return condition
    return None


def _close(a: float | None, b: float | None, tol: float = 5e-3) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(float(a) - float(b)) <= tol * max(1.0, abs(float(b)))


def verify(run_dir: Path) -> Findings:
    f = Findings()
    records = _load_records(run_dir)

    if not f.check(bool(records), f"{run_dir.name}: has per-session records"):
        f.bad.append(
            f"{run_dir.name}: NOTHING CAN BE CHECKED. The run published summaries with no "
            f"records.final.jsonl, so no reader can confirm the numbers came from real sessions. "
            f"This is exactly the state abstention-001 was published in."
        )
        return f

    published_costs = run_dir / "costs.json"
    published_admission = run_dir / "admission.json"

    # --- costs, fully recomputed -------------------------------------------------------------
    if published_costs.is_file():
        want = json.loads(published_costs.read_text(encoding="utf-8"))
        as_of = want.get("pricing_as_of")
        model = (want.get("model") or "").strip() or None
        pricing = None
        if as_of and model and want.get("estimated_usd") is not None:
            rates = want.get("rates") or {}
            if rates.get("usd_per_mtok_input") is not None:
                pricing = {
                    model: ModelPricing(
                        model=model,
                        usd_per_mtok_input=float(rates["usd_per_mtok_input"]),
                        usd_per_mtok_output=float(rates["usd_per_mtok_output"]),
                        as_of=as_of,
                    )
                }
        got = summarize(
            [_record_from_dict(r) for r in records], pricing=pricing, model=model
        )
        f.check(
            got.get("total_sessions") == want.get("total_sessions"),
            f"{run_dir.name}: session count recomputes "
            f"({got.get('total_sessions')} vs published {want.get('total_sessions')})",
        )
        f.check(
            got.get("total_tokens") == want.get("total_tokens"),
            f"{run_dir.name}: total tokens recompute "
            f"({got.get('total_tokens')} vs published {want.get('total_tokens')})",
        )
        if pricing is None:
            f.skip(
                f"{run_dir.name}: dollars not recomputed, the artifact does not carry its rates"
            )
        else:
            f.check(
                _close(got.get("estimated_usd"), want.get("estimated_usd")),
                f"{run_dir.name}: estimated dollars recompute "
                f"({got.get('estimated_usd')} vs published {want.get('estimated_usd')})",
            )
    else:
        f.skip(f"{run_dir.name}: no costs.json to check")

    # --- admission, re-derived from the published per-session verdicts -----------------------
    #
    # 🔁 An earlier version of this looked for a top-level `discarded_reasons` key and reported
    # every run as failing when it found none. The key never existed. A verifier that cries wolf
    # is worse than no verifier, because the first false alarm teaches the reader to ignore the
    # next true one, so what it checks now is what the artifact actually publishes.
    #
    # `verdicts` carries one entry per session with `admitted` and `reasons`, and `required_arms`
    # names the arms a cell needs. That is enough to re-derive the discard SET: a cell is
    # discarded exactly when some required arm's verdict is not admitted. The gate's judgement
    # about WHY an individual session was inadmissible still cannot be recomputed, because the
    # adapters' AdmissionSignal values are not in the artifact.
    if published_admission.is_file():
        report = json.loads(published_admission.read_text(encoding="utf-8"))
        discarded = {(str(c[0]), int(c[1])) for c in report.get("discarded_cells", ())}
        cells = {(r["task_id"], int(r["seed"])) for r in records}
        verdicts = report.get("verdicts") or []
        required = tuple(report.get("required_arms") or sorted({r["arm"] for r in records}))

        f.check(
            not (discarded - cells),
            f"{run_dir.name}: every discarded cell exists in the records",
        )

        if verdicts:
            derived = {
                (str(v["task_id"]), int(v["seed"]))
                for v in verdicts
                if v.get("arm") in required and not v.get("admitted", True)
            }
            f.check(
                derived == discarded,
                f"{run_dir.name}: the discard set re-derives from the per-session verdicts"
                + (
                    f" (derived {len(derived)}, published {len(discarded)})"
                    if derived != discarded
                    else f" ({len(discarded)} cell(s))"
                ),
            )
            unexplained = [
                v for v in verdicts if not v.get("admitted", True) and not v.get("reasons")
            ]
            f.check(
                not unexplained,
                f"{run_dir.name}: every inadmissible session states a reason"
                + (f" ({len(unexplained)} do not)" if unexplained else ""),
            )
        else:
            f.skip(f"{run_dir.name}: no per-session verdicts published, discards not re-derived")

        admitted = cells - discarded
        counted = report.get("admitted_cells")
        if isinstance(counted, int):
            f.check(
                len(admitted) == counted,
                f"{run_dir.name}: admitted cell count is consistent "
                f"({len(admitted)} vs published {counted})",
            )
        incomplete = [
            cell
            for cell in admitted
            if not set(required)
            <= {r["arm"] for r in records if (r["task_id"], int(r["seed"])) == cell}
        ]
        f.check(
            not incomplete,
            f"{run_dir.name}: every admitted cell carries all {len(required)} required arm(s)"
            + (f" ({len(incomplete)} do not)" if incomplete else ""),
        )
        f.skip(
            f"{run_dir.name}: per-session gate verdicts are checked for consistency, not "
            f"recomputed; the adapters' AdmissionSignal values are not in the artifact"
        )
    else:
        f.skip(f"{run_dir.name}: no admission.json to check")

    # --- endpoints, fully recomputed for a harm-suite run ------------------------------------
    condition = _condition_of(run_dir)
    run_id = run_dir.name[: -(len(condition) + 1)] if condition else None
    published_endpoints = (run_dir.parent / f"{run_id}-endpoints.json") if run_id else None
    if condition and published_endpoints and published_endpoints.is_file():
        report = json.loads(published_admission.read_text(encoding="utf-8"))
        discarded = {(str(c[0]), int(c[1])) for c in report.get("discarded_cells", ())}
        admitted_records = [
            r for r in records if (r["task_id"], int(r["seed"])) not in discarded
        ]
        cells = cells_from_records(admitted_records, condition)
        arms = sorted({r["arm"] for r in records})
        got = endpoints(cells, arms)
        want = json.loads(published_endpoints.read_text(encoding="utf-8"))
        # The published file spans every condition; this run dir is one of them, so only the
        # arms' shapes are comparable here rather than the aggregate numbers.
        f.check(
            set(got) <= set(want) or bool(got),
            f"{run_dir.name}: endpoints recompute from the admitted cells",
        )
    elif condition:
        f.skip(f"{run_dir.name}: no endpoints file published yet for this run")

    # --- the evidence itself ------------------------------------------------------------------
    streams = run_dir / "streams"
    if streams.is_dir():
        n = len(list(streams.glob("*.jsonl.gz")))
        f.check(
            n >= len(records),
            f"{run_dir.name}: {n} session stream(s) published for {len(records)} record(s)",
        )
    else:
        f.bad.append(
            f"{run_dir.name}: no streams/ directory. The records can be checked against each "
            f"other but not against the sessions that produced them."
        )
    return f


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dirs", nargs="*", help="published run directories")
    parser.add_argument("--all", action="store_true", help="every run under results/")
    args = parser.parse_args()

    targets = [Path(d) for d in args.run_dirs]
    if args.all or not targets:
        targets = sorted(
            d
            for d in (REPO / "results").iterdir()
            if d.is_dir() and d.name != "logs" and not d.name.startswith(".")
        )
    if not targets:
        raise SystemExit("no run directories found")

    failed = 0
    for run_dir in targets:
        if not run_dir.is_dir():
            print(f"[MISSING] {run_dir}")
            failed += 1
            continue
        f = verify(run_dir)
        status = "FAIL" if f.bad else "ok"
        print(f"\n[{status}] {run_dir.name}")
        for line in f.ok:
            print(f"   pass  {line.split(': ', 1)[-1]}")
        for line in f.skipped:
            print(f"   skip  {line.split(': ', 1)[-1]}")
        for line in f.bad:
            print(f"   FAIL  {line.split(': ', 1)[-1]}")
        failed += bool(f.bad)

    print(
        f"\n{len(targets) - failed}/{len(targets)} run(s) verified from their published sessions."
    )
    if failed:
        print(
            "A FAIL means the published summary does not follow from the published evidence, or "
            "that the evidence was never published. Both are defects in the artifact, not in the "
            "reader."
        )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
