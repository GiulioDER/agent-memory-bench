#!/usr/bin/env python3
import csv
import json

with open("records.json") as f:
    records = json.load(f)

with open("report.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["id", "customer", "note", "amount"])
    for r in records:
        writer.writerow([r["id"], r["customer"], r["note"], r["amount"]])
