import os
import re

reports_dir = os.path.join(os.path.dirname(__file__), 'reports')
files = os.listdir(reports_dir)

def report_number(filename):
    match = re.search(r'report-(\d+)\.txt$', filename)
    if match:
        return int(match.group(1))
    return float('inf')

files.sort(key=report_number)

for f in files:
    print(f)
