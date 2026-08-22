"""Persistence helpers for the run state."""

import json


def load(path):
    """Read the state dict from ``path``."""
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)
