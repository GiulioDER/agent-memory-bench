"""Report host-environment identifiers in the tracked tree, before anything is republished.

The corpus is verbatim agent output on purpose (`corpus/README.md`, rule 1), so the recording
machine's paths and usernames are IN the evidence and cannot be redacted afterwards without
breaking the rule that makes the corpus worth anything. That trade is already made and this
script does not argue with it.

What it exists for is the second publication. Everything here is already public on GitHub, where
it is read by people who came looking. A Hugging Face dataset is indexed, mirrored, and pulled
into training corpora by parties who did not, so the same bytes travel much further, and the
decision to let them travel should be taken with the count in front of you rather than inferred
from "it was already public".

Read-only. It changes nothing and redacts nothing; the output is an input to a decision.

    python scripts/scan_host_identifiers.py
    python scripts/scan_host_identifiers.py --paths corpus --verbose
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Each pattern captures the IDENTIFIER, not the whole match, so the report says which user and
# which host rather than only how many times some path shape occurred.
PATTERNS = {
    "windows_user_path": re.compile(r"C:\\{1,4}Users\\{1,4}([A-Za-z0-9_.-]+)"),
    "posix_home": re.compile(r"/home/([a-z][a-z0-9_-]*)"),
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
}

# Addresses under RFC 2606 / RFC 6761 reserved names cannot resolve and cannot reach anybody, so
# a fixture that uses one is not a disclosure. Anything else is reported.
FIXTURE_EMAIL_SUFFIXES = (".example.invalid", ".example.com", ".invalid", ".example")

# Compressed streams decode to noise under a text read, and that noise matches the email pattern
# often enough to bury the real hits. `results/diagnostic-010/streams/` alone produced 18 such
# matches before this skip existed, every one of them random bytes.
BINARY_SUFFIXES = (".gz", ".zip", ".png", ".jpg", ".jpeg", ".gif", ".pdf", ".onnx", ".bin")

DEFAULT_PATHS = ("corpus", "tasks", "results", "docs", "reports", "site", "huggingface")


def tracked_files(paths: tuple[str, ...]) -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", *paths],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [line for line in out.splitlines() if line.strip()]


def _is_fixture_email(address: str) -> bool:
    lowered = address.lower()
    return any(lowered.endswith(suffix) for suffix in FIXTURE_EMAIL_SUFFIXES)


def scan(
    paths: tuple[str, ...], literals: tuple[str, ...] = ()
) -> tuple[dict[str, Counter], dict[str, set[str]], int]:
    """Structural patterns, plus any bare identifier the caller names.

    The literals are a parameter rather than a constant because a username baked into a public
    repository is the thing this script is for finding, and a scanner that carries one is a
    smaller version of the same mistake. Pass ``--literal`` for the account you are checking.
    """
    keys = list(PATTERNS) + [f"literal:{value}" for value in literals]
    hits: dict[str, Counter] = {name: Counter() for name in keys}
    files_hit: dict[str, set[str]] = {name: set() for name in keys}
    files = [
        rel for rel in tracked_files(paths) if not rel.lower().endswith(BINARY_SUFFIXES)
    ]

    for rel in files:
        try:
            text = (REPO_ROOT / rel).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for name, pattern in PATTERNS.items():
            found = pattern.findall(text)
            if name == "email":
                found = [f for f in found if not _is_fixture_email(f)]
            if not found:
                continue
            files_hit[name].add(rel)
            hits[name].update(found)
        for value in literals:
            count = text.lower().count(value.lower())
            if count:
                files_hit[f"literal:{value}"].add(rel)
                hits[f"literal:{value}"][value] += count

    return hits, files_hit, len(files)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paths", nargs="*", default=list(DEFAULT_PATHS))
    parser.add_argument(
        "--literal",
        action="append",
        default=[],
        metavar="TEXT",
        help="also count this bare string, case-insensitively; repeatable",
    )
    parser.add_argument("--verbose", action="store_true", help="list every affected file")
    args = parser.parse_args()

    hits, files_hit, scanned = scan(tuple(args.paths), tuple(args.literal))

    print(f"scanned {scanned} tracked text files under {', '.join(args.paths)}\n")
    total = 0
    for name in hits:
        count = sum(hits[name].values())
        total += count
        print(f"{name}: {len(files_hit[name])} files, {count} occurrences")
        for value, n in hits[name].most_common(10):
            print(f"    {value}: {n}")
        listing = sorted(files_hit[name])
        for rel in listing if args.verbose else listing[:5]:
            print(f"    file: {rel}")
        if not args.verbose and len(listing) > 5:
            print(f"    ... and {len(listing) - 5} more")
        print()

    print(f"total identifier occurrences: {total}")
    print(
        "\nThis is a report, not a gate. It exits 0 whatever it finds, because whether these\n"
        "may be republished is a decision for the run holder and not a property of the tree."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
