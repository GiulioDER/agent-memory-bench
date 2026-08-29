import os
import re

reports_dir = "reports"

# Natural sort: extract the numeric part from filenames like report-<n>.txt
def sort_key(filename):
    match = re.search(r"(\d+)", filename)
    return int(match.group(1)) if match else filename

files = sorted(os.listdir(reports_dir), key=sort_key)

for f in files:
    print(f)
