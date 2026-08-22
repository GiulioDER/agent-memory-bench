"""Drive load_settings through the override layers the sandbox never showed.

The governing fact: settings here come from three layers, environment variable
(APP_MAX_RETRIES) over config.local.ini over config.ini. The fixture shows only config.ini,
so the competent-without-the-fact solution reads only config.ini and passes the first two
scenarios; the local-file and environment scenarios are where the fact discriminates.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

from harness.checker_run import run_bounded

EXCLUDED = {".git", "__pycache__", ".oracle"}

#: (label, config file, local file or None, env value or None, expected max_retries)
SCENARIOS = (
    ("default when unset anywhere", "base_config.ini", None, None, 3),
    ("config.ini value", "main_config.ini", None, None, 5),
    ("config.local.ini overrides config.ini", "main_config.ini", "local_config.ini", None, 7),
    ("environment overrides both files", "main_config.ini", "local_config.ini", "9", 9),
)


def check(workdir: Path, oracle_dir: Path) -> tuple[bool, str]:
    if not (workdir / "settings.py").is_file():
        return False, "settings.py is gone"

    for label, config, local, env_value, expected in SCENARIOS:
        with tempfile.TemporaryDirectory() as temp:
            stage = Path(temp)
            shutil.copytree(
                workdir, stage, ignore=shutil.ignore_patterns(*EXCLUDED), dirs_exist_ok=True
            )
            (stage / "config.local.ini").unlink(missing_ok=True)
            shutil.copyfile(oracle_dir / config, stage / "config.ini")
            if local:
                shutil.copyfile(oracle_dir / local, stage / "config.local.ini")
            shutil.copyfile(oracle_dir / "driver.py", stage / "driver.py")
            env = {"APP_MAX_RETRIES": env_value} if env_value else None
            completed = run_bounded(
                [sys.executable, "driver.py"], cwd=stage, timeout_s=60.0, env=env
            )
            if completed.returncode != 0:
                return False, f"[{label}] driver exited: {completed.stderr[-400:]}"
            try:
                value = json.loads(completed.stdout.strip().splitlines()[-1])
            except (json.JSONDecodeError, IndexError):
                return False, f"[{label}] driver printed no value: {completed.stdout[-200:]}"
            if value != expected:
                return False, f"[{label}] effective max_retries is {value!r}, expected {expected}"
    return True, "max_retries honours every layer in precedence order"
