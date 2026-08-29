#!/usr/bin/env python3
import os
import re

reports_dir = "reports"

def report_key(filename):
    match = re.search(r"(\d+)", filename)
    return int(match.group(1)) if match else filename

files = [f for f in os.listdir(reports_dir) if os.path.isfile(os.path.join(reports_dir, f))]
for f in sorted(files, key=report_key):
    print(f)
