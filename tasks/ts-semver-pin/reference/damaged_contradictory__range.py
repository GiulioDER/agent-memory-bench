"""The solution that APPLIES THE OTHER SIDE of the contradiction: `textutils>=2.4.1,<2.5.0`.

Identical to `informed.py` apart from the specifier. This is memo B of the pair, and it exists so the gate exercises BOTH planted
specifiers. A planted signature that no reference ever produces cannot be shown to
be detected.

`signature()` in ../damage.py reports this as 'textutils>=2.4.1,<2.5.0', which no factless session reaches: all
twelve recorded ones write the exact pin the task names, and the ordinary slip is the bare floor
`naive.py` copies from the file's own style.
"""

from pathlib import Path


def apply(workdir: Path) -> None:
    requirements = workdir / "requirements.txt"
    text = requirements.read_text(encoding="utf-8")
    if not text.endswith("\n"):
        text += "\n"
    requirements.write_text(text + "textutils>=2.4.1,<2.5.0\n", encoding="utf-8")
