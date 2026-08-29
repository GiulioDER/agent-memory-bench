#!/usr/bin/env python3
"""Read records.json and write report.csv."""

import csv
import json

with open("records.json", "r") as f:
    records = json.load(f)

with open("report.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["id", "customer", "note", "amount"])
    writer.writeheader()
    writer.writerows(records)
