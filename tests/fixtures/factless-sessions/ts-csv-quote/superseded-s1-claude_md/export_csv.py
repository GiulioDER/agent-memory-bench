import csv
import json

def main():
    with open("records.json", "r") as f:
        records = json.load(f)

    with open("report.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "customer", "note", "amount"])
        writer.writeheader()
        writer.writerows(records)

if __name__ == "__main__":
    main()