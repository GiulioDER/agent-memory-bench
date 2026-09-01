"""Generate site/data/leaderboard.js from published results. Never from a keyboard.

The site promises that every number on the leaderboard traces to a published run
directory. This script is the only path a number takes to the page, and
``tests/test_leaderboard_generated.py`` fails CI whenever the committed file differs from
its regeneration, so a hand-edited number cannot survive review.

Inputs, both committed:

- ``site/data/leaderboard.config.json`` holds the pointer, never a number:
  ``{"official_run": null | "<run_id>", "updated": "YYYY-MM-DD"}``.
- When ``official_run`` is set, ``results/<run_id>/leaderboard_summary.json`` supplies the
  numbers. Its shape (fractions for rates, points as fractions, USD for cost)::

      {
        "run": {"id", "date", "cli", "model", "tasks", "sessionsPerCell", "prereg"},
        "arms": {"<arm>": {"success", "delta", "ci", "discarded",
                            "tokensPerTask", "costPerTask"}},
        "reference": {"oracle_memory": {"success", "delta"},
                      "recall_prefetch": {"success", "delta"}}
      }

  Every product arm must be present, exactly once, and ``claude_md``'s delta must be 0:
  a summary that drops an embarrassing arm, invents a new one, or moves the baseline is
  refused, not smoothed over.

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
UNDISCLOSED_PRODUCTS = ("mem0", "supermemory", "zep", "cognee")

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
    for name, values in summary["arms"].items():
        absent = [k for k in ARM_FIELDS if k not in values]
        if absent:
            raise SummaryInvalid(f"arm {name!r} is missing fields {absent}")
    if summary["arms"]["claude_md"]["delta"] != 0:
        raise SummaryInvalid("claude_md is the baseline; its delta must be exactly 0")

    expected_ref = {name for name, _ in REFERENCE_TRACKS}
    got_ref = set(summary.get("reference", {}))
    if got_ref != expected_ref:
        raise SummaryInvalid(
            f"summary reference tracks must be exactly {sorted(expected_ref)}, got {sorted(got_ref)}"
        )
    return summary


def public_arms() -> list[tuple[str, str, str, str | None]]:
    """``(internal, public, integration, role)`` per arm, in display order.

    An undisclosed arm becomes ``product_a``, ``product_b``, ... and loses its integration
    description. The internal name stays behind for the run summary lookup and never
    reaches the page; ``tests/test_site_vendor_disclosure.py`` reads this function to
    assert that, over the whole of ``site/``, rather than trusting the generator.
    """
    out: list[tuple[str, str, str, str | None]] = []
    anonymous = 0
    for internal, arm_type, role, public in PRODUCT_ARMS:
        if public is None:
            if anonymous >= 26:
                raise ValueError("more undisclosed arms than letters; widen the label scheme")
            label = UNDISCLOSED_PREFIX + chr(ord("a") + anonymous)
            anonymous += 1
            out.append((internal, label, UNDISCLOSED_TYPE, role))
        else:
            out.append((internal, public, arm_type, role))
    return out


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

    arms = []
    for internal, public, arm_type, role in public_arms():
        entry: dict = {"name": public, "type": arm_type}
        if role:
            entry["role"] = role
        numbers = summary["arms"][internal] if summary else {}
        for field in ARM_FIELDS:
            entry[field] = numbers.get(field)
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

    data = {
        "updated": config["updated"],
        "baseline": "claude_md",
        "scope": _scope(config),
        "run": summary["run"] if summary else None,
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
