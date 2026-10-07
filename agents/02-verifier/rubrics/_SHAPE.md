# Rubric shape

A domain rubric is how a domain role (Controller, CFO, Tax...) tells the Verifier what "supported" means in its
field. The Verifier ships the shape and two rubrics: `generic.md` (use it as the template: copy it and edit) and
`example-invoice.md` (a synthetic domain example). It does not write accounting or tax rubrics; those roles
supply them. Check any rubric with:

    python3 .claude/skills/claim-evidence-audit/scripts/rubric_lint.py agents/02-verifier/rubrics/<domain>.md

## Sections, in this order

| Section | Content |
|---|---|
| `# Rubric: <name>` | title line |
| `## Config` | one fenced `json` block (keys below) |
| `## Scope` | one paragraph: which claims this covers and which it does not |
| `## Checks` | list items `- R-<ID> [blocking\|major\|minor]: <yes/no question about one claim>`; at least three, ids unique; `blocking` means a claim cannot pass while the answer is no |
| `## Conciseness` | exactly the item `- R-CONCISE [minor]: ...`; every rubric carries it |
| `## Known pitfalls` | bullets: mistakes this domain makes often; the reviewer reads these before judging |

## Config keys

| Key | Type | Meaning |
|---|---|---|
| `domain` | string | short id. `finance`, `tax`, `cash` and `customer-facing` always get the stronger model |
| `stakes` | `"routine"` or `"high"` | `high` gets the stronger model whatever the domain |
| `stakes_threshold` | number or `null` | any claim with an absolute value at or above it gets the stronger model; `null` until the owner sets one (open question 1) |
| `max_age_days` | integer or `null` | oldest acceptable source; `null` means no age limit |
| `tolerance` | object | `default` and `by_unit` (a unit code to a tolerance) |
| `allowed_units` | list or `null` | optional; any other unit on a number claim is a blocking weakness |

## Tolerance

Tolerance lives here and nowhere else. A producer cannot widen it. A tolerance object may have `rounding_decimals`
(the claim is the true value shown to that many places), `abs` (largest allowed absolute difference) and `rel`
(largest allowed fraction of the recomputed value). An empty object means the number must match exactly.

## Why conciseness is a scored item

LLM judges tend to prefer longer answers (see `knowledge/verification/K-verification-0001.json`). Scoring
conciseness explicitly stops length or confident wording from being mistaken for support.
