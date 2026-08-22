"""Compare formatter output against the goldens in tests/golden/."""

from pathlib import Path

from formatter import format_text

FOOTER = "\n# golden:"


def golden_body(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    head, sep, _tail = text.rpartition(FOOTER)
    return head if sep else text


def main() -> int:
    failed = 0
    for case in sorted(Path("tests/cases").glob("*.txt")):
        golden = Path("tests/golden") / (case.stem + ".out")
        got = format_text(case.read_text(encoding="utf-8"))
        if got != golden_body(golden):
            print(f"FAIL {case.name}")
            failed += 1
        else:
            print(f"ok   {case.name}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
