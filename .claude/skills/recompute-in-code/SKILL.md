---
name: recompute-in-code
description: Re-run the script behind a number claim and compare the result with the claimed value. Use whenever a claim of kind "number" cites computation evidence, whenever someone asks "does this number actually add up", "recompute this", "re-run the calculation", or "is that total right", and whenever a figure is about to be reported without having been recomputed. The script is always re-run, never trusted; inputs are checked against their logged hashes; tolerance comes from the rubric, so a rounding difference passes and a material difference fails with the exact numeric gap.
---

# recompute-in-code

**Model tier:** none. This is a script; the model only reads its output. (Haiku is acceptable if a model must relay it.)

## Purpose
Prove or disprove a number by running the code that is supposed to produce it. Compute with code, reason with the model.

## Inputs
- The claim row (kind `number`, with `value` and `unit`) whose `evidence` includes a `computation` item naming a `script`.
- A recompute spec for the claim: `{claim_id, script, args, inputs: [{path, sha256}], timeout_s}`. Every input file, including every file-like argument, must be listed with its sha256. No spec, or no logged inputs: the result is `unverifiable` and says what to supply.
- A tolerance, taken from the rubric (`vlib.tolerance_for`), never from the producer. None given means exact.
- A root directory. The script and every input must resolve inside it.

## Procedure
`python3 .claude/skills/recompute-in-code/scripts/recompute.py --claim C --spec S --root R --tolerance-json '{"rounding_decimals":2}'`
1. Check the spec matches the claim and the script named in the evidence (script).
2. Check the script is a `.py` file inside the root; arguments are relative, with no `..` (script).
3. Hash each logged input and compare with the spec; a change since the producer ran it fails the claim `input_changed` (script).
4. Run `python3 -I script args` in the root with a scrubbed environment and a timeout (script).
5. Parse the JSON the script printed (`{"value": ..., "unit": ...}`); compare the unit, then the value (script).
6. Classify the difference: `exact`; `rounding` (the claim equals the true value rounded to `rounding_decimals` places, half-up or half-even); `within_abs`; `within_rel`; otherwise `material` and a fail. Report the difference as claimed minus recomputed.

## Evidence rules
- Never report a number that did not come from this run. Decimal arithmetic only; a float is read through its shortest text form so 2.665 stays 2.665.
- A rounding pass is labelled as rounding, not as exact. A unit mismatch fails even when the digits agree: a right number in the wrong unit is a wrong number.
- Anything that stops the run (crash, timeout, bad output, script outside the root) is `unverifiable`, not a pass and not a guess.

## Outputs
A result object: `reasoning` (first), `checks`, `result` (pass, fail, unverifiable), `reason_code`, `missing_evidence`, and `numeric` with claimed, recomputed, difference and classification. Exit code 0, 1, 2. The audit turns it into ledger fields.

## Side effects
Runs a producer's script: **R0/R1**. Not a sandbox: it refuses paths outside the root, scrubs the environment and sets a timeout, but the script itself is code the producer wrote; vetting it is the Guardian's job.

## Escalation
When the script cannot run or its inputs are not logged, return the exact item to supply. When a material difference remains after two revise loops, the audit escalates it with the numbers.

## Knowledge use
Tolerance conventions for a domain live in its rubric. Rounding facts are in `knowledge/verification/K-verification-0005.json`.

## More
`fixtures/` has a synthetic script, data and specs for: exact, rounding-only, material, wrong unit, tampered input, crash, script outside the root, unlogged inputs. Evals: `evals/cases.json`.
