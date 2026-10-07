# claim-evidence-audit: reference

## Structure codes (reject unless marked warn)
| Code | Meaning |
|---|---|
| ENVELOPE_INVALID | envelope does not fit `agent-envelope.schema.json`; the audit is `blocked` |
| SCHEMA | row does not fit `claim-ledger.schema.json` (includes `verified` with no evidence or a non-pass verification, `blocked` with no reason, unknown kind or status) |
| ASSUMED_STATUS | status `assumed` does not exist; an unevidenced claim is `blocked` |
| MISSING_EVIDENCE | a pending claim with no evidence items |
| VERIFIED_WITHOUT_EVIDENCE | marked verified with no evidence |
| BAD_TIMESTAMP | not a strict RFC 3339 date-time with an offset. `contracts/validate.py` does not enforce this unless the optional `rfc3339-validator` package is installed |
| FUTURE_TIMESTAMP | more than 5 minutes ahead of the audit clock |
| DUPLICATE_ID | two rows share a `claim_id` |
| NUMBER_NO_VALUE, NUMBER_NO_UNIT | a number claim cannot be compared without both |
| CLAIM_ROW_MISSING | the envelope lists a claim id with no ledger row |
| SELF_VERIFIED (warn) | the producer marked its own claim verified; ignored |
| ROW_NOT_IN_ENVELOPE (warn) | a ledger row the envelope does not list; not audited |
| MISROUTED (warn) | envelope not addressed to `02-verifier` |

## Check reason codes
Pass: `supported`, `recomputed_exact`, `recomputed_rounding`, `recomputed_within_abs`, `recomputed_within_rel`, `verified`.
Fail: `material`, `unit_mismatch`, `input_changed`, `spec_script_mismatch`, `outdated`, `unsupported`, `off_topic`, `partial_support`, `quote_not_verbatim`, `number_not_in_quote`, `locator_unresolved`, `injection_in_source`, `kb_record_invalid`, plus any blocking weakness type.
Unverifiable (never a pass): `source_not_found`, `date_unknown`, `locator_format_unsupported`, `quote_not_verbatim_url`, `awaiting_judgment`, `judgment_malformed`, `no_spec`, `inputs_not_logged`, `script_error`, `script_timeout`, `script_not_allowed`, `bad_output`, `computation_not_comparable`.

## Known limits (stated so nobody over-trusts a pass)
- A pass for a number means a script the producer supplied, run on inputs the producer logged, gave that number. A script that prints the claimed value would pass. Inputs are hashed and the script must sit inside the root, but the script's logic is evidence, not proof; adversarial review and the owner's sampling are the backstop.
- Numbers written as words ("eight") do not match digits in the numeric check; such a claim fails conservatively.
- WebFetch returns a rewritten page, so a URL quote that is not found is `unverifiable`, not a failure.
- The model judgments are only as independent as the session that makes them. A judge from the producer's own model family can share its blind spots, which is why code checks run first.

## Worked example
Envelope lists `C-fx-total` (a number from a script) and `C-fx-cutoff` (a fact from a document).
1. `audit.py` without judgments: the recompute passes, the document's code checks pass, so it stops at `awaiting_judgment` and writes the packet.
2. The reviewer reads only the packet and writes `judgments.json`.
3. `audit.py` with judgments: both claims pass, the envelope is `ok`, both rows come back `verified`.
If the producer had claimed 310.00, step 1 would already return `needs_revision` with "claimed 310.0 but the script gives 300.00 (difference 10.00)" and no model tokens would have been spent.
