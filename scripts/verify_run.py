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
import math
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from harness.abstention import cells_from_records, endpoints
from harness.adapters.base import IngestReport
from harness.costs import ModelPricing, summarize
from harness.damage import CORPUS_CONDITIONS
from harness.schema import SessionRecord

_FIELDS = {f.name for f in dataclasses.fields(SessionRecord)}
# Imported, never restated. This was a copy of the adversarial four, so a `-present` run
# directory matched no suffix, `_condition_of` returned None, and the endpoint re-derivation
# below was skipped in SILENCE: the verifier reported the run green having checked the one
# thing it exists to check on nothing.
CONDITIONS = CORPUS_CONDITIONS


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


#: Where a run's per-session records may live, in order of preference. The third is a real
#: published layout, not a courtesy: `abstention-001` put its records in `results/` as
#: `<run>-records.jsonl`, a SIBLING of the run directory rather than a file inside it. Found
#: 2026-09-02.
#:
#: ⚠️ This corrects a claim this repository makes about itself in three places. `verify_run`
#: reported "the run published summaries with no records.final.jsonl", the README repeated it as
#: "published with an admission file and a cost ledger and no records at all", and both were
#: wrong: 99 records per condition were published all along, under a different name. The evidence
#: was never missing, only unfindable, and a checker that cannot find evidence reports the same
#: string as one that finds none.
_RECORD_NAMES = ("records.final.jsonl", "records.jsonl")


def _record_paths(run_dir: Path) -> tuple[Path, ...]:
    inside = tuple(run_dir / name for name in _RECORD_NAMES)
    sibling = run_dir.parent / f"{run_dir.name}-records.jsonl"
    return inside + (sibling,)


def _load_records(run_dir: Path) -> list[dict[str, Any]]:
    for candidate in _record_paths(run_dir):
        if candidate.is_file():
            path = candidate
            break
    else:
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _load_ingest_reports(run_dir: Path) -> list[IngestReport]:
    """Rebuild the published ingest ledger from the run's environment manifest.

    Session token usage is carried by ``records.final.jsonl``.  Self-ingesting adapters also
    publish their hosted extraction usage in ``environment.json`` because ingest happens before
    the first session and cannot be attached to one session without double-counting it.  Reading
    that published report here makes the end-to-end total reproducible while keeping the verifier
    credential-free and avoiding any change to recorded session evidence.
    """

    path = run_dir / "environment.json"
    if not path.is_file():
        return []
    raw_reports = json.loads(path.read_text(encoding="utf-8")).get("ingest", [])
    if not isinstance(raw_reports, list):
        raise ValueError(f"{path} has a non-list ingest report")
    reports: list[IngestReport] = []
    for raw in raw_reports:
        if not isinstance(raw, dict):
            raise ValueError(f"{path} has a malformed ingest report")
        reports.append(
            IngestReport(
                arm=str(raw["arm"]),
                namespace=str(raw["namespace"]),
                sessions_offered=int(raw["sessions_offered"]),
                items_stored=(
                    int(raw["items_stored"]) if raw.get("items_stored") is not None else None
                ),
                wall_time_ms=(
                    float(raw["wall_time_ms"]) if raw.get("wall_time_ms") is not None else None
                ),
                llm_input_tokens=(
                    int(raw["llm_input_tokens"])
                    if raw.get("llm_input_tokens") is not None
                    else None
                ),
                llm_output_tokens=(
                    int(raw["llm_output_tokens"])
                    if raw.get("llm_output_tokens") is not None
                    else None
                ),
                local_model=(str(raw["local_model"]) if raw.get("local_model") else None),
                notes=tuple(str(note) for note in raw.get("notes", [])),
            )
        )
    return reports


def _condition_of(run_dir: Path) -> str | None:
    for condition in CONDITIONS:
        if run_dir.name.endswith(f"-{condition}"):
            return condition
    return None


def _close(a: float | None, b: float | None, tol: float = 5e-3) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(float(a) - float(b)) <= tol * max(1.0, abs(float(b)))



