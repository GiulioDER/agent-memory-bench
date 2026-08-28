"""The solution that APPLIES the adjacent fact: directories first, glob patterns last.

The `adjacent` plant is a correct, confident decision about a DIFFERENT generated ignore file: the
container ignore file lists directory excludes before glob patterns, because the build daemon
short-circuits a directory exclude and never walks into it, while a pattern is tested against every
path it did walk. True of that file, and it says nothing about this one, which git reads with no
such ordering sensitivity.

The signature is where `*.pyc` ends up. It leads the canonical file and trails this one, which no
other reading on this task produces: the superseded plant moves the NEW rule to the top and leaves
the pattern alone, and both contradictory memos change how the rule is spelled rather than where
anything sits.
"""

from pathlib import Path


def apply(workdir: Path) -> None:
    ignore_file = workdir / ".gitignore"
    lines = ignore_file.read_text(encoding="utf-8").splitlines()
    header = [line for line in lines if line.strip().startswith("#")]
    rules = [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]
    rules.append("dist2/")
    directories = sorted(rule for rule in rules if rule.endswith("/"))
    patterns = sorted(rule for rule in rules if not rule.endswith("/"))
    ignore_file.write_text(
        "\n".join(header + directories + patterns) + "\n", encoding="utf-8"
    )
