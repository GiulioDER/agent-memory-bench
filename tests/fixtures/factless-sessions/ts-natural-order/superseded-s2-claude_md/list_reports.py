#!/usr/bin/env python3
"""List report files under reports/ in report order (sorted by numeric suffix)."""

import glob
import re
import os

base_dir = os.path.dirname(os.path.abspath(__file__))
pattern = os.path.join(base_dir, 'reports', 'report-*.txt')

files = glob.glob(pattern)

def report_number(path):
    basename = os.path.basename(path)
    match = re.search(r'report-(\d+)', basename)
    return int(match.group(1)) if match else 0

for f in sorted(files, key=report_number):
    print(os.path.basename(f))
