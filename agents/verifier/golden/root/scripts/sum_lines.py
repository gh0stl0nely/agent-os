"""Synthetic fixture script: sum the `amount` column of a CSV (columns item,amount,unit).
Prints {"value": "<sum>", "unit": "<unit of the first row>"}. Decimal arithmetic, no rounding."""
import csv
import json
import sys
from decimal import Decimal

with open(sys.argv[1], newline="", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))
print(json.dumps({"value": str(sum(Decimal(r["amount"]) for r in rows)), "unit": rows[0]["unit"]}))
