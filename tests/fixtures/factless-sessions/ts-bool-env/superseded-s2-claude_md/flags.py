"""Feature flag lookup."""

import configparser


def _config():
    parser = configparser.ConfigParser()
    parser.read("config.ini", encoding="utf-8")
    return parser


def is_enabled(name):
    """Return True if the named flag is enabled in the [flags] section."""
    return _config().getboolean("flags", name)
