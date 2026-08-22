"""The competent solution WITHOUT the fact: add the copy in the style the script already uses.

One added cp line, matching the surrounding unquoted expansions. It works on every path the
sandbox can produce, including the prompt's own out/rel verification. Production release
directories contain spaces, and on those the unquoted expansions word-split.
"""

from pathlib import Path

SCRIPT = """\
#!/usr/bin/env bash
set -euo pipefail

TARGET=$1

mkdir -p $TARGET/app
cp app/main.py $TARGET/app/
cp -r assets $TARGET/
echo "deployed app to $TARGET"
"""


def apply(workdir: Path) -> None:
    (workdir / "deploy.sh").write_text(SCRIPT, encoding="utf-8", newline="\n")
