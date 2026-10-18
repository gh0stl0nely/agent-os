# Rubric: example-invoice

## Config
```json
{
  "domain": "invoice-example",
  "stakes": "routine",
  "stakes_threshold": null,
  "max_age_days": 400,
  "tolerance": {"default": {}, "by_unit": {"CAD": {"rounding_decimals": 2}}},
  "allowed_units": ["CAD", "count", "%"]
}
```

## Scope
A synthetic example of a domain rubric, for invoices and supplier statements. It shows the shape; it is not
accounting guidance and carries no real rates or vendors. The Controller writes the real one.

## Checks
- R-TOTAL [blocking]: Does the stated invoice total equal the sum of its lines, recomputed in code?
- R-LINES [blocking]: Is every line amount present in the source document at the cited location?
- R-DUPE [blocking]: Is this invoice a duplicate of another invoice in the same run (same vendor, number and amount)?
- R-PERIOD [major]: Does the invoice date fall in the period the claim is about?
- R-SIGN [major]: Are credit notes and refunds entered as negative amounts?
- R-ROUND [minor]: Is rounding applied once, to the total, in the way the source document does it?

## Conciseness
- R-CONCISE [minor]: Is the claim stated in the fewest words that keep its meaning? A longer or more confident claim is not a stronger one.

## Known pitfalls
- Rounding each line and then summing can differ from rounding the sum by a cent; check which one the source uses.
- The same invoice can arrive twice, once as a PDF and once as a statement line.
- Amounts in another currency are not comparable until converted, and the conversion needs its own dated source.
