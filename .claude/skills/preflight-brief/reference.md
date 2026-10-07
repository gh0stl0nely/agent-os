# preflight-brief reference

## Files
- `scripts/brief_common.py`: loads the template from the contract, loads and judges ledger rows, finds injection text.
- `scripts/build_brief.py`: plan + ledger -> brief + envelope, or `blocked`.
- `scripts/check_brief.py`: checks any brief; rejects hand-written "pass" the ledger does not support.
- `fixtures/ledger.jsonl`: five synthetic claims: two verified, one pending, one blocked, one with a failed verification.
- `fixtures/plans.json`: seven plans, R2 to R6.
- `evals/run_evals.py`: the cases below.

## What the checker rejects
Title not `# Preflight: ...`; a missing or empty header field; a brief id not shaped `PF-YYYYMMDD-n`; class below R2 or below the classifier's class; a deadline with no date; sections not exactly the template's, in order; placeholder text left in; Evidence rows that are not `pass`, or that the ledger does not confirm; a claim cited in the text but not in the table; Why with no claim id; alternatives without "do nothing"; "not reversible" with no reason; an R6 cost with no number; a safety box that is neither checked nor N/A with a reason; secret-like values; instruction-like text.

## Design choices
- The ledger is the only source of Verifier results, so a brief cannot say "verified" about something the Verifier has not seen.
- A class is never lowered here. If the declared class is lower than the computed one, the build stops and the plan owner must raise it or rewrite the description.
- Safety checks marked N/A need a stated reason, because "not applicable" is the usual hiding place for a skipped check.
- Blocked results quote injected text (as data) but never repeat a secret value.
- The brief id is the next free number for the day in the output folder. Two sessions writing to the same folder at once could collide; the Chief of Staff owns the shared folder and should serialize writes.

## Limits
- The classifier and injection patterns are heuristics. A reviewer should read the brief; the checker proves completeness, not that the plan is wise.
- "Target verified" and "dry run" are statements by the planner. The Verifier must confirm the claims behind them.
