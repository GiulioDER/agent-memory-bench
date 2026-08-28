import json
import csv

def main():
    with open("records.json", "r", encoding="utf-8") as f:
        records = json.load(f)

    with open("report.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "customer", "note", "amount"])
        for record in records:
            writer.writerow([record["id"], record["customer"], record["note"], record["amount"]])

if __name__ == "__main__":
    main()
