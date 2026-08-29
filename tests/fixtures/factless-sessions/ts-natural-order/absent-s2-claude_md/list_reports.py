#!/usr/bin/env python3
"""Print report filenames under reports/ in report order."""

import os
import re

reports_dir = "reports"

def report_sort_key(filename):
    match = re.search(r"(\d+)", filename)
    return int(match.group(1)) if match else 0

filenames = sorted(os.listdir(reports_dir), key=report_sort_key)
for f in filenames:
    print(f)
