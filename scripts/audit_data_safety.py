"""Audit the default corpus declaration and reject obvious credential or real contact leaks."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EMAIL = re.compile(r"(?<!\\)\b[A-Z0-9._%+-]+@([A-Z0-9.-]+\.[A-Z]{2,})\b", re.IGNORECASE)
SECRET = re.compile(
    r"(?i)(?:-----BEGIN [A-Z ]+ PRIVATE KEY-----|\b(?:sk|rk|or)-[A-Za-z0-9_-]{12,}\b)"
)
SYNTHETIC_DOMAINS = ("example.invalid", "example.test", "example.com", "example.org")


def _readable(path: Path) -> str:
    """Inspect decoded transcript fields, so JSON escaping cannot create false addresses."""

    raw = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix != ".jsonl":
        return raw
    parts: list[str] = []
    for line in raw.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            parts.append(line)
            continue
        if isinstance(event, dict):
            for key in ("content", "tool_input", "tool_result"):
                value = event.get(key)
                if isinstance(value, str):
                    if key == "tool_input":
                        try:
                            value = json.dumps(json.loads(value), ensure_ascii=False)
                        except json.JSONDecodeError:
                            pass
                    parts.append(value)
    return "\n".join(parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO / "corpus")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    policy_path = root / "data-policy.json"
    try:
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"FAIL: unreadable {policy_path}: {error}")
        return 1
    required_false = (
        "contains_real_personal_data",
        "contains_real_customer_data",
        "contains_real_proprietary_data",
    )
    violations = [name for name in required_false if policy.get(name) is not False]
    manifest = root / "manifest.json"
    try:
        entries = json.loads(manifest.read_text(encoding="utf-8")).get("sessions", {})
    except (OSError, json.JSONDecodeError, AttributeError) as error:
        print(f"FAIL: unreadable {manifest}: {error}")
        return 1
    for relative in entries:
        path = root / relative
        if not path.is_file():
            violations.append(f"missing manifest member {relative}")
            continue
        text = _readable(path)
        for match in EMAIL.finditer(text):
            domain = match.group(1).lower().rstrip(".")
            if not any(domain == allowed or domain.endswith("." + allowed) for allowed in SYNTHETIC_DOMAINS):
                violations.append(f"non synthetic email domain in {relative}")
        if SECRET.search(text):
            violations.append(f"credential shaped value in {relative}")
    if violations:
        print(f"FAIL: {len(violations)} data safety violation(s)")
        for violation in violations:
            print(f"  {violation}")
        return 1
    print(f"clean: synthetic-only corpus declaration and {len(entries)} manifest members audited")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
