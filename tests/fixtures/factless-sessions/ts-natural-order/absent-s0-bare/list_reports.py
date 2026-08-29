#!/usr/bin/env python3
import os
import re


def main():
    reports_dir = "reports"
    pattern = re.compile(r"report-(\d+)\.txt")

    files = []
    for fname in os.listdir(reports_dir):
        match = pattern.match(fname)
        if match:
            files.append((int(match.group(1)), fname))

    # sort by numeric index
    files.sort(key=lambda x: x[0])

    for _, fname in files:
        print(fname)


if __name__ == "__main__":
    main()