def _leaf_mismatches(got: object, want: object, path: str = "") -> list[str]:
    """Every leaf where a recomputation and a published value disagree, named by its path.

    Numbers compare at 1e-9 relative, NOT with `_close`, whose 0.5% band is right for a cost
    total accumulating float error over thousands of additions and wrong for a figure recomputed
    by the same function from the same integer counts. Everything else compares exactly. A
    missing key on either side is a mismatch rather than a skip, because a published endpoint
    that has lost a field is exactly as wrong as one carrying a bad number.
    """

    if isinstance(got, dict) and isinstance(want, dict):
        out: list[str] = []
        for key in sorted(set(got) | set(want)):
            here = f"{path}.{key}" if path else str(key)
            if key not in got:
                out.append(f"{here}: published but not recomputed")
            elif key not in want:
                out.append(f"{here}: recomputed but not published")
            else:
                out.extend(_leaf_mismatches(got[key], want[key], here))
        return out
    if isinstance(got, bool) or isinstance(want, bool):
        return [] if got is want else [f"{path}: recomputed {got!r}, published {want!r}"]
    if isinstance(got, (int, float)) and isinstance(want, (int, float)):
        # NOT `_close`, whose 0.5% band is right for a cost total that accumulates float error
        # across thousands of additions. An endpoint is recomputed by the SAME function from the
        # SAME integer counts, so it either reproduces to floating point or the published number
        # did not come from these sessions. Measured with the loose band: a net_harm perturbed by
        # 0.001 verified clean.
        return [] if math.isclose(float(got), float(want), rel_tol=1e-9, abs_tol=1e-12) else [
            f"{path}: recomputed {got!r}, published {want!r}"
        ]
    if isinstance(got, list) and isinstance(want, list):
        if len(got) != len(want):
            return [f"{path}: recomputed {len(got)} item(s), published {len(want)}"]
        out = []
        for i, (g, w) in enumerate(zip(got, want, strict=True)):
            out.extend(_leaf_mismatches(g, w, f"{path}[{i}]"))
        return out
    return [] if got == want else [f"{path}: recomputed {got!r}, published {want!r}"]


#: Endpoints keyed BY CONDITION, so a single-condition run directory recomputes its own slice
#: exactly. Endpoint 1 is pooled across every condition and is deliberately absent: one run dir
#: cannot check it, and it is SKIPPED by name below rather than quietly passed.
_CONDITION_KEYED_ENDPOINTS = (
    "2_damage_rate_by_condition",
    "3_abstention_rate",
    "4_wrong_fact_applied",
)



def _pooled_cells(run_dir: Path, run_id: str, conditions: list[str]):
    """Admitted cells from EVERY condition of this run, or (None, why) if the pool is incomplete.

    `1_net_harm_by_stratum` is computed over all conditions at once, so it cannot be checked from
    the single condition a run directory holds. It is also the headline endpoint, and leaving the
    headline unverifiable is how the tautology this replaced survived four gates: three of four
    fabrications were caught by the per-condition checks and a sign-flipped net_harm was not.
    """

    pooled = []
    for cond in conditions:
        sibling = run_dir.parent / f"{run_id}-{cond}"
        if not sibling.is_dir():
            return None, f"{sibling.name} is not published"
        admission = sibling / "admission.json"
        if not admission.is_file():
            return None, f"{sibling.name} has no admission.json"
        records = _load_records(sibling)
        if not records:
            return None, f"{sibling.name} has no records"
        report = json.loads(admission.read_text(encoding="utf-8"))
        discarded = {(str(c[0]), int(c[1])) for c in report.get("discarded_cells", ())}
        admitted = [r for r in records if (r["task_id"], int(r["seed"])) not in discarded]
        try:
            pooled.extend(cells_from_records(admitted, cond))
        except (KeyError, ValueError) as exc:
            return None, f"{sibling.name}: {exc}"
    return pooled, ""


