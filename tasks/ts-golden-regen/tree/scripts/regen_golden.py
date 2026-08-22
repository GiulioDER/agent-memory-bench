"""Regenerate tests/golden/*.out from tests/cases/*.txt."""

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from formatter import format_text


def main() -> None:
    (ROOT / "tests" / "golden").mkdir(parents=True, exist_ok=True)
    for case in sorted((ROOT / "tests" / "cases").glob("*.txt")):
        body = format_text(case.read_text(encoding="utf-8"))
        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()[:8]
        out = ROOT / "tests" / "golden" / (case.stem + ".out")
        out.write_text(body + "\n# golden:" + digest + "\n", encoding="utf-8", newline="\n")
        print(f"wrote {out.name}")


if __name__ == "__main__":
    main()
