"""The solution WITH the fact: APP_MAX_RETRIES over config.local.ini over config.ini."""

from pathlib import Path

SCRIPT = '''\
"""Load runtime settings.

Precedence: environment variables, then config.local.ini, then config.ini.
"""

import configparser
import os


def load_settings() -> dict:
    parser = configparser.ConfigParser()
    parser.read(["config.ini", "config.local.ini"], encoding="utf-8")
    section = parser["app"]
    settings = {
        "timeout": section.getint("timeout"),
        "log_level": section.get("log_level"),
        "max_retries": section.getint("max_retries", fallback=3),
    }
    env = os.environ.get("APP_MAX_RETRIES")
    if env is not None:
        settings["max_retries"] = int(env)
    return settings
'''


def apply(workdir: Path) -> None:
    (workdir / "settings.py").write_text(SCRIPT, encoding="utf-8")
