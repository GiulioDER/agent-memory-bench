"""Nightly billing run. Placeholder for the real job, which lives in the billing service."""

import json

with open("orders.json", encoding="utf-8") as handle:
    orders = json.load(handle)

total = sum(float(order["amount"]) for order in orders)
print(f"billed {len(orders)} orders, {total:.2f} total")
