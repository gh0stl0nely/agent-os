# Rubric: generic

## Config
```json
{
  "domain": "generic",
  "stakes": "routine",
  "stakes_threshold": null,
  "max_age_days": 90,
  "tolerance": {"default": {}, "by_unit": {}},
  "allowed_units": null
}
```

## Scope
Any claim from any producer when no domain rubric exists. It checks that evidence exists, was actually checked, is
current, and says what the claim says. It does not judge domain correctness; a domain rubric adds that.

## Checks
- R-EVIDENCE [blocking]: Does the claim cite at least one evidence item that was actually checked (re-run, opened, looked up), not just named?
- R-SUPPORT [blocking]: Does the cited passage say what the claim says, rather than discussing the same topic?
- R-CURRENT [blocking]: Is the evidence dated within the allowed age for the decision it feeds?
- R-UNITS [blocking]: Do the value, unit and period in the claim match the evidence?
- R-REUSE [blocking]: Is any figure counted twice, or picked from a range in the producer's favour?
- R-INFER [blocking]: Does a recommendation follow from the evidence cited, with no step the evidence does not contain?
- R-SCOPE [major]: Are entity, period and scope the same in the claim and the evidence?
- R-HEDGE [minor]: Is uncertainty stated in the confidence field rather than hidden in wording?

## Conciseness
- R-CONCISE [minor]: Is the claim stated in the fewest words that keep its meaning? A longer or more confident claim is not a stronger one.

## Known pitfalls
- A source on the same topic is not a source for the claim.
- A number that is right in the wrong unit or period is wrong.
- "Verified" written by the producer means nothing; only the Verifier sets it.
- A claim that sounds careful ("approximately", "should") may still be filed as a fact.
