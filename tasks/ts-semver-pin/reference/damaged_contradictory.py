"""The solution that APPLIES ONE SIDE of the contradiction: `textutils==2.4.*`.

Identical to `informed.py` apart from the specifier. This is memo A of the pair. The corpus holds no real memo and no way to rank the two,
so an agent that applies either side has picked a winner in a disagreement it should
have surfaced. `damaged_contradictory__range.py` applies the other side.

`signature()` in ../damage.py reports this as 'textutils==2.4.*', which no factless session reaches: all
twelve recorded ones write the exact pin the task names, and the ordinary slip is the bare floor
`naive.py` copies from the file's own style.
"""

from pathlib import Path


def apply(workdir: Path) -> None:
    requirements = workdir / "requirements.txt"
    text = requirements.read_text(encoding="utf-8")
    if not text.endswith("\n"):
        text += "\n"
    requirements.write_text(text + "textutils==2.4.*\n", encoding="utf-8")
