"""The competent solution WITHOUT the fact: read max_retries from config.ini with a default.

Exactly what the existing code does for every other setting, and the fixture contains no
other configuration source to imitate. The project's decided precedence (environment over
config.local.ini over config.ini) lives only in the precursor session.
"""

from pathlib import Path

SCRIPT = '''\
"""Load runtime settings."""

import configparser


def load_settings() -> dict:
    parser = configparser.ConfigParser()
    parser.read("config.ini", encoding="utf-8")
    section = parser["app"]
    return {
        "timeout": section.getint("timeout"),
        "log_level": section.get("log_level"),
        "max_retries": section.getint("max_retries", fallback=3),
    }
'''


def apply(workdir: Path) -> None:
    (workdir / "settings.py").write_text(SCRIPT, encoding="utf-8")
