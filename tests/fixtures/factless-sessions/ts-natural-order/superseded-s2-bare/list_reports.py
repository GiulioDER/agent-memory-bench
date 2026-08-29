#!/usr/bin/env python3
"""Print the file names under reports/, one per line, in report order."""
import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(BASE_DIR, "reports")


def natural_key(name):
    """Sort key that orders embedded numbers numerically (report-2 before report-10)."""
    return [
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", name)
    ]


def main():
    names = [
        name
        for name in os.listdir(REPORTS_DIR)
        if os.path.isfile(os.path.join(REPORTS_DIR, name))
    ]
    for name in sorted(names, key=natural_key):
        print(name)


if __name__ == "__main__":
    main()