def _check_endpoints(f, run_dir, records, condition, published_admission, published_endpoints):
    """Recompute this condition's endpoints and compare them VALUE BY VALUE.

    ⚠️ **What this cannot check, stated because a verifier that overpromises is worse than
    none.** The recomputation calls the SAME `endpoints()` the artifact was written with, so a
    defect inside that function makes the verifier and the artifact agree rather than disagree.
    That is not hypothetical: on 2026-08-30 `_paired` was found keying on `(task, seed, arm)`
    without the condition, which dropped roughly half the paired cells from the headline
    endpoint, and this check reported `pass` on the affected artifact throughout. What
    recomputation proves is that the published numbers FOLLOW FROM the published sessions by the
    published code. It cannot prove the code is right. Only a test of `endpoints()` itself can,
    which is why `tests/test_abstention_endpoints.py` asserts the pooled endpoint's denominator
    against the per-condition ones rather than against another call to the same function.

    ⚠️ This check used to read ``set(got) <= set(want) or bool(got)``, which is a tautology:
    ``endpoints()`` never returns an empty dict, so ``bool(got)`` is a constant True and the
    published file was parsed and discarded. A file claiming ``net_harm: -0.999`` over 999 tasks
    verified clean, and so did ``{}``. It is the one check that would catch a fabricated headline
    number, in the one script whose stated purpose is letting a reader who distrusts this
    benchmark check that its numbers follow from its sessions.
    """

    report = json.loads(published_admission.read_text(encoding="utf-8"))
    discarded = {(str(c[0]), int(c[1])) for c in report.get("discarded_cells", ())}
    admitted_records = [r for r in records if (r["task_id"], int(r["seed"])) not in discarded]
    try:
        cells = cells_from_records(admitted_records, condition)
    except (KeyError, ValueError) as exc:
        f.skip(f"{run_dir.name}: cells cannot be rebuilt from these records ({exc})")
        return
    arms = sorted({r["arm"] for r in records})
    got = endpoints(cells, arms)

    want = json.loads(published_endpoints.read_text(encoding="utf-8"))
    if not isinstance(want, dict):
        f.check(
            False,
            f"{run_dir.name}: published endpoints file is a "
            f"{type(want).__name__}, not an object",
        )
        return

    f.check(
        got.get("reference_arm") == want.get("reference_arm"),
        f"{run_dir.name}: endpoints name the same reference arm "
        f"(recomputed {got.get('reference_arm')!r}, published {want.get('reference_arm')!r})",
    )

    published_arms = want.get("arms")
    if not isinstance(published_arms, dict):
        f.check(False, f"{run_dir.name}: published endpoints carry no `arms` object")
        return

    for arm in sorted(set(got["arms"]) | set(published_arms)):
        if arm not in got["arms"]:
            f.check(False, f"{run_dir.name}: endpoints publish arm {arm!r}, which never ran")
            continue
        if arm not in published_arms:
            f.check(False, f"{run_dir.name}: arm {arm!r} ran but is absent from the endpoints")
            continue
        mine, theirs = got["arms"][arm], published_arms[arm]
        for block in _CONDITION_KEYED_ENDPOINTS:
            here = (mine.get(block) or {}).get(condition)
            there = (theirs.get(block) or {}).get(condition)
            if here is None and there is None:
                continue
            bad = _leaf_mismatches(here, there, f"{arm}.{block}")
            f.check(
                not bad,
                f"{run_dir.name}: {arm} endpoints {block}[{condition}] recompute from the "
                f"admitted cells" + ("" if not bad else "  ->  " + "; ".join(bad[:4])),
            )
    # The pooled endpoint, checked once per RUN rather than once per condition.
    conditions = want.get("conditions")
    run_id = run_dir.name[: -(len(condition) + 1)]
    if not isinstance(conditions, list) or not conditions:
        f.skip(
            f"{run_dir.name}: 1_net_harm_by_stratum is pooled, and the published file names no "
            f"`conditions`, so the pool cannot be rebuilt"
        )
    elif condition != min(conditions):
        f.skip(
            f"{run_dir.name}: 1_net_harm_by_stratum is pooled across {len(conditions)} "
            f"condition(s) and is checked once per run, on {run_id}-{min(conditions)}"
        )
    else:
        pooled, why = _pooled_cells(run_dir, run_id, sorted(conditions))
        if pooled is None:
            f.skip(
                f"{run_id}: 1_net_harm_by_stratum needs every condition of the run and {why}"
            )
        else:
            pooled_arms = sorted({c.arm for c in pooled})
            pooled_got = endpoints(pooled, pooled_arms)
            for arm in sorted(set(pooled_got["arms"]) & set(published_arms)):
                bad = _leaf_mismatches(
                    pooled_got["arms"][arm].get("1_net_harm_by_stratum"),
                    published_arms[arm].get("1_net_harm_by_stratum"),
                    f"{arm}.1_net_harm_by_stratum",
                )
                f.check(
                    not bad,
                    f"{run_id}: {arm} endpoints 1_net_harm_by_stratum recompute from all "
                    f"{len(conditions)} condition(s)"
                    + ("" if not bad else "  ->  " + "; ".join(bad[:4])),
                )


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
            [_record_from_dict(r) for r in records],
            _load_ingest_reports(run_dir),
            pricing=pricing,
            model=model,
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
    if not condition:
        # A skipped check and a passed check must never render the same. Naming the recognised
        # set makes the next unrecognised condition a one-line diagnosis instead of an audit.
        f.skip(
            f"{run_dir.name}: endpoints NOT re-derived, because the directory name ends in no "
            f"known condition ({', '.join(CONDITIONS)}). Nothing here checked the published "
            f"endpoint arithmetic."
        )
    elif published_endpoints and not published_endpoints.is_file():
        f.skip(
            f"{run_dir.name}: endpoints NOT re-derived; {published_endpoints.name} is absent."
        )
    if condition and published_endpoints and published_endpoints.is_file():
        if not published_admission.is_file():
            f.skip(
                f"{run_dir.name}: endpoints published but no admission.json, so the admitted "
                f"cells cannot be reconstructed"
            )
        else:
            _check_endpoints(f, run_dir, records, condition, published_admission,
                             published_endpoints)
    elif condition:
        f.skip(f"{run_dir.name}: no endpoints file published yet for this run")

    # --- the evidence itself ------------------------------------------------------------------
    streams = run_dir / "streams"
    if streams.is_dir():
        # 🔁 This used to demand one stream per record and failed every honest run that contained
        # a timeout. A session killed at the timeout leaves a record saying so and never flushes
        # its stream, so the strict form reported `official-001` as defective for four sessions
        # that behaved exactly as the protocol says they should. Crying wolf here is worse than
        # not checking, because it trains the reader to skim past the FAIL that matters.
        #
        # So a missing stream is a defect only when nothing in the record explains it. A recorded
        # error is the explanation; silence is not.
        have = {p.name.rsplit(".jsonl.gz", 1)[0] for p in streams.glob("*.jsonl.gz")}
        missing = [
            r
            for r in records
            if f"{r['task_id']}.s{r['seed']}.{r['arm']}" not in have
        ]
        unexplained = [r for r in missing if not r.get("error")]
        f.check(
            not unexplained,
            f"{run_dir.name}: {len(have)} stream(s) for {len(records)} record(s); "
            f"{len(missing)} absent, all explained by a recorded error"
            if missing and not unexplained
            else f"{run_dir.name}: {len(have)} session stream(s) for {len(records)} record(s)"
            if not missing
            else f"{run_dir.name}: {len(unexplained)} session(s) have no stream and no recorded "
            f"error, so nothing says why the evidence is absent",
        )
    else:
        f.bad.append(
            f"{run_dir.name}: no streams/ directory. The records can be checked against each "
            f"other but not against the sessions that produced them."
        )
    return f



