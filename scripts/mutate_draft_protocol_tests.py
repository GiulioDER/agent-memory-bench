"""Break each draft-protocol guard on purpose and watch the named test go red.

A guard nobody has watched fail has not been tested. Three properties this harness has, each
because one of them has failed somewhere in this project:

* **The baseline is asserted BEFORE anything is mutated.** An interrupted run can leave a mutant in
  the tree, and the next run then reads that mutant as its baseline and reports "restored: True",
  which is true and worthless.
* **"mutation did not apply" is a third outcome and is never a pass.** If an anchor has moved, the
  mutation silently becomes a no-op and the test passes for the wrong reason.
* **Restore happens in a `finally`, in-process.** A shell copy dies with the shell.

Run: python -m scripts.mutate_draft_protocol_tests
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

MUTANTS = [
    (
        "the committed draft is hand-edited",
        REPO / "adapters" / "_shared" / "memory_protocol_draft.md",
        "Short is fine and short is normal",
        "Short is fine and short is normal, and somebody edited this by hand",
        "test_the_committed_draft_is_what_the_generator_produces",
    ),
    (
        "an unknown variant falls back to the standard protocol",
        REPO / "harness" / "instructions.py",
        "        raise InstructionError(\n"
        "            f\"unknown protocol variant {variant!r}; known: {sorted(PROTOCOL_VARIANTS)}\"\n"
        "        ) from None",
        "        return PROTOCOL_PATH",
        "test_an_unknown_variant_never_falls_back_to_the_standard_protocol",
    ),
    (
        "only recall gets the draft protocol, mempalace keeps the standard one",
        REPO / "scripts" / "pilot.py",
        "        texts[\"mempalace\"] = MemPalaceAdapter.shared_instruction(\n"
        "            neutral=neutral, variant=variant if shared else \"protocol\"\n"
        "        )",
        "        texts[\"mempalace\"] = MemPalaceAdapter.shared_instruction(neutral=neutral)",
        "test_every_memory_arm_gets_the_draft_protocol_not_just_recall",
    ),
    (
        "the fairness assertion ignores the variant it was given",
        REPO / "harness" / "instructions.py",
        "    template = protocol_template(neutral=neutral, variant=variant)",
        "    template = protocol_template(neutral=neutral, variant=\"protocol\")",
        "test_the_fairness_assertion_uses_the_variant_it_was_composed_with",
    ),
    (
        "the draft section loses the phrase that is its whole point",
        REPO / "scripts" / "build_draft_protocol.py",
        "**the text you are about to write**",
        "**the operations you are about to perform**",
        "test_the_draft_actually_says_to_search_with_the_draft",
    ),
]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", newline="")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="")


def run_test(name: str) -> tuple[bool, str]:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_draft_protocol.py", "-k", name, "-q"],
        cwd=REPO, capture_output=True, text=True, timeout=300, check=False,
    )
    return result.returncode == 0, (result.stdout + result.stderr).strip().splitlines()[-1]


def main() -> int:
    # 1. Baseline. Every anchor must be present BEFORE anything is touched, and the suite green.
    for label, path, anchor, _, _ in MUTANTS:
        if anchor not in read(path):
            print(f"  BASELINE BROKEN: anchor for {label!r} is absent from {path.name}.")
            print("  Either a mutant survived an earlier run, or the code moved. Refusing to start.")
            return 2
    green, line = run_test("")
    if not green:
        print(f"  BASELINE BROKEN: the suite is already red -> {line}")
        return 2
    print(f"  baseline OK: all anchors present, suite green ({line})")
    print()

    failures = 0
    for label, path, anchor, replacement, test in MUTANTS:
        original = read(path)
        mutated = original.replace(anchor, replacement, 1)
        if mutated == original:
            print(f"  NOT APPLIED  {label}  <- never a pass; the anchor did not match")
            failures += 1
            continue
        try:
            write(path, mutated)
            # If the mutated file is the generated draft, do NOT regenerate it: the point is that
            # the committed bytes drifted from the generator.
            green, line = run_test(test)
        finally:
            write(path, original)
        if green:
            print(f"  SURVIVED     {label}")
            print(f"               {test} stayed green; that guard does not guard.")
            failures += 1
        else:
            print(f"  killed       {label}")

    print()
    for label, path, anchor, _, _ in MUTANTS:
        if anchor not in read(path):
            print(f"  RESTORE FAILED for {label!r} in {path.name}")
            failures += 1
    green, line = run_test("")
    print(f"  restored and green: {line}")
    if failures:
        print(f"\n  {failures} mutant(s) survived or did not apply.")
        return 1
    print(f"\n  all {len(MUTANTS)} mutants killed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
