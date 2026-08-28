"""The solution that APPLIES ONE SIDE of the contradiction: the rule written as `/dist2/`.

Hand-edits the file the way `naive.py` does, but writes a different FORM of the rule and puts it
where the sorted file would have put `dist2/`. Every prior rule keeps its order, so the planted
outcomes differ from each other only in what was written, which is the axis the prompt leaves open:
it asks for dist2/ not to be tracked and does not say what to write.

This is memo A of the pair: every rule is anchored to the repository root. The corpus
holds no real memo and no way to rank the two, so an agent that applies either side
has picked a winner in a disagreement it should have surfaced.
`damaged_contradictory__bare.py` applies the other side.
"""

from pathlib import Path

RULE = "/dist2/"


def apply(workdir: Path) -> None:
    ignore_file = workdir / ".gitignore"
    lines = ignore_file.read_text(encoding="utf-8").splitlines()
    out = []
    for line in lines:
        if line.strip() == "logs/":
            out.append(RULE)
        out.append(line)
    if RULE not in out:
        out.append(RULE)
    ignore_file.write_text("\n".join(out) + "\n", encoding="utf-8")
