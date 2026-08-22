"""Load runtime settings."""

import configparser


def load_settings() -> dict:
    parser = configparser.ConfigParser()
    parser.read("config.ini", encoding="utf-8")
    section = parser["app"]
    return {
        "timeout": section.getint("timeout"),
        "log_level": section.get("log_level"),
    }
