#!/usr/bin/env python3
"""Print report file names under reports/ in report order."""

import os
import re


def report_key(filename: str) -> int:
    """Extract the numeric part from report-<n>.txt for sorting."""
    m = re.match(r"report-(\d+)\.txt", filename)
    return int(m.group(1)) if m else -1


def main() -> None:
    reports_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
    files = [f for f in os.listdir(reports_dir) if os.path.isfile(os.path.join(reports_dir, f))]
    files.sort(key=report_key)
    for f in files:
        print(f)


if __name__ == "__main__":
    main()
