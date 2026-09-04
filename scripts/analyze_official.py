"""Generate an auditable analysis for an official multi-condition run.

The official leaderboard summary is deliberately a small roll-up.  This script joins it to the
five condition runs and derives the useful questions a reader otherwise has to answer by hand:
what helped, what regressed, how much it cost, how long it took, and whether the result is safe to
compare.  It writes outside the summary-only run directory so ``verify_run`` keeps its roll-up
invariant.

Usage::

    python -m scripts.analyze_official --run-id official-003
    python -m scripts.analyze_official --run-id official-003 --check
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

CONDITIONS = ("present", "absent", "superseded", "contradictory", "adjacent")
BASELINE = "claude_md"
PRODUCTS = ("recall", "mempalace")
CONTROLS = ("bare", "placebo", "claude_md", "protocol", "fs_grep", "recall_prefetch")
REPORT_SCHEMA = 1


def _round(value: float | None, digits: int = 4) -> float | None:
    return None if value is None else round(float(value), digits)


def _rate(successes: int, cells: int) -> float | None:
    return _round(successes / cells, 4) if cells else None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _records(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _condition_data(run_dir: Path) -> dict[str, Any]:
    admission = _load_json(run_dir / "admission.json")
    costs = _load_json(run_dir / "costs.json")
    environment = _load_json(run_dir / "environment.json")
    records = _records(run_dir / "records.final.jsonl")
    discarded = {tuple(cell) for cell in admission.get("discarded_cells", ())}
    admitted = [record for record in records if (record["task_id"], record["seed"]) not in discarded]
    cells = sorted({(record["task_id"], int(record["seed"])) for record in admitted})
    return {
        "run_dir": run_dir,
        "admission": admission,
        "costs": costs,
        "environment": environment,
        "records": records,
        "admitted": admitted,
        "cells": cells,
        "discarded": discarded,
    }


def _arm_condition_stats(data: dict[str, Any], arms: tuple[str, ...]) -> dict[str, dict[str, Any]]:
    cells = data["cells"]
    by_arm_cell = {(record["arm"], (record["task_id"], int(record["seed"]))): record
                   for record in data["admitted"]}
    result: dict[str, dict[str, Any]] = {}
    for arm in arms:
        successes = sum(
            bool(by_arm_cell.get((arm, cell), {}).get("success", False)) for cell in cells
        )
        result[arm] = {"solved": successes, "cells": len(cells), "success": _rate(successes, len(cells))}
    return result


def _sum_costs(condition_data: list[dict[str, Any]], arms: tuple[str, ...]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for arm in arms:
        rows = [data["costs"].get("arms", {}).get(arm, {}) for data in condition_data]
        sessions = sum(int(row.get("sessions", 0)) for row in rows)
        result[arm] = {
            "observed_sessions": sessions,
            "unmetered_sessions": sum(int(row.get("sessions_unmetered", 0)) for row in rows),
            "total_tokens": sum(int(row.get("total_tokens", 0)) for row in rows),
            "input_tokens": sum(int(row.get("session_input_tokens", 0)) for row in rows),
            "output_tokens": sum(int(row.get("session_output_tokens", 0)) for row in rows),
            "total_usd": _round(sum(float(row.get("estimated_usd", 0.0) or 0.0) for row in rows)),
            "session_wall_time_ms": sum(float(row.get("session_wall_time_ms", 0.0) or 0.0) for row in rows),
            "ingest_wall_time_ms": sum(float(row.get("ingest_wall_time_ms", 0.0) or 0.0) for row in rows),
            "ingest_items_stored": sum(int(row.get("ingest_items_stored", 0) or 0) for row in rows),
            "ingest_models": sorted({str(row["ingest_local_model"]) for row in rows if row.get("ingest_local_model")}),
            "pricing_as_of": next((row.get("pricing_as_of") for row in rows if row.get("pricing_as_of")), None),
            "pricing_model": next((row.get("pricing_model") for row in rows if row.get("pricing_model")), None),
        }
    return result


def _admitted_cell_count(condition_data: list[dict[str, Any]]) -> int:
    return sum(len(data["cells"]) for data in condition_data)


def _raw_arm_stats(condition_data: list[dict[str, Any]], arms: tuple[str, ...]) -> dict[str, dict[str, Any]]:
    total_cells = _admitted_cell_count(condition_data)
    per_arm: dict[str, dict[str, Any]] = {}
    baseline_by_condition: dict[str, dict[str, Any]] = {}
    for condition, data in zip(CONDITIONS, condition_data, strict=True):
        stats = _arm_condition_stats(data, arms)
        baseline_by_condition[condition] = stats[BASELINE]
        for arm in arms:
            target = per_arm.setdefault(arm, {"by_condition": {}, "solved": 0})
            target["by_condition"][condition] = stats[arm]
            target["solved"] += stats[arm]["solved"]
    for arm in arms:
        item = per_arm[arm]
        item["cells"] = total_cells
        item["success"] = _rate(item["solved"], total_cells)
        item["condition_delta_vs_baseline"] = {
            condition: _round(
                item["by_condition"][condition]["success"] - baseline_by_condition[condition]["success"]
            )
            for condition in CONDITIONS
        }
    return per_arm


def _task_profiles(condition_data: list[dict[str, Any]], arms: tuple[str, ...]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, list[bool]]] = {}
    for data in condition_data:
        discarded = data["discarded"]
        for record in data["records"]:
            cell = (record["task_id"], int(record["seed"]))
            if cell in discarded:
                continue
            grouped.setdefault(record["task_id"], {}).setdefault(record["arm"], []).append(bool(record["success"]))
    profiles = {}
    for task, outcomes in sorted(grouped.items()):
        rates = {arm: _rate(sum(outcomes.get(arm, [])), len(outcomes.get(arm, []))) for arm in arms}
        profiles[task] = {
            "cells": len(outcomes.get(BASELINE, [])),
            "success": rates,
            "delta_vs_baseline": {
                arm: _round(rates[arm] - rates[BASELINE])
                for arm in arms
                if rates[arm] is not None and rates[BASELINE] is not None
            },
        }
    return profiles


def _quality_checks(
    repo_root: Path,
    run_id: str,
    summary: dict[str, Any],
    condition_data: list[dict[str, Any]],
    raw_stats: dict[str, dict[str, Any]],
    costs: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    def check(name: str, status: str, detail: str) -> None:
        checks.append({"name": name, "status": status, "detail": detail})

    config = _load_json(repo_root / "site" / "data" / "leaderboard.config.json")
    check("config_points_to_run", "pass" if config.get("official_run") == run_id else "fail",
          f"official_run={config.get('official_run')!r}")
    check("summary_run_id", "pass" if summary.get("run", {}).get("id") == run_id else "fail",
          f"summary run id={summary.get('run', {}).get('id')!r}")
    required_files = ("admission.json", "costs.json", "environment.json", "records.final.jsonl")
    missing = [str(data["run_dir"] / name) for data in condition_data for name in required_files if not (data["run_dir"] / name).is_file()]
    check("condition_artifacts", "pass" if not missing else "fail", "all required artifacts exist" if not missing else f"missing {missing}")

    rosters = [tuple(data["admission"].get("required_arms", ())) for data in condition_data]
    roster_ok = bool(rosters) and all(roster == rosters[0] for roster in rosters)
    check("condition_rosters", "pass" if roster_ok else "fail", f"required arms={rosters[0] if rosters else ()}")

    duplicate_cells = []
    bad_cell_counts = []
    for data in condition_data:
        seen = set()
        for record in data["admitted"]:
            key = (record["arm"], record["task_id"], int(record["seed"]))
            if key in seen:
                duplicate_cells.append(f"{data['run_dir'].name}:{key}")
            seen.add(key)
        expected = len(data["cells"])
        for arm in rosters[0] if rosters else ():
            actual = sum(1 for record in data["admitted"] if record["arm"] == arm)
            if actual != expected:
                bad_cell_counts.append(f"{data['run_dir'].name}:{arm}={actual}/{expected}")
    cell_ok = not duplicate_cells and not bad_cell_counts
    detail = "one admitted record per arm and cell" if cell_ok else f"duplicates={duplicate_cells}; counts={bad_cell_counts}"
    check("admitted_cell_integrity", "pass" if cell_ok else "fail", detail)

    admission_ok = all(data["admission"].get("admitted_cells") == len(data["cells"]) for data in condition_data)
    check("admission_rederives", "pass" if admission_ok else "fail", "admitted cells match the discarded set")

    summary_mismatches = []
    for arm, published in summary.get("arms", {}).items():
        actual = raw_stats.get(arm)
        if not actual:
            continue
        if abs(float(published.get("success")) - float(actual["success"])) > 0.0001:
            summary_mismatches.append(f"{arm}.success {published.get('success')} != {actual['success']}")
        for condition in CONDITIONS:
            expected = published.get("byCondition", {}).get(condition)
            measured = actual["by_condition"].get(condition)
            if expected and measured and (expected.get("solved"), expected.get("cells")) != (measured["solved"], measured["cells"]):
                summary_mismatches.append(f"{arm}.{condition}")
    check("summary_matches_records", "pass" if not summary_mismatches else "fail",
          "headline and condition counts rederive from records" if not summary_mismatches else f"mismatches={summary_mismatches}")

    token_mismatches = []
    discarded_mismatches = []
    for arm, published in summary.get("arms", {}).items():
        cost = costs.get(arm, {})
        if published.get("totalTokens") is not None and int(published["totalTokens"]) != int(cost.get("total_tokens", 0)):
            token_mismatches.append(f"{arm} totalTokens")
        actual_discarded = sum(int(data["admission"].get("discarded_by_arm", {}).get(arm, 0)) for data in condition_data)
        if published.get("discarded") is not None and int(published["discarded"]) != actual_discarded:
            discarded_mismatches.append(f"{arm} discarded")
    check("summary_matches_costs", "pass" if not token_mismatches else "fail",
          "published token totals match ledgers" if not token_mismatches else f"mismatches={token_mismatches}")
    check("summary_matches_admission", "pass" if not discarded_mismatches else "fail",
          "discard counts match admission ledgers" if not discarded_mismatches else f"mismatches={discarded_mismatches}")

    denominator_mismatches = []
    for arm, published in summary.get("arms", {}).items():
        observed = costs.get(arm, {}).get("total_tokens", 0)
        sessions = costs.get(arm, {}).get("observed_sessions", 0)
        expected = round(observed / sessions) if sessions else None
        if published.get("tokensPerTask") is not None and expected is not None and int(published["tokensPerTask"]) != expected:
            denominator_mismatches.append(f"{arm}: published {published['tokensPerTask']}, observed-session rate {expected}")
    check("published_token_rate_denominator", "warn" if denominator_mismatches else "pass",
          "token rate uses the observed session denominator" if not denominator_mismatches else "; ".join(denominator_mismatches))

    prereg = repo_root / str(summary.get("run", {}).get("prereg", ""))
    prereg_text = prereg.read_text(encoding="utf-8") if prereg.is_file() else ""
    mid_run = bool(re.search(r"REGISTERED MID RUN", prereg_text, re.IGNORECASE))
    check("preregistration_timing", "warn" if mid_run else ("pass" if prereg.is_file() else "fail"),
          "the preregistration discloses that it was registered mid run" if mid_run else "preregistration exists")
    if not bool(config.get("write_path_measured", False)):
        check("write_path_scope", "warn", "the leaderboard measures retrieval over a bulk-ingested corpus; write path is not measured")
    if summary.get("run", {}).get("sessionsPerCell") == 1:
        check("replication_depth", "warn", "one session per cell; uncertainty excludes run to run variance")
    return checks


def _hold_map() -> dict[str, dict[str, str]]:
    try:
        from scripts.build_leaderboard import VENDOR_REVIEW_HOLDS
        return VENDOR_REVIEW_HOLDS
    except ImportError:
        return {}


def _arm_analysis(
    arm: str,
    raw: dict[str, Any],
    cost: dict[str, Any],
    summary: dict[str, Any],
    profiles: dict[str, dict[str, Any]],
    all_stats: dict[str, dict[str, Any]],
    total_cells: int,
    discarded_cells: int,
    hold: dict[str, str] | None,
) -> dict[str, Any]:
    published = summary.get("arms", {}).get(arm, {})
    baseline = all_stats[BASELINE]
    success = raw["success"]
    delta = _round(success - baseline["success"])
    mean_wall_s = cost["session_wall_time_ms"] / 1000 / cost["observed_sessions"] if cost["observed_sessions"] else None
    baseline_cost = None
    baseline_time = None
    if arm != BASELINE:
        baseline_cost = all_stats.get("__cost__", {}).get(BASELINE, {}).get("total_usd")
        baseline_time = all_stats.get("__cost__", {}).get(BASELINE, {}).get("mean_session_s")
    payload: dict[str, Any] = {
        "status": "held" if hold else "published",
        "success": success,
        "delta_vs_baseline": delta,
        "ci95": published.get("ci"),
        "solved_cells": raw["solved"],
        "admitted_cells": total_cells,
        "discarded_cells": discarded_cells,
        "by_condition": raw["by_condition"],
        "condition_delta_vs_baseline": raw["condition_delta_vs_baseline"],
        "cost": {
            "total_usd": cost["total_usd"],
            "usd_per_admitted_cell": _round(cost["total_usd"] / total_cells, 4) if total_cells else None,
            "total_tokens": cost["total_tokens"],
            "tokens_per_observed_session": round(cost["total_tokens"] / cost["observed_sessions"]) if cost["observed_sessions"] else None,
            "tokens_per_admitted_cell": round(cost["total_tokens"] / total_cells) if total_cells else None,
            "pricing_model": cost["pricing_model"],
            "pricing_as_of": cost["pricing_as_of"],
        },
        "speed": {
            "mean_session_s": _round(mean_wall_s, 2),
            "ingest_s": _round(cost["ingest_wall_time_ms"] / 1000, 2),
            "ingest_s_per_admitted_cell": _round(cost["ingest_wall_time_ms"] / 1000 / total_cells, 3) if total_cells else None,
            "ingest_items_stored": cost["ingest_items_stored"],
            "ingest_models": cost["ingest_models"],
        },
        "efficiency": {
            "successes_per_million_tokens": _round(raw["solved"] / cost["total_tokens"] * 1_000_000, 2) if cost["total_tokens"] else None,
            "successes_per_dollar": _round(raw["solved"] / cost["total_usd"], 2) if cost["total_usd"] else None,
        },
        "strongest_gains": [],
        "largest_losses": [],
    }
    if baseline_cost is not None:
        payload["cost"]["relative_to_baseline"] = _round(cost["total_usd"] / baseline_cost - 1, 4) if baseline_cost else None
    if baseline_time is not None:
        payload["speed"]["relative_to_baseline"] = _round(mean_wall_s / baseline_time - 1, 4) if mean_wall_s is not None and baseline_time else None

    task_deltas = [(task, values["delta_vs_baseline"].get(arm)) for task, values in profiles.items() if arm in values["delta_vs_baseline"]]
    payload["strongest_gains"] = [{"task": task, "delta": delta} for task, delta in sorted(task_deltas, key=lambda pair: (pair[1], pair[0]), reverse=True)[:5] if delta > 0]
    payload["largest_losses"] = [{"task": task, "delta": delta} for task, delta in sorted(task_deltas, key=lambda pair: (pair[1], pair[0]))[:5] if delta < 0]
    if hold:
        return {"status": "held", "hold": hold}
    return payload


def _insights(
    arms: dict[str, dict[str, Any]],
    costs: dict[str, dict[str, Any]],
    summary: dict[str, Any],
    product_names: tuple[str, ...],
) -> list[str]:
    visible = [arm for arm, data in arms.items() if data.get("status") != "held"]
    winner = max(visible, key=lambda arm: arms[arm]["success"])
    products = [arm for arm in product_names if arm in arms and arms[arm].get("status") != "held"]
    best_product = max(products, key=lambda arm: arms[arm]["success"]) if products else None
    insights = [
        f"{winner} is the highest scoring visible arm at {arms[winner]['success']:.1%}; this is not evidence that a memory layer won.",
        f"{best_product} is the highest scoring visible memory product at {arms[best_product]['success']:.1%}." if best_product else "No visible memory product has a publishable score.",
    ]
    if "placebo" in arms and arms["placebo"].get("success") is not None:
        insights.append(f"The placebo exceeds the claude_md baseline by {arms['placebo']['delta_vs_baseline']:+.1%}, so the run does not isolate a memory benefit cleanly.")
    for arm in products:
        data = arms[arm]
        if data.get("delta_vs_baseline", 0) > 0 and data.get("ci95") and data["ci95"][0] <= 0 <= data["ci95"][1]:
            insights.append(f"{arm} shows a positive point estimate, but its published 95% interval crosses zero.")
        if data.get("cost", {}).get("relative_to_baseline", 0) > 0.5:
            insights.append(f"{arm} costs {data['cost']['relative_to_baseline'] + 1:.1f} times the baseline per admitted cell, including retrieval context tokens.")
    if any(data.get("status") == "held" for data in arms.values()):
        insights.append("A vendor review hold suppresses one product's metrics from the public analysis until the hold is released.")
    return insights


def _additive_arm_analysis(
    repo_root: Path,
    base_run_id: str,
    summary: dict[str, Any],
    baseline_stats: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Project accepted joined vendor submissions into the same report schema.

    Additive submissions intentionally publish a joined summary rather than rerunning the frozen
    base arms. Their result has no wall time field, so the report exposes submitted cost and token
    rates while leaving speed and per-cell spend unavailable instead of inventing a denominator.
    """

    config = _load_json(repo_root / "site" / "data" / "leaderboard.config.json")
    arm_runs = config.get("arm_runs", {}) or {}
    if not isinstance(arm_runs, dict) or not arm_runs:
        return {}
    from scripts.build_leaderboard import _load_arm_submission

    analyzed: dict[str, dict[str, Any]] = {}
    for arm, configured in arm_runs.items():
        submission_run = configured.get("run") if isinstance(configured, dict) else configured
        if not isinstance(submission_run, str) or not submission_run:
            raise ValueError(f"arm_runs entry {arm!r} must name a result run")
        submission = _load_arm_submission(repo_root / "results", submission_run, arm, base_run_id, summary)
        result = submission["result"]
        join = submission["join"]
        by_condition = result.get("byCondition", {})
        condition_delta = {}
        for condition in CONDITIONS:
            product = by_condition.get(condition, {})
            baseline = baseline_stats["by_condition"].get(condition, {})
            product_rate = _rate(int(product.get("solved", 0)), int(product.get("cells", 0)))
            baseline_rate = baseline.get("success")
            condition_delta[condition] = _round(product_rate - baseline_rate) if product_rate is not None and baseline_rate is not None else None
        held = _hold_map().get(arm)
        if held:
            analyzed[arm] = {"status": "held", "hold": held}
            continue
        joined_cells = int(join["joinedCells"])
        total_tokens = int(result["totalTokens"])
        analyzed[arm] = {
            "status": "published",
            "comparison": f"joined to {base_run_id}",
            "source_run": submission_run,
            "success": float(result["success"]),
            "delta_vs_baseline": float(result["delta"]),
            "ci95": result.get("ci"),
            "solved_cells": None,
            "admitted_cells": joined_cells,
            "discarded_cells": int(result.get("discarded", 0)),
            "by_condition": by_condition,
            "condition_delta_vs_baseline": condition_delta,
            "cost": {
                "total_usd": None,
                "usd_per_admitted_cell": None,
                "reported_usd_per_task": result.get("costPerTask"),
                "total_tokens": total_tokens,
                "tokens_per_observed_session": result.get("tokensPerTask"),
                "tokens_per_admitted_cell": round(total_tokens / joined_cells) if joined_cells else None,
                "pricing_model": submission["run"].get("model"),
                "pricing_as_of": None,
                "relative_to_baseline": None,
            },
            "speed": {"mean_session_s": None, "ingest_s": None, "relative_to_baseline": None},
            "efficiency": {},
            "strongest_gains": [],
            "largest_losses": [],
            "join": join,
        }
    return analyzed


