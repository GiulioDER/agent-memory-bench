"""Generate site/data/leaderboard.js from published results. Never from a keyboard.

The site promises that every number on the leaderboard traces to a published run
directory. This script is the only path a number takes to the page, and
``tests/test_leaderboard_generated.py`` fails CI whenever the committed file differs from
its regeneration, so a hand-edited number cannot survive review.

Inputs, both committed:

- ``site/data/leaderboard.config.json`` holds the pointer, never a number:
  ``{"official_run": null | "<run_id>", "arm_runs": {}, "updated": "YYYY-MM-DD"}``.
- When ``official_run`` is set, ``results/<run_id>/leaderboard_summary.json`` supplies the
  numbers. Its shape (fractions for rates, points as fractions, USD for cost)::

      {
        "run": {"id", "date", "cli", "model", "tasks", "sessionsPerCell", "prereg"},
        "arms": {"<arm>": {"success", "delta", "ci", "discarded", "tokensPerTask",
                            "costPerTask", "totalTokens"}},
        "reference": {"oracle_memory": {"success", "delta"},
                      "recall_prefetch": {"success", "delta"}}
      }

  Every product arm must be present, exactly once, and ``claude_md``'s delta must be 0:
  a summary that drops an embarrassing arm, invents a new one, or moves the baseline is
  refused, not smoothed over.

  ``arm_runs`` may add an independently measured arm without changing that frozen summary. Each
  entry names a result directory containing ``arm_summary.json``. The submission is joined to the
  base run and carries its own provenance, so a new runner does not have to rerun the grid.

Disclosure is a separate, later step. A run summary always carries the internal arm names;
what reaches the page is decided by ``PRODUCT_ARMS``, and an arm whose vendor has not been
announced yet is emitted under a neutral ``product_a``/``product_b`` label. The pages
therefore publish the shape of the grid without naming a product before its review
invitation has gone out, and nothing downstream of the harness has to know the difference.

Usage, from the repository root:

    python scripts/build_leaderboard.py           # regenerate the file in place
    python scripts/build_leaderboard.py --check   # fail if the committed file differs
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

# One entry per arm, in display order. The structure lives here; numbers never do.
#
# The fourth field is the name the SITE is allowed to print. ``None`` means the arm is not
# named publicly yet: the third-party products are unannounced, their vendor-review
# invitations have not gone out, and the pages carry a neutral placeholder instead. The
# first field is the INTERNAL name, which the harness, the adapters, the admission gate and
# every run summary use, and which never changes. Disclosing an arm is a one-word edit here
# plus a regeneration; nothing else in the harness moves.
PRODUCT_ARMS = [
    # internal name, integration, role, public name (None while undisclosed)
    ("recall", "MCP server", None, "recall"),
    ("mempalace", "MCP server", None, "mempalace"),
    ("fs_grep", "transcripts on disk plus grep", "control", "fs_grep"),
    ("placebo", "inert prose, no memory content", "control", "placebo"),
    ("claude_md", "CLAUDE.md bundle", "baseline", "claude_md"),
    ("bare", "no memory", "floor", "bare"),
]

# Arms that may be added by an independently validated submission.  They are deliberately kept
# out of PRODUCT_ARMS: the frozen base run must continue to validate against the exact roster it
# actually measured.  Adding a name here makes the adapter eligible for a later additive board
# entry; it does not publish a row by itself.
ADDITIVE_ARM_DEFINITIONS = {
    # internal name: integration, role, public name
    "cognee": ("MCP server", None, None),
    "supermemory": ("MCP server", None, None),
}

# ⛔ This list is the arms that are MEASURED, not the arms that are hoped for. `mem0`,
# `supermemory`, `zep` and `cognee` sat here for weeks with no adapter behind any of them, which
# put four permanently null rows on a public leaderboard and read as "measured, scored nothing"
# rather than "not built".
#
# `mempalace` left for the same reason on 2026-08-31: preregistration 021's second amendment
# defers it from `official-002` on a measured ingest cost, so it is built, not running, and a row
# for it would be null for the length of a run it is not in. It RETURNED on 2026-09-01, named,
# because `official-003` runs it: the ingest cost was paid once into a reusable base palace, and
# an arm belongs on the board exactly when the approved run runs it.
#
# `protocol` is a reference track rather than a product because it is not one. It carries the
# shared memory instruction with no memory behind it, which is what makes the products' numbers
# readable: the instruction alone is a treatment with its own effect, and every memory product
# pays for it before it retrieves anything. `fs_grep` arrived by the reverse
# move: it was excluded while it was not in the official roster, and the same amendment puts it in
# as the non-memory retrieval control. An arm belongs here when the approved run runs it.

# Third-party products this repository holds material about, and which `site/` may NOT name.
# Kept apart from PRODUCT_ARMS on purpose: leaderboard membership tracks what a run MEASURES,
# disclosure tracks what has had its review window, and the two came apart the moment an arm was
# deferred. Removing an arm from the board must not quietly remove it from this guard.
# `tests/test_site_vendor_disclosure.py` reads this.
UNDISCLOSED_PRODUCTS = ("mem0", "supermemory", "zep", "cognee", "cachly")

# What an undisclosed arm looks like on the page. The integration description is withheld
# with the name, because "SaaS API" against a short field of candidates is most of an
# identification on its own.
UNDISCLOSED_TYPE = "third-party product, not yet named"
UNDISCLOSED_PREFIX = "product_"

# What the page is allowed to call itself while the write path is unmeasured.
#
# The corpus is bulk ingested once, before the grid, and never written to again, so a ranking built
# from it ranks retrieval and nothing else: a product whose value is extraction and consolidation
# at write time gets no credit for either and full exposure to the lossiness of the first. So no
# multi-product ranking ships until `preregistration/006` has run, or it ships titled for what it
# actually measured.
#
# It is enforced here rather than promised in a README because a promise about a title is exactly
# the kind of thing a launch deadline edits. `write_path_measured` in the config is the only switch,
# and flipping it without naming the longitudinal run that justifies it is refused below.
RETRIEVAL_ONLY_TITLE = "Retrieval over a bulk-ingested corpus"
RETRIEVAL_ONLY_QUALIFICATION = (
    "The write path is not measured. Every arm was handed the same corpus before the grid and "
    "never wrote to its own store, so this ranks retrieval, not memory formation, and it gives "
    "no credit to extraction or consolidation at write time."
)
FULL_TITLE = "Memory layers, read and write path"

# Diagnostics, never ranked. `oracle_memory` left on 2026-08-31: its bundles carry no corpus
# condition, so it would supply verified evidence under `absent`, the condition whose whole point
# is that the corpus does not hold the answer. Preregistration 021 does not run it, and a track
# the approved run does not run is a null row, not a diagnostic.
REFERENCE_TRACKS = [
    ("recall_prefetch", "harness-side retrieval with the exact task prompt"),
    ("protocol", "the shared memory instruction, with no memory behind it"),
]

# Arms whose numbers are withheld from the board while their vendor's review window is open.
#
# This is a PUBLIC COMMITMENT, made in an issue on the vendor's own repository, so it needs a
# mechanism and not a note: the whole lesson of this project is that a recorded intention nobody
# checks reads exactly like an enforced one.
#
# 🔑 The hold is keyed on PRESENCE, not on a date comparison, and that is deliberate twice over.
# A date-computed hold would make `build()` time-dependent, so the committed `leaderboard.js`
# would drift from its regeneration the moment the date passed and
# `tests/test_leaderboard_generated.py` would fail for no reason connected to any change. And a
# hold that expires on its own expires silently: somebody must delete the entry, which is exactly
# the moment to confirm the window actually closed rather than merely elapsed.
#
# `until` and `issue` are published on the page so a reader can check the promise against the
# vendor's own thread rather than taking this repository's word for it.
VENDOR_REVIEW_HOLDS: dict[str, dict[str, str]] = {
    "mempalace": {
        "until": "2026-09-15",
        "issue": "https://github.com/MemPalace/mempalace/issues/2414",
        "reason": "held for vendor review",
    },
}

ARM_FIELDS = ("success", "delta", "ci", "discarded", "tokensPerTask", "costPerTask")
VENDOR_FIELDS = ("totalTokens",)
RUN_FIELDS = ("id", "date", "cli", "model", "tasks", "sessionsPerCell", "prereg")

HEADER = """\
/* GENERATED by scripts/build_leaderboard.py. Do not edit by hand:
   tests/test_leaderboard_generated.py fails CI when this file differs from its
   regeneration. The pointer lives in site/data/leaderboard.config.json; numbers enter
   only through results/<run_id>/leaderboard_summary.json. */
"""


class SummaryInvalid(ValueError):
    pass


def _load_summary(results_dir: Path, run_id: str) -> dict:
    path = results_dir / run_id / "leaderboard_summary.json"
    if not path.is_file():
        raise SummaryInvalid(f"official_run is {run_id!r} but {path} does not exist")
    summary = json.loads(path.read_text(encoding="utf-8"))

    missing_run = [k for k in RUN_FIELDS if k not in summary.get("run", {})]
    if missing_run:
        raise SummaryInvalid(f"summary run block is missing {missing_run}")

    expected = {name for name, *_ in PRODUCT_ARMS}
    got = set(summary.get("arms", {}))
    if got != expected:
        raise SummaryInvalid(
            f"summary arms must be exactly {sorted(expected)}; "
            f"missing {sorted(expected - got)}, unknown {sorted(got - expected)}"
        )
    vendor_names = {internal for internal, _, role, _ in PRODUCT_ARMS if role is None}
    for name, values in summary["arms"].items():
        absent = [k for k in ARM_FIELDS if k not in values]
        if absent:
            raise SummaryInvalid(f"arm {name!r} is missing fields {absent}")
        if name in vendor_names:
            absent_vendor = [k for k in VENDOR_FIELDS if k not in values]
            if absent_vendor:
                raise SummaryInvalid(f"vendor arm {name!r} is missing fields {absent_vendor}")
    if summary["arms"]["claude_md"]["delta"] != 0:
        raise SummaryInvalid("claude_md is the baseline; its delta must be exactly 0")

    expected_ref = {name for name, _ in REFERENCE_TRACKS}
    got_ref = set(summary.get("reference", {}))
    if got_ref != expected_ref:
        raise SummaryInvalid(
            f"summary reference tracks must be exactly {sorted(expected_ref)}, got {sorted(got_ref)}"
        )
    return summary


def _active_product_arms(config: dict | None = None) -> list[tuple[str, str, str, str | None]]:
    """Return the base roster plus explicitly accepted additive arm definitions."""

    config = config or {}
    arm_runs = config.get("arm_runs", {})
    if not isinstance(arm_runs, dict):
        raise SummaryInvalid("arm_runs must be an object mapping arm names to submission runs")

    base_names = {name for name, *_ in PRODUCT_ARMS}
    active = list(PRODUCT_ARMS)
    for internal in arm_runs:
        if internal in base_names:
            raise SummaryInvalid(
                f"arm_runs cannot replace base arm {internal!r}; publish a new base run instead"
            )
        definition = ADDITIVE_ARM_DEFINITIONS.get(internal)
        if definition is None:
            raise SummaryInvalid(
                f"arm_runs names unknown arm {internal!r}; add its reviewed definition first"
            )
        active.append((internal, *definition))
    return active


def public_arms(
    definitions: list[tuple[str, str, str, str | None]] | None = None,
) -> list[tuple[str, str, str, str | None]]:
    """``(internal, public, integration, role)`` per arm, in display order.

    An undisclosed arm becomes ``product_a``, ``product_b``, ... and loses its integration
    description. The internal name stays behind for the run summary lookup and never
    reaches the page; ``tests/test_site_vendor_disclosure.py`` reads this function to
    assert that, over the whole of ``site/``, rather than trusting the generator.
    """
    out: list[tuple[str, str, str, str | None]] = []
    anonymous = 0
    for internal, arm_type, role, public in definitions or PRODUCT_ARMS:
        if public is None:
            if anonymous >= 26:
                raise ValueError("more undisclosed arms than letters; widen the label scheme")
            label = UNDISCLOSED_PREFIX + chr(ord("a") + anonymous)
            anonymous += 1
            out.append((internal, label, UNDISCLOSED_TYPE, role))
        else:
            out.append((internal, public, arm_type, role))
    return out


def _load_arm_submission(
    results_dir: Path,
    run_id: str,
    arm: str,
    base_run_id: str,
    base_summary: dict,
) -> dict:
    """Load one independently measured arm and check that it joins the frozen base."""

    path = results_dir / run_id / "arm_summary.json"
    if not path.is_file():
        raise SummaryInvalid(f"arm_runs entry {run_id!r} has no {path}")
    submission = json.loads(path.read_text(encoding="utf-8"))

    missing = [
        key
        for key in ("schema", "generated_by", "run", "arm", "base_run", "result", "join")
        if key not in submission
    ]
    if missing:
        raise SummaryInvalid(f"arm submission {path} is missing {missing}")
    if submission["schema"] != 1:
        raise SummaryInvalid(f"arm submission {path} has unsupported schema {submission['schema']!r}")
    if submission["generated_by"] != "scripts/build_arm_submission.py":
        raise SummaryInvalid(f"arm submission {path} was not generated by the supported script")
    if submission["arm"] != arm:
        raise SummaryInvalid(
            f"arm submission {path} declares {submission['arm']!r}, expected {arm!r}"
        )
    if submission["base_run"] != base_run_id:
        raise SummaryInvalid(
            f"arm submission {path} joins {submission['base_run']!r}, expected {base_run_id!r}"
        )
    join = submission["join"]
    if join.get("baseRun") != base_run_id:
        raise SummaryInvalid(f"arm submission {path} join.baseRun does not match base_run")
    for key in ("baseAdmittedCells", "joinedCells", "baseCellsLostToJoin"):
        if not isinstance(join.get(key), int) or join[key] < 0:
            raise SummaryInvalid(f"arm submission {path} join.{key} must be a nonnegative integer")
    if join["joinedCells"] == 0:
        raise SummaryInvalid(f"arm submission {path} has no joined cells")

    run = submission["run"]
    missing_run = [key for key in RUN_FIELDS if key not in run]
    if missing_run:
        raise SummaryInvalid(f"arm submission {path} run block is missing {missing_run}")
    if run["id"] != run_id:
        raise SummaryInvalid(f"arm submission {path} run.id is not {run_id!r}")

    base_run = base_summary["run"]
    for key in ("model", "tasks", "sessionsPerCell"):
        if run[key] != base_run[key]:
            raise SummaryInvalid(
                f"arm submission {path} is incompatible with base run on {key}: "
                f"{run[key]!r} != {base_run[key]!r}"
            )

    result = submission["result"]
    missing_result = [key for key in (*ARM_FIELDS, *VENDOR_FIELDS) if key not in result]
    if missing_result:
        raise SummaryInvalid(f"arm submission {path} result is missing {missing_result}")
    return submission


def _scope(config: dict) -> dict:
    """What this page is a ranking OF, decided by the config and not by the person writing copy.

    Default is the honest one. Claiming the write path was measured requires naming the run that
    measured it, so the claim and its evidence move together or not at all.
    """

    measured = bool(config.get("write_path_measured", False))
    if not measured:
        return {
            "writePathMeasured": False,
            "title": RETRIEVAL_ONLY_TITLE,
            "qualification": RETRIEVAL_ONLY_QUALIFICATION,
            "longitudinalRun": None,
        }
    run_id = config.get("longitudinal_run")
    if not run_id:
        raise SummaryInvalid(
            "write_path_measured is true but no longitudinal_run is named; a ranking may only "
            "drop the retrieval-only title once the run that measured the write path exists"
        )
    return {
        "writePathMeasured": True,
        "title": FULL_TITLE,
        "qualification": f"Write path measured by {run_id}.",
        "longitudinalRun": str(run_id),
    }


def build(repo_root: str | Path) -> str:
    repo_root = Path(repo_root)
    config = json.loads(
        (repo_root / "site" / "data" / "leaderboard.config.json").read_text(encoding="utf-8")
    )
    run_id = config["official_run"]
    summary = _load_summary(repo_root / "results", run_id) if run_id else None

    definitions = _active_product_arms(config)
    arm_runs = config.get("arm_runs", {}) or {}
    if arm_runs and summary is None:
        raise SummaryInvalid("arm_runs requires an official_run base summary")
    arm_numbers = {
        internal: summary["arms"][internal] if summary else {}
        for internal, *_ in PRODUCT_ARMS
    }
    arm_sources = {internal: run_id for internal, *_ in PRODUCT_ARMS}
    for internal, configured_run in arm_runs.items():
        submission_run = (
            configured_run.get("run") if isinstance(configured_run, dict) else configured_run
        )
        if not isinstance(submission_run, str) or not submission_run:
            raise SummaryInvalid(f"arm_runs entry {internal!r} must name a result run")
        submission = _load_arm_submission(
            repo_root / "results", submission_run, internal, run_id, summary
        )
        arm_numbers[internal] = submission["result"]
        arm_sources[internal] = submission_run

    arms = []
    for internal, public, arm_type, role in public_arms(definitions):
        entry: dict = {"name": public, "type": arm_type}
        if role:
            entry["role"] = role
        numbers = arm_numbers.get(internal, {})
        for field in ARM_FIELDS:
            entry[field] = numbers.get(field)
        if role is None:
            for field in VENDOR_FIELDS:
                entry[field] = numbers.get(field)
        source_run = arm_sources.get(internal)
        if source_run:
            entry["sourceRun"] = source_run
        if source_run and source_run != run_id:
            entry["comparison"] = f"joined to {run_id}"
        if internal == "claude_md" and entry["delta"] is None:
            entry["delta"] = 0  # the page renders the baseline row from this sentinel
        # Per-condition detail is published for PRODUCTS only. The controls exist to price the
        # grid, not to be studied condition by condition, and putting five more columns on
        # `bare` and `placebo` would bury the comparison the table is for.
        if role is None:
            entry["byCondition"] = numbers.get("byCondition")
        hold = VENDOR_REVIEW_HOLDS.get(internal)
        if hold:
            # Blank the numbers AFTER they were read, not by skipping the read: the summary must
            # still contain this arm, so a held arm cannot be used to smuggle a missing one past
            # `_load_summary`'s every-arm-present check.
            for field in ARM_FIELDS:
                entry[field] = None
            if role is None:
                for field in VENDOR_FIELDS:
                    entry[field] = None
            # The hold covers the per-condition detail too. Publishing a product's condition
            # breakdown while withholding its headline would defeat the point of the hold.
            if "byCondition" in entry:
                entry["byCondition"] = None
            entry["held"] = hold["reason"]
            entry["heldUntil"] = hold["until"]
            entry["heldIssue"] = hold["issue"]
        arms.append(entry)

    reference = []
    for name, what in REFERENCE_TRACKS:
        numbers = summary["reference"][name] if summary else {}
        reference.append(
            {
                "name": name,
                "what": what,
                "success": numbers.get("success"),
                "delta": numbers.get("delta"),
            }
        )

    public_sources = {
        public: arm_sources[internal]
        for internal, public, _arm_type, _role in public_arms(definitions)
        if arm_sources.get(internal)
    }
    data = {
        "updated": config["updated"],
        "baseline": "claude_md",
        "scope": _scope(config),
        "run": summary["run"] if summary else None,
        "provenance": {
            "baseRun": run_id,
            # Internal names are deliberately excluded. The disclosure layer must cover
            # provenance too, not just the visible row.
            "armRuns": public_sources,
        },
        "arms": arms,
        "reference": reference,
    }
    return f"{HEADER}window.AMB_LEADERBOARD = {json.dumps(data, indent=2)};\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="compare instead of writing")
    parser.add_argument("--root", default=Path(__file__).resolve().parents[1], type=Path)
    args = parser.parse_args()

    out = args.root / "site" / "data" / "leaderboard.js"
    generated = build(args.root)

    if args.check:
        current = out.read_text(encoding="utf-8") if out.is_file() else ""
        if current != generated:
            print(
                f"{out} does not match its regeneration. Never edit it by hand; "
                "change leaderboard.config.json or the run summary and rerun "
                "scripts/build_leaderboard.py."
            )
            return 1
        print(f"{out} matches its regeneration")
        return 0

    out.write_text(generated, encoding="utf-8", newline="\n")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
