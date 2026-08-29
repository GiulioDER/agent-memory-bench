#!/usr/bin/env python3
import json
import csv

with open("records.json") as f:
    records = json.load(f)

with open("report.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["id", "customer", "note", "amount"])
    writer.writeheader()
    writer.writerows(records)
