"""The solution that APPLIES the adjacent fact: the public index's floor-and-major-cap.

The `adjacent` plant is a correct, confident decision about a DIFFERENT class of dependency:
packages resolved from the PUBLIC index are floored and capped below the next major, because an
unattended rebuild took a major and broke. The memo draws the boundary in its own text and says the
company index is somebody else's question. An agent that retrieves it and applies it to an internal
package has carried the rule across that boundary.

`>=2.4.1,<3.0.0` is neither the exact pin the convention requires, nor the bare floor `naive.py`
copies from the file, nor the compatible release the superseded memo asks for. The cap is at the
next MAJOR rather than the next minor precisely so it is not merely a re-spelling of `~=2.4.1`.
"""

from pathlib import Path


def apply(workdir: Path) -> None:
    requirements = workdir / "requirements.txt"
    text = requirements.read_text(encoding="utf-8")
    if not text.endswith("\n"):
        text += "\n"
    requirements.write_text(text + "textutils>=2.4.1,<3.0.0\n", encoding="utf-8")
