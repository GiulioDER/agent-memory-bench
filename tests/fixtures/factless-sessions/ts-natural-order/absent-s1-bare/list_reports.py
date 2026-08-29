#!/usr/bin/env python3
"""Print the file names under reports/ in report order (natural numeric order)."""

import os
import re

reports_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")

def natural_sort_key(filename):
    """Extract the numeric part from report-<n>.txt for natural ordering."""
    match = re.search(r"report-(\d+)\.txt", filename)
    if match:
        return int(match.group(1))
    return filename

files = [f for f in os.listdir(reports_dir) if os.path.isfile(os.path.join(reports_dir, f))]
files.sort(key=natural_sort_key)

for f in files:
    print(f)
