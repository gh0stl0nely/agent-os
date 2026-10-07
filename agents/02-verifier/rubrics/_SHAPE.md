# Rubric shape

A domain rubric is how a domain role (Controller, CFO, Tax...) tells the Verifier what "supported" means in its
field. The Verifier ships the shape and two rubrics (`generic.md`, `example-invoice.md`). It does not write
accounting or tax rubrics: those roles supply them. Check any rubric with:

    python3 .claude/skills/claim-evidence-audit/scripts/rubric_lint.py agents/02-verifier/rubrics/<domain>.md

## Fixed shape (sections appear in this order)

```
# Rubric: <name>

## Config
```json
{
  "domain": "<short id; finance, tax, cash and customer-facing always get the stronger model>",
  "stakes": "routine" | "high",
  "stakes_threshold": null,          // a number: any claim with |value| at or above it gets the stronger model
  "max_age_days": 90,                // oldest acceptable source, or null for no age limit
  "tolerance": {
    "default": {},                   // exact unless the rubric says otherwise
    "by_unit": {"CAD": {"rounding_decimals": 2}}
  },
  "allowed_units": ["CAD", "count"]  // optional; any other unit on a number claim is a blocking weakness
}
```

## Scope
One paragraph: which claims this rubric covers and which it does not.

## Checks
- R-<ID> [blocking|major|minor]: <a yes/no question about one claim> 
  (at least three, ids unique; blocking means a claim cannot pass while the answer is no)

## Conciseness
- R-CONCISE [minor]: <the conciseness item; every rubric carries it>

## Known pitfalls
Bullets: mistakes this domain makes often. The reviewer reads these before judging.
```

## Tolerance
Tolerance lives here and nowhere else. A producer cannot widen it. Keys: `rounding_decimals` (the claim is the
true value shown to that many places), `abs` (largest allowed absolute difference), `rel` (largest allowed
fraction of the recomputed value). With none of them the number must match exactly.

## Why conciseness is a scored item
LLM judges tend to prefer longer answers (see `knowledge/verification/K-verification-0001.json`). Scoring
conciseness explicitly stops length from being mistaken for support.
