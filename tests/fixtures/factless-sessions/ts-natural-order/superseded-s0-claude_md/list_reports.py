import os
import re

reports_dir = "reports"

def report_sort_key(filename):
    match = re.search(r"report-(\d+)", filename)
    return int(match.group(1)) if match else 0

files = sorted(os.listdir(reports_dir), key=report_sort_key)
for f in files:
    print(f)