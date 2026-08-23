"""Ops helper: set one status field in state.json."""

import json
import sys

sys.path.insert(0, ".")
from store import load


def main(key, value):
    state = load("state.json")
    state[key] = value
    with open("state.json", "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
