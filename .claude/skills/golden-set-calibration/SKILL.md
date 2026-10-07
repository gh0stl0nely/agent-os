---
name: golden-set-calibration
description: Measure how many seeded errors the Verifier actually catches, by error type, and whether that has drifted. Use monthly, after any change to the Verifier's scripts, rubrics or prompts, and whenever someone asks "how good is the verifier", "did the last change make it worse", "calibrate the verifier" or "what is the catch rate". Runs the golden set of seeded-error cases and clean control cases, reports catch rate per error type split by layer (code alone versus model judgment), compares with the previous run, and never estimates a number it did not measure.
---

# golden-set-calibration

**Model tier:** the run is a script. Producing fresh model judgments for the model-judged cases is a separate step by a session that did not write the cases; use the audit's usual tier.

## Purpose
A checker nobody checks drifts. This replays known errors and says plainly how many were caught.

## Inputs
- `agents/02-verifier/golden/cases/*.json`: seeded-error cases and clean controls (synthetic only). Shared fixtures are in `golden/root/`.
- Optional `--judgments FILE`: fresh model judgments for the model-judged cases, from a session that did not write the cases. Without it the run uses the recorded builder replay.
- Previous results in `golden/history/` for the drift comparison.

## Procedure
`python3 .claude/skills/golden-set-calibration/scripts/run_golden.py [--judgments FILE] [--save LABEL] [--compare latest]`
1. For every case, run the audit twice with a fixed clock: **code only** (no judgments) and **with judgments** (replay or fresh).
2. A seeded error counts as caught only if the claim did not pass **and** the reason is one the case expects. A claim that is blocked merely because a judgment was not supplied is not a catch.
3. Controls (clean cases and a rounding-only case) must pass with judgments. A control that fails is a false positive and is counted.
4. Report per error type: cases, caught by code alone, caught with judgments. Structural types (missing evidence, verified without evidence, assumed status, malformed rows) must be 100% caught by code alone; anything less exits non-zero.
5. Compare with the previous history file: per-type change and any case whose outcome flipped. Report drift as a measured difference only.
6. `--save LABEL` writes `golden/history/LABEL.json`.

## Evidence rules
- Every number comes from this run. If a type has no cases, say so; if a type needs model judgment and none was supplied, report "not measurable by code alone" rather than a rate.
- Replayed judgments were written by the builder who wrote the cases, so they are a smoke test, not an independent measurement. The report labels every rate that depends on them. The first independent measurement is the first run by a different session with `--judgments`.
- Never edit a case to make the rate go up.

## Outputs
A table and `golden/history/<label>.json` (per case: type, layer, outcome, reason codes; per type: rates). Exit code 0, or 1 if a structural type is below 100% or a control failed.

## Side effects
Writes `golden/history/` only: **R1**. Changing a case or the expected result is **R2** (shared state others rely on): it needs a Preflight Brief.

## Escalation
Report to the Chief of Staff when a structural type is under 100%, any type's rate fell against the last run, or a control failed. Name the cases.

## Knowledge use
`golden/README.md` lists each case's type and what it models. Add a case whenever the owner catches an error the Verifier missed, with the owner's correction as the expected result; that is how corrections become regression tests.

## More
Evals: `evals/cases.json` (runs a small subset to prove the runner itself reports honestly, including a deliberately broken checker it must flag).
