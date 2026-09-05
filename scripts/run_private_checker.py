"""Run one trusted private checker and print one JSON result for the evaluator."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checker", required=True, type=Path)
    parser.add_argument("--workdir", required=True, type=Path)
    parser.add_argument("--oracle", required=True, type=Path)
    args = parser.parse_args()

    spec = importlib.util.spec_from_file_location("amb_private_checker", args.checker)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load private checker: {args.checker}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    check = getattr(module, "check", None)
    if not callable(check):
        raise TypeError(f"private checker has no callable check(): {args.checker}")

    try:
        result = check(args.workdir, args.oracle)
    except Exception as error:  # noqa: BLE001 - a checker exception is a failed task outcome
        print(
            json.dumps(
                {
                    "task_id": args.checker.parent.name,
                    "ok": False,
                    "verdict": f"checker raised: {type(error).__name__}: {error}",
                }
            )
        )
        return 0
    if not isinstance(result, (tuple, list)) or len(result) != 2:
        raise RuntimeError("private checker must return (bool, str)")
    ok, verdict = result
    if not isinstance(ok, bool):
        raise TypeError("private checker first result must be bool")
    print(
        json.dumps(
            {
                "task_id": args.checker.parent.name,
                "ok": ok,
                "verdict": str(verdict),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