def analyze(repo_root: Path, run_id: str) -> tuple[dict[str, Any], dict[str, Any], str, str]:
    results_root = repo_root / "results"
    summary_path = results_root / run_id / "leaderboard_summary.json"
    summary = _load_json(summary_path)
    condition_data = []
    for condition in CONDITIONS:
        condition_data.append(_condition_data(results_root / f"{run_id}-{condition}"))

    arms = tuple(summary.get("arms", {}).keys()) + tuple(
        name for name in summary.get("reference", {}) if name not in summary.get("arms", {})
    )
    raw_stats = _raw_arm_stats(condition_data, arms)
    costs = _sum_costs(condition_data, arms)
    total_cells = _admitted_cell_count(condition_data)
    profiles = _task_profiles(condition_data, arms)
    all_stats = {**raw_stats, "__cost__": {}}
    for arm, cost in costs.items():
        cost["mean_session_s"] = cost["session_wall_time_ms"] / 1000 / cost["observed_sessions"] if cost["observed_sessions"] else None
        all_stats["__cost__"][arm] = cost

    holds = _hold_map()
    analyzed_arms = {
        arm: _arm_analysis(
            arm,
            raw_stats[arm],
            costs[arm],
            summary,
            profiles,
            all_stats,
            total_cells,
            sum(int(item["admission"].get("discarded_by_arm", {}).get(arm, 0)) for item in condition_data),
            holds.get(arm),
        )
        for arm in arms
    }
    additive_arms = _additive_arm_analysis(repo_root, run_id, summary, raw_stats[BASELINE])
    analyzed_arms.update(additive_arms)
    product_names = PRODUCTS + tuple(additive_arms)
    checks = _quality_checks(repo_root, run_id, summary, condition_data, raw_stats, costs)
    failures = sum(check["status"] == "fail" for check in checks)
    warnings = sum(check["status"] == "warn" for check in checks)
    audit = {
        "schema": REPORT_SCHEMA,
        "generated_by": "scripts/analyze_official.py",
        "run_id": run_id,
        "status": "fail" if failures else ("warn" if warnings else "pass"),
        "counts": {"pass": len(checks) - failures - warnings, "warn": warnings, "fail": failures},
        "checks": checks,
        "sources": {
            "summary": str(summary_path.relative_to(repo_root)).replace("\\", "/"),
            "summary_sha256": _sha256(summary_path),
            "condition_runs": [str(data["run_dir"].relative_to(repo_root)).replace("\\", "/") for data in condition_data],
        },
    }
    visible_arms = {arm: data for arm, data in analyzed_arms.items() if data.get("status") != "held"}
    overall_winner = max(visible_arms, key=lambda arm: visible_arms[arm]["success"]) if visible_arms else None
    visible_products = {arm: analyzed_arms[arm] for arm in PRODUCTS if arm in analyzed_arms and analyzed_arms[arm].get("status") != "held"}
    best_product = max(visible_products, key=lambda arm: visible_products[arm]["success"]) if visible_products else None
    leaderboard = {
        "status": audit["status"],
        "headline": "No clear memory winner" if best_product is None or any(
            analyzed_arms[arm].get("ci95") and analyzed_arms[arm]["ci95"][0] <= 0 <= analyzed_arms[arm]["ci95"][1]
            for arm in visible_products
        ) else "Memory result is statistically distinguishable",
        "overall_winner": {"arm": overall_winner, "success": visible_arms[overall_winner]["success"]} if overall_winner else None,
        "best_visible_memory": {"arm": best_product, "success": visible_products[best_product]["success"], "delta_vs_baseline": visible_products[best_product]["delta_vs_baseline"]} if best_product else None,
        "admitted_cells": total_cells,
        "conditions": list(CONDITIONS),
        "insights": _insights(analyzed_arms, costs, summary, product_names),
        "report_markdown": f"reports/{run_id}-analysis.md",
        "audit_json": f"reports/{run_id}-audit.json",
        "arms": {
            arm: {
                key: value
                for key, value in data.items()
                if key in ("status", "success", "delta_vs_baseline", "ci95", "cost", "speed", "efficiency", "hold")
            }
            for arm, data in analyzed_arms.items()
        },
    }
    report = {
        "schema": REPORT_SCHEMA,
        "generated_by": "scripts/analyze_official.py",
        "run": summary["run"],
        "sources": audit["sources"],
        "audit": {"status": audit["status"], "counts": audit["counts"]},
        "headline": {
            "overall_winner": overall_winner,
            "best_visible_memory": best_product,
            "admitted_cells": total_cells,
            "conditions": list(CONDITIONS),
            "records": sum(len(data["records"]) for data in condition_data),
            "discarded_cells": sum(len(data["discarded"]) for data in condition_data),
        },
        "insights": leaderboard["insights"],
        "arms": analyzed_arms,
        "task_profiles": profiles,
        "leaderboard": leaderboard,
        "audit_details": audit,
    }
    markdown = render_markdown(report)
    audit_markdown = render_audit_markdown(audit)
    return report, audit, markdown, audit_markdown


