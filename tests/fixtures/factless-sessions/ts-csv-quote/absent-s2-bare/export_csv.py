import csv
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(BASE_DIR, "records.json"), encoding="utf-8") as f:
    records = json.load(f)

with open(os.path.join(BASE_DIR, "report.csv"), "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["id", "customer", "note", "amount"])
    for record in records:
        writer.writerow([record["id"], record["customer"], record["note"], record["amount"]])
