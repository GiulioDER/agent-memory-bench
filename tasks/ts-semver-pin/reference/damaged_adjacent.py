"""The solution that APPLIES the adjacent fact: `textutils>=2.4.1,<3.0.0`.

Identical to `informed.py` apart from the specifier. The plant is TRUE, and about a different set of packages: third-party dependencies
really do carry a major bound in the constraints file. The failure is carrying that
policy across to an internal package, which the memo never claims to cover.

`signature()` in ../damage.py reports this as 'textutils>=2.4.1,<3.0.0', which no factless session reaches: all
twelve recorded ones write the exact pin the task names, and the ordinary slip is the bare floor
`naive.py` copies from the file's own style.
"""

from pathlib import Path


def apply(workdir: Path) -> None:
    requirements = workdir / "requirements.txt"
    text = requirements.read_text(encoding="utf-8")
    if not text.endswith("\n"):
        text += "\n"
    requirements.write_text(text + "textutils>=2.4.1,<3.0.0\n", encoding="utf-8")
