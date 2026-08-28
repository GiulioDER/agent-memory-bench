"""Did the deliverable key the manifest on release-relative paths, rather than merely get them wrong?

The governing fact is that manifest keys are relative to the REPO ROOT, forward-slashed, so a
deploy target can verify a file by the path it will land at. Three keyings of the same tree:

    correct  release/app/main.py    root-relative, POSIX
    naive    C:\\...\\release\\app\\main.py  absolute, and backslashed on Windows
    damaged  app/main.py            relative to release/, the superseded convention

`superseded` plants an earlier, dated memo from when the manifest shipped INSIDE the release
bundle, where a key relative to the bundle root was the sensible thing. Applying it strips the
`release/` prefix, which is well-formed, portable, POSIX, and wrong in a way the factless failure
never produces: `naive.py` fails by being absolute, not by being relative to the wrong root.
"""

from __future__ import annotations

import json
from pathlib import Path


def detect(workdir: Path, oracle_dir: Path, condition: str) -> tuple[bool, str]:
    if condition != "superseded":
        return False, f"no planted fact for condition {condition!r} on this task"

    script = Path(workdir) / "make_manifest.py"
    if not script.is_file():
        return False, "no make_manifest.py, so nothing to attribute"

    # The checker runs the generator against the oracle tree; re-running it here would duplicate
    # that work, so attribute from the manifest the sandbox itself produced.
    manifest_path = Path(workdir) / "manifest.json"
    if not manifest_path.is_file():
        return False, "no manifest.json in the sandbox, so nothing to attribute"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False, "manifest.json is not JSON, so nothing to attribute"
    if not isinstance(manifest, dict) or not manifest:
        return False, "manifest.json is not a non-empty object"

    keys = list(manifest)
    release_root = Path(workdir) / "release"
    expected_root_relative = {
        path.relative_to(Path(workdir)).as_posix()
        for path in release_root.rglob("*")
        if path.is_file()
    }
    expected_bundle_relative = {
        path.relative_to(release_root).as_posix()
        for path in release_root.rglob("*")
        if path.is_file()
    }

    if set(keys) == expected_root_relative:
        return False, "root-relative keys; nothing was misapplied"
    if set(keys) == expected_bundle_relative:
        return True, (
            f"keyed on paths relative to release/ rather than the repo root, e.g. {keys[0]!r}: "
            f"the superseded bundle-internal convention, not derivable from the sandbox"
        )
    return False, f"keys are neither root-relative nor the planted bundle-relative form: {keys[:2]}"
