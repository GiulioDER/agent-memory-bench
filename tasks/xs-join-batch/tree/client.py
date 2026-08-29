"""Minimal partner client. `send` posts one batch and returns the partner's status code."""

from __future__ import annotations

import configparser
import json
from pathlib import Path


def _endpoint() -> str:
    config = configparser.ConfigParser()
    config.read(Path(__file__).with_name("partner.ini"), encoding="utf-8")
    return config["partner"]["endpoint"]


def send(batch: list[dict]) -> int:
    """Post one batch of records. The transport is stubbed for local work."""

    payload = json.dumps({"records": list(batch)}, ensure_ascii=False)
    _ = (_endpoint(), payload)
    return 200
