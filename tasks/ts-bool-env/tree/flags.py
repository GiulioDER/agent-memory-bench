"""Feature flag lookup."""

import configparser


def _config():
    parser = configparser.ConfigParser()
    parser.read("config.ini", encoding="utf-8")
    return parser
