"""Read records.json and write report.csv with header and data rows."""

import csv
import json

def main():
    with open("records.json", "r") as f:
        records = json.load(f)

    fieldnames = ["id", "customer", "note", "amount"]

    with open("report.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow(record)

if __name__ == "__main__":
    main()