def render_markdown(report: dict[str, Any]) -> str:
    run = report["run"]
    headline = report["headline"]
    lines = [
        f"# Official run analysis: {run['id']}",
        "",
        f"Generated from {headline['records']:,} records across {headline['admitted_cells']:,} admitted cells and five corpus conditions.",
        "",
        "## Decision",
        "",
        f"Overall winner among visible arms: `{headline['overall_winner']}`." if headline["overall_winner"] else "No visible arm has a score.",
        f"Best visible memory product: `{headline['best_visible_memory']}`." if headline["best_visible_memory"] else "No visible memory product has a score.",
        "",
        *[f"1. {insight}" for insight in report["insights"]],
        "",
        "The intervals are within run intervals over the admitted cells. They do not include run to run variance. The write path is not measured, so this is a retrieval comparison over a bulk ingested corpus.",
        "",
        "## Tradeoffs by arm",
        "",
        "| arm | success | delta vs baseline | cost per admitted cell or task | mean session seconds | tokens per admitted cell | status |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for arm, data in report["arms"].items():
        if data.get("status") == "held":
            lines.append(f"| `{arm}` | withheld | withheld | withheld | withheld | withheld | {data['hold']['reason']} |")
            continue
        cost = data["cost"].get("usd_per_admitted_cell")
        cost_text = f"${cost:.4f}" if cost is not None else (
            f"${data['cost']['reported_usd_per_task']:.4f}/task"
            if data["cost"].get("reported_usd_per_task") is not None else "n/a"
        )
        speed_text = f"{data['speed']['mean_session_s']:.2f}" if data["speed"].get("mean_session_s") is not None else "n/a"
        token_text = f"{data['cost']['tokens_per_admitted_cell']:,}" if data["cost"].get("tokens_per_admitted_cell") is not None else "n/a"
        lines.append(
            f"| `{arm}` | {data['success']:.1%} | {data['delta_vs_baseline']:+.1%} | {cost_text} | {speed_text} | {token_text} | {data.get('comparison', 'published')} |"
        )
    lines.extend(["", "## Condition analysis", "", "The condition delta is measured against `claude_md` within the same condition.", ""])
    lines.extend(["| arm | " + " | ".join(CONDITIONS) + " |", "|---|" + "---:|" * len(CONDITIONS)])
    for arm, data in report["arms"].items():
        if data.get("status") == "held":
            lines.append(f"| `{arm}` | " + " | ".join(["withheld"] * len(CONDITIONS)) + " |")
        else:
            values = [data["condition_delta_vs_baseline"].get(condition) for condition in CONDITIONS]
            lines.append(f"| `{arm}` | " + " | ".join("n/a" if value is None else f"{value:+.1%}" for value in values) + " |")
    lines.extend(["", "## Strengths and weaknesses", ""])
    for arm, data in report["arms"].items():
        if data.get("status") == "held":
            lines.append(f"1. `{arm}`: metrics withheld while the vendor review hold is active.")
            continue
        gains = ", ".join(f"`{item['task']}` ({item['delta']:+.1%})" for item in data["strongest_gains"][:3]) or "none"
        losses = ", ".join(f"`{item['task']}` ({item['delta']:+.1%})" for item in data["largest_losses"][:3]) or "none"
        lines.append(f"1. `{arm}`: strongest gains {gains}; largest losses {losses}.")
    lines.extend(["", "## Audit status", "", f"Audit status: **{report['audit']['status']}**. See the generated audit artifact for each check and its evidence.", ""])
    return "\n".join(lines).rstrip("\n") + "\n"


def render_audit_markdown(audit: dict[str, Any]) -> str:
    lines = [f"# Official run audit: {audit['run_id']}", "", f"Status: **{audit['status']}**.", "", "| check | status | detail |", "|---|---|---|"]
    for item in audit["checks"]:
        lines.append(f"| `{item['name']}` | **{item['status']}** | {item['detail']} |")
    lines.extend(["", "## Source artifacts", "", f"Summary: `{audit['sources']['summary']}`", "", f"Summary SHA256: `{audit['sources']['summary_sha256']}`", ""])
    lines.extend(f"1. `{path}`" for path in audit["sources"]["condition_runs"])
    return "\n".join(lines) + "\n"


def _write_or_check(path: Path, expected: str, check: bool) -> None:
    current = path.read_text(encoding="utf-8") if path.is_file() else None
    if check:
        if current != expected:
            raise SystemExit(f"{path} does not match regeneration")
    else:
        path.write_text(expected, encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default="official-003")
    parser.add_argument("--root", default=REPO, type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report, audit, markdown, audit_markdown = analyze(args.root, args.run_id)
    report_path = args.root / "reports" / f"{args.run_id}-analysis.json"
    audit_path = args.root / "reports" / f"{args.run_id}-audit.json"
    markdown_path = args.root / "reports" / f"{args.run_id}-analysis.md"
    audit_markdown_path = args.root / "reports" / f"{args.run_id}-audit.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    _write_or_check(report_path, json.dumps(report, indent=2) + "\n", args.check)
    _write_or_check(audit_path, json.dumps(audit, indent=2) + "\n", args.check)
    _write_or_check(markdown_path, markdown, args.check)
    _write_or_check(audit_markdown_path, audit_markdown, args.check)
    print(json.dumps({"run_id": args.run_id, "audit": audit["status"], "analysis": str(markdown_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
