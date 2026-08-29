#!/usr/bin/env python3
"""List report files in numerical order."""

import os
import re

def report_key(filename):
    match = re.search(r'(\d+)', filename)
    return int(match.group(1)) if match else filename

def main():
    reports_dir = os.path.join(os.path.dirname(__file__), 'reports')
    files = [f for f in os.listdir(reports_dir) if f.startswith('report-')]
    files.sort(key=report_key)
    for f in files:
        print(f)

if __name__ == '__main__':
    main()
