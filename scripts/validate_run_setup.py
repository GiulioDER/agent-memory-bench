"""Was this run SET UP so that its data means anything? Answered from its own environment.json.

    python -m scripts.validate_run_setup results/official-003-present
    python -m scripts.validate_run_setup --run official-003            # every condition
    python -m scripts.validate_run_setup --run official-003 --watch    # for a LIVE run

## Why this exists, which is a different question from verify_run.py

`verify_run.py` asks whether the published numbers follow from the published sessions. It is
thorough and it needs no credentials. It reads `records.final.jsonl`, `costs.json` and the
endpoints, and it reads `environment.json` exactly zero times.

Nothing asked the other question: **were the conditions of the run such that its numbers mean
anything at all?** Every expensive failure in this project's history is that question going
unasked, and in every case the evidence was already sitting in `environment.json`:

| What went wrong | Cost | What the artefact said at the time |
|---|---|---|
| corpora built without the haystack | 94 sessions discarded, corpora rebuilt | `sessions_offered: 207`, not ~4,900 |
| `official-002` gave one arm more coaching | 2,181 sessions, headline finding withdrawn | `instruction_excess_bytes`: recall 1,958 against mempalace 853 |

Neither was a missing measurement. Both were a **recorded value nobody compared to an
expectation**, which is the same failure this repository already documents for a green
`.mcp.json present` line standing in for a live corpus. Provenance without assertion reads as
provenance with assertion, because both look like a file full of correct numbers.

**The timing is the point.** `environment.json` is written at the START of each condition,
before a single session runs. So this check can refuse a doomed run at minute five rather than
after eleven hours, which is the whole reason it is worth writing.

## What it checks

Every check names an expectation the caller supplies, or a self-consistency property of the
recorded numbers. It never infers a threshold from the data it is checking.

* **corpus reached the arms.** Each ingest entry's `sessions_offered` against a floor.
* **the shared protocol is byte identical.** For every instruction-carrying arm,
  ``bytes - excess`` must be the SAME number. That is an independent arithmetic check on the
  recorded manifest, and it does not trust `instruction_arms_matched`.
* **`instruction_arms_matched` is true.** The harness's own assertion, reported separately so a
  disagreement between it and the arithmetic above is visible rather than blurred into one line.
* **no arm's appendix dwarfs the protocol.** Each arm's excess as a fraction of the shared base.
  A result-schema appendix cannot be byte identical across products, so equality is the wrong
  test; "a minor addendum rather than a second document" is the right one. Under the `skill`
  instruction recall's appendix was 56% of the protocol and mempalace's 25%; under `protocol`
  they are 21% and 25%. The default bound of 0.33 separates those cleanly.
* **the roster is what was asked for**, and **the instruction variant is what was asked for**.
* **the sandbox is not inside the repo**, which contaminates a task that greps its own tree.

## What it deliberately does NOT do

It does not read `records.jsonl`, so it cannot say whether the run produced good sessions, only
whether it was configured to be capable of producing them. It states which checks it could not
run rather than passing them silently: a skipped check and a passing check must never render the
same, which is the failure mode this whole script exists to answer.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

#: A corpus this small has never been intentional here. The rebuilt haystack is ~4,900 documents
#: per condition and the old feed was 196, so any floor between them catches the real failure.
DEFAULT_CORPUS_FLOOR = 4000

#: See the module docstring: 0.33 sits between the confounded run (0.56) and the fair one (0.25).
DEFAULT_MAX_APPENDIX_FRACTION = 0.33

_MARKS = {True: "PASS", False: "FAIL", None: "SKIP"}


@dataclass(frozen=True)
class Check:
    """One question, and whether the artefact answered it. `ok is None` means it could not run."""

    name: str
    ok: bool | None
    detail: str

    @property
    def mark(self) -> str:
        return _MARKS[self.ok]


def _instruction_arms(env: dict) -> dict[str, int]:
    """Arms carrying an instruction at all. An arm with an empty one is not an offender."""

    manifest = env.get("instruction_manifest") or {}
    return {arm: m.get("bytes", 0) for arm, m in manifest.items() if m.get("bytes")}


def check_corpus_reached(env: dict, floor: int) -> Check:
    ingest = env.get("ingest")
    if not ingest:
        return Check("corpus_reached", None, "no ingest entries recorded")
    offered = {e.get("arm", "?"): e.get("sessions_offered") for e in ingest}
    missing = sorted(arm for arm, n in offered.items() if n is None)
    if missing:
        return Check("corpus_reached", None, f"sessions_offered absent for {missing}")
    shown = ", ".join(f"{arm}={n}" for arm, n in sorted(offered.items()))
    low = {arm: n for arm, n in offered.items() if n < floor}
    if low:
        return Check("corpus_reached", False, f"below floor {floor}: {low}  (all: {shown})")
    return Check("corpus_reached", True, f"floor {floor}; {shown}")


def check_shared_protocol_identical(env: dict) -> Check:
    """`bytes - excess` must be one number. Arithmetic on the manifest, trusting no flag."""

    excess = env.get("instruction_excess_bytes") or {}
    arms = _instruction_arms(env)
    if not arms or not excess:
        return Check("shared_protocol_identical", None, "no instruction manifest recorded")
    bases = {arm: n - excess.get(arm, 0) for arm, n in arms.items()}
    distinct = sorted(set(bases.values()))
    if len(distinct) != 1:
        return Check(
            "shared_protocol_identical",
            False,
            f"arms do not share one protocol: {bases} (bases seen: {distinct})",
        )
    return Check(
        "shared_protocol_identical",
        True,
        f"{distinct[0]} bytes shared by {len(arms)} arm(s): {sorted(arms)}",
    )


def check_arms_matched_flag(env: dict) -> Check:
    flag = env.get("instruction_arms_matched")
    if flag is None:
        return Check("instruction_arms_matched", None, "flag not recorded")
    return Check("instruction_arms_matched", bool(flag), f"harness reported {flag}")


def check_appendix_proportion(env: dict, max_fraction: float) -> Check:
    excess = env.get("instruction_excess_bytes") or {}
    arms = _instruction_arms(env)
    if not arms or not excess:
        return Check("appendix_proportion", None, "no instruction manifest recorded")
    bases = {n - excess.get(arm, 0) for arm, n in arms.items()}
    if len(bases) != 1:
        return Check("appendix_proportion", None, "protocol base is not shared; cannot compare")
    base = bases.pop()
    if base <= 0:
        return Check("appendix_proportion", None, f"shared base is {base}")
    fracs = {arm: excess.get(arm, 0) / base for arm in arms}
    over = {arm: round(f, 3) for arm, f in fracs.items() if f > max_fraction}
    shown = ", ".join(f"{arm}={f:.2f}" for arm, f in sorted(fracs.items()))
    if over:
        return Check("appendix_proportion", False, f"over {max_fraction}: {over}  (all: {shown})")
    return Check("appendix_proportion", True, f"max {max_fraction}; {shown}")


def check_expected(env: dict, key: str, expected: object, label: str) -> Check:
    if expected is None:
        return Check(label, None, "no expectation supplied")
    actual = env.get(key)
    if actual is None:
        return Check(label, None, f"{key} not recorded")
    if isinstance(expected, list):
        got, want = sorted(actual), sorted(expected)
        return Check(label, got == want, f"expected {want}, got {got}")
    return Check(label, actual == expected, f"expected {expected!r}, got {actual!r}")


def check_sandbox_outside_repo(env: dict) -> Check:
    inside = env.get("sandbox_inside_repo")
    if inside is None:
        return Check("sandbox_outside_repo", None, "sandbox_inside_repo not recorded")
    return Check("sandbox_outside_repo", not inside, f"sandbox_inside_repo={inside}")


def validate(
    env: dict,
    *,
    corpus_floor: int = DEFAULT_CORPUS_FLOOR,
    max_appendix_fraction: float = DEFAULT_MAX_APPENDIX_FRACTION,
    expect_arms: list[str] | None = None,
    expect_instruction: str | None = None,
) -> list[Check]:
    return [
        check_corpus_reached(env, corpus_floor),
        check_shared_protocol_identical(env),
        check_arms_matched_flag(env),
        check_appendix_proportion(env, max_appendix_fraction),
        check_expected(env, "arms", expect_arms, "expected_arms"),
        check_expected(env, "memory_instruction", expect_instruction, "expected_instruction"),
        check_sandbox_outside_repo(env),
    ]


def _env_paths(run: str | None, paths: list[str]) -> list[Path]:
    if run:
        return sorted((REPO / "results").glob(f"{run}*/environment.json"))
    out = []
    for p in paths:
        path = Path(p)
        out.append(path / "environment.json" if path.is_dir() else path)
    return out


def _report(path: Path, checks: list[Check]) -> tuple[int, int]:
    print(f"\n{path.parent.name}")
    for c in checks:
        print(f"  {c.mark:4}  {c.name:28} {c.detail}")
    return (
        sum(1 for c in checks if c.ok is False),
        sum(1 for c in checks if c.ok is None),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate how a run was set up.")
    parser.add_argument("paths", nargs="*", help="run directories or environment.json paths")
    parser.add_argument("--run", help="run id prefix; validates every condition under results/")
    parser.add_argument("--corpus-floor", type=int, default=DEFAULT_CORPUS_FLOOR)
    parser.add_argument(
        "--max-appendix-fraction", type=float, default=DEFAULT_MAX_APPENDIX_FRACTION
    )
    parser.add_argument("--expect-arms", help="comma separated roster the run must have")
    parser.add_argument("--expect-instruction", help="the memory_instruction it must have")
    parser.add_argument(
        "--watch",
        action="store_true",
        help="poll until at least one environment.json exists, for a live run",
    )
    parser.add_argument("--watch-timeout", type=int, default=1800)
    args = parser.parse_args(argv)

    if not args.run and not args.paths:
        parser.error("give a run directory, or --run <id>")

    if args.watch:
        deadline = time.monotonic() + args.watch_timeout
        while not _env_paths(args.run, args.paths) and time.monotonic() < deadline:
            time.sleep(10)

    paths = _env_paths(args.run, args.paths)
    if not paths:
        print("no environment.json found; nothing validated", file=sys.stderr)
        return 2

    expect_arms = args.expect_arms.split(",") if args.expect_arms else None
    total_failed = total_skipped = 0
    for path in paths:
        try:
            env = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"\n{path.parent.name}\n  FAIL  unreadable                    {exc}")
            total_failed += 1
            continue
        failed, skipped = _report(
            path,
            validate(
                env,
                corpus_floor=args.corpus_floor,
                max_appendix_fraction=args.max_appendix_fraction,
                expect_arms=expect_arms,
                expect_instruction=args.expect_instruction,
            ),
        )
        total_failed += failed
        total_skipped += skipped

    print(f"\n{len(paths)} condition(s): {total_failed} failed, {total_skipped} not run")
    if total_skipped:
        print("A SKIP is not a pass. It means the artefact did not carry what the check needs.")
    return 1 if total_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