#: Directories under results/ that are not runs. `archive` is written by
#: scripts/archive_partial.py, which deliberately parks an interrupted grid there; treating it as
#: a run made --all report "NOTHING CAN BE CHECKED" and exit 1 on a healthy repository. A verifier
#: that cries wolf is worse than no verifier, which this module says nine lines above the check
#: that was doing it.
#: `retrieval` joined them 2026-09-02: it holds `scripts/retrieval_probe.py --out` artifacts, one
#: JSON list per corpus root, and no agent session ever ran under it. Reporting it as a run whose
#: evidence is missing is a false alarm on a directory that will never have any.
_NOT_RUN_DIRS = frozenset({"logs", "archive", "retrieval"})

#: Runs whose per-session streams were never captured, with the reason, measured 2026-09-02 by
#: looking for them in this checkout, in the main checkout and on the run host. They are not
#: recoverable and there is nothing to publish.
#:
#: ⚠️ This ANNOTATES a failure. It does not silence one. Every run below still reports FAIL and
#: still counts against the verified total, because a reader who cannot check a run against its
#: sessions is in the same position whether or not we know why. What the note buys is that the
#: reader learns the reason from the tool instead of guessing at a defect.
#:
#: `tests/test_verify_run.py` asserts each of these still fails, so a note cannot outlive the
#: thing it explains: publish the streams and the test demands the note be deleted.
KNOWN_MISSING_STREAMS = {
    "abstention-001-absent": "streams were never captured for this run; the records were "
    "published as the sibling file results/abstention-001-absent-records.jsonl",
    "abstention-001-superseded": "streams were never captured for this run; the records were "
    "published as the sibling file results/abstention-001-superseded-records.jsonl",
    "midband-001": "streams were never captured for this run",
    "resolution-001": "streams were never captured for this run",
    "smoke-002": "a bring-up smoke run; 4 of its sessions have no stream",
    "smoke-abstention-absent": "a bring-up smoke run; streams were never captured",
    "smoke-sup2-superseded": "a bring-up smoke run; streams were never captured",
    "pilot-001": "the earliest pilot; 72 of its 287 sessions have a stream and 215 do not",
}


def _is_leaderboard_rollup(d: Path) -> bool:
    """True for a directory that carries only the published leaderboard roll-up.

    ``site/data/leaderboard.config.json`` points at ``results/<run_id>/leaderboard_summary.json``,
    and for a run measured per condition that summary is a roll-up ACROSS the five condition
    directories rather than a run of its own: ``official-003`` holds the summary while
    ``official-003-present`` and its four siblings hold the sessions. Reporting the roll-up as an
    unverifiable run is the wolf-crying this module warns about nine lines above, and it named the
    flagship run, which is the one a reader checks first.

    The test is that the summary is the ONLY thing there, never merely that records are absent.
    A run that lost its records while keeping everything else is a gutted run, and "no records"
    alone would hide exactly the artifact this verifier exists to catch. Requiring a lone file
    means anything still carrying an admission.json, a costs.json or a streams/ directory is
    reported however little else survives; ``tests/test_verify_run.py`` pins both halves.
    """

    contents = list(d.iterdir())
    return len(contents) == 1 and contents[0].name == "leaderboard_summary.json"


def _is_leaderboard_rollup(d: Path) -> bool:
    """True for a directory that carries only the published leaderboard roll-up.

    ``site/data/leaderboard.config.json`` points at ``results/<run_id>/leaderboard_summary.json``,
    and for a run measured per condition that summary is a roll-up ACROSS the five condition
    directories rather than a run of its own: ``official-003`` holds the summary while
    ``official-003-present`` and its four siblings hold the sessions. Reporting the roll-up as an
    unverifiable run is the wolf-crying this module warns about nine lines above, and it named the
    flagship run, which is the one a reader checks first.

    The test is that the summary is the ONLY thing there, never merely that records are absent.
    A run that lost its records while keeping everything else is a gutted run, and "no records"
    alone would hide exactly the artifact this verifier exists to catch. Requiring a lone file
    means anything still carrying an admission.json, a costs.json or a streams/ directory is
    reported however little else survives; ``tests/test_verify_run.py`` pins both halves.
    """

    contents = list(d.iterdir())
    return len(contents) == 1 and contents[0].name == "leaderboard_summary.json"



def run_targets(results: Path) -> list[Path]:
    """Every published run directory under `results`, in name order.

    A named function rather than a comprehension inside `main`, so a test can call the SELECTOR
    rather than restate it. The test that covered this first copied the comprehension into its own
    body and stayed green with both halves of the fix deleted.
    """

    return sorted(
        d
        for d in results.iterdir()
        if d.is_dir()
        and d.name not in _NOT_RUN_DIRS
        and not d.name.startswith(".")
        and not _is_leaderboard_rollup(d)
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dirs", nargs="*", help="published run directories")
    parser.add_argument("--all", action="store_true", help="every run under results/")
    args = parser.parse_args()

    targets = [Path(d) for d in args.run_dirs]
    if args.all or not targets:
        targets = run_targets(REPO / "results")
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
        note = KNOWN_MISSING_STREAMS.get(run_dir.name)
        if note and f.bad:
            # Printed AFTER the failure and counted as one, so the reason never reads as a pass.
            print(f"   note  KNOWN: {note}. See docs/STATUS.md.")
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
