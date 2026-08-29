#!/usr/bin/env python3
import csv
import json

with open("records.json", "r") as f:
    records = json.load(f)

with open("report.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["id", "customer", "note", "amount"])
    for record in records:
        writer.writerow([record["id"], record["customer"], record["note"], record["amount"]])