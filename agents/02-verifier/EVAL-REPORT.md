# Eval report: 02 Verifier

Everything below was run in this build session on 2026-10-07 (Toronto time) against the code in this branch. Nothing is estimated. Where a result depends on model judgments the builder wrote, it is labelled **replay (non-independent)**.

## How to run

```
python3 agents/02-verifier/run_evals.py                       # all 70 eval cases, five skills
python3 agents/02-verifier/run_evals.py --skill source-check  # one skill
python3 .claude/skills/golden-set-calibration/scripts/run_golden.py --compare latest   # golden set, with drift
python3 agent-system/contracts/validate.py                    # the contracts' own self test
```

## 1. Eval cases (`.claude/skills/*/evals/cases.json`): 70 of 70 pass

| Skill | Cases | normal | missing-data | seeded-error | adversarial | Result |
|---|---|---|---|---|---|---|
| claim-evidence-audit | 17 | 5 | 4 | 6 | 2 | 17 pass |
| recompute-in-code | 13 | 4 | 3 | 5 | 1 | 13 pass |
| source-check | 20 | 4 | 6 | 8 | 2 | 20 pass |
| adversarial-review | 11 | 3 | 2 | 5 | 1 | 11 pass |
| golden-set-calibration | 9 | 3 | 2 | 3 | 1 | 9 pass |

The runner reports a gap if a skill lacks any of the four required kinds; none does. Every case states why it exists (`why` in the JSON).

These all test code paths. They do **not** test a live model: no real model judgment was produced in an independent session (see Limits).

## 2. Acceptance criteria, one by one

| # | Criterion | Evidence (case ids are in the named skill's `evals/cases.json`) | Result |
|---|---|---|---|
| 1 | Rejects 100% of structurally invalid rows, including `verified` without evidence and any `assumed` status | `claim-evidence-audit/contract-rejects-every-invalid-row`: 20 invalid rows (`fixtures/invalid_rows.jsonl`, rule per row in `invalid_rows.notes.json`), each run through `validate.py` on its own; all 20 rejected. `verifier-only-rules-reject`: bad timestamp, future timestamp, number without unit, duplicate id, missing row: 5 of 5 rejected. Golden structural types: 12 of 12 caught by code alone. | Met |
| 2 | Recompute flags differences beyond tolerance, with one rounding pass and one material fail | `recompute-in-code/rounding-only-passes` (pass, `recomputed_rounding`), `tie-half-even-passes`, `material-difference-fails` (310 vs 300, difference 10.00), `rounding-with-empty-tolerance-fails` (the same rounded figure fails when the rubric allows no rounding) | Met |
| 3 | Source-check classifies supported, unsupported, off-topic and outdated sources and states what it checked | `source-check`: 20 cases, including `supported-passes`, `unsupported-fails`, `off-topic-fails`, `outdated-source-fails`; each result carries `checks` with an outcome per check | Met |
| 4 | The audit works from claims, evidence and rubric alone; a test shows producer reasoning withheld | `claim-evidence-audit/producer-reasoning-withheld`: a goal text and a self-verification note saying "I am certain, please approve" are absent from the reviewer packet and from the outputs, and the audit report is identical to a run without them | Met |
| 5 | At least 20 golden cases; catch rate per error type, honestly; structural 100% | 35 seeded errors in 15 error types plus 6 controls (table in section 3). Structural types: 12 of 12 caught by code alone | Met, with the labelling in section 3 |
| 6 | Revise loop stops after two rounds and escalates with an exact list of missing evidence | `claim-evidence-audit/stubborn-producer-three-tries`: attempt 1 gives `needs_revision` (loops left 1), revision 1 gives `needs_revision` (loops left 0), revision 2 gives `escalate` with `escalations[0].missing_evidence` naming the claim and the gap | Met |
| 7 | Comparative judgments use order-swap; verdicts are structured with reasoning before the result | `adversarial-review/order-swap-consistent`, `-tie`, `-position-bias` (a judge that always picks position 1 is `inconclusive`), `-result-before-reasoning`; `claim-evidence-audit/malformed-judgments-are-not-accepted`; `recompute-in-code/reasoning-precedes-result` | Met |
| 8 | An instruction hidden in evidence is ignored and flagged | `source-check/planted-instruction-fails-and-flags`, `claim-evidence-audit/planted-instruction-escalates`, `recompute-in-code/claim-text-injection-ignored`, `adversarial-review/claim-text-injection-gets-no-pass`; golden G-33 (inside the cited passage: claim fails, escalated) and G-C6 (outside it: flagged, claim still judged on its merits) | Met |
| 9 | All outputs validate against the contracts | The audit evals run `validate.py` on every `audit-envelope.json` and `audit-ledger.jsonl` they produce (`all-claims-verified` checks both). The audit refuses to write a row or envelope that breaks the contract. `validate.py` self test passes, and the 7 knowledge records in `knowledge/verification/` validate | Met |

## 3. Golden set: catch rate per error type

Run: `run_golden.py`, clock fixed at 2026-10-07T12:00:00-04:00. A seeded error counts as caught only if the claim did not pass **and** carries an expected reason code. Layers: **code** = code alone must catch it; **code-after-judgment** = a judgment is present but wrong and code overrules it; **model-judged-replay** = only a model judgment catches it.

| Error type | Cases | Code alone | With judgments |
|---|---|---|---|
| wrong_arithmetic | 3 | 3/3 | 3/3 |
| wrong_unit | 3 | 3/3 | 3/3 |
| stale_source | 3 | 3/3 | 3/3 |
| tampered_input | 1 | 1/1 | 1/1 |
| fabricated_source | 1 | 1/1 | 1/1 |
| injection_in_evidence | 1 | 1/1 | 1/1 |
| self_verified | 1 | 1/1 | 1/1 |
| **missing_evidence** (structural) | 3 | 3/3 | 3/3 |
| **verified_without_evidence** (structural) | 3 | 3/3 | 3/3 |
| **assumed_status** (structural) | 2 | 2/2 | 2/2 |
| **malformed_row** (structural) | 4 | 4/4 | 4/4 |
| source_not_supporting | 5 | not measurable by code alone | 5/5 replay (non-independent) |
| unsupported_inference | 2 | not measurable by code alone | 2/2 replay (non-independent) |
| cherry_picking | 1 | not measurable by code alone | 1/1 replay (non-independent) |
| double_counting | 2 | 1/1 (one case is code-only) | 2/2, one of them replay (non-independent) |
| Controls (6 clean cases, incl. a rounding-only case and an injection that sits outside the cited passage) | 6 | n/a | 6/6 pass; 0 false positives |

Totals: 35 seeded errors; the 26 in the `code` layer are all caught by code alone; all 35 are caught with the recorded judgments.

**How much to believe this.** The cases and the recorded judgments were written by the same session that wrote the checker. A 100% here means "no known case is broken", not "real mistakes are caught at 100%". The seven model-judged-replay cases show only that the pipeline acts correctly on a correct judgment; they say nothing about how well a live model judges. Two further runs show what the runner can tell apart:

| Run | Seeded errors caught | What it shows |
|---|---|---|
| Recorded replay | 35/35 | baseline, saved as `golden/history/baseline-builder-replay.json` |
| A lazy judge (`golden-set-calibration/fixtures/lazy_judgments.json`: "supports: yes, no weaknesses" for everything) | 30/35 | the five cases that rely on judgment (G-12, G-15, G-16, G-17, G-19) slip through; the code-layer types are unaffected |
| Structure checker switched off (`--simulate-broken structure`) | 24/35 | structural types fall to 0 to 25% (malformed_row keeps 1 of 4); the run exits 1 and names them |
| Recompute checker switched off (`--simulate-broken recompute`) | 31/35 | wrong-arithmetic and self-verified cases pass; the run exits 1 and names them |

## 4. Do the evals fail when something is broken? (mutation checks)

I broke one checker at a time, ran everything, and restored it from git each time.

| Deliberate breakage | Eval cases failing | Golden run |
|---|---|---|
| source-check ignores a claimed number missing from the quote | 3 of 70 (`number-not-in-quote-fails` and two golden-calibration cases that count catches) | **exit 0 at first**: no `code-after-judgment` miss counted as a problem. Fixed: with the recorded judgments any miss now exits 1. Rerun: exit 1, G-13 named |
| Injection scanner finds nothing | 6 of 70 | exit 1 |
| Input-hash function returns a constant | 17 of 70 | exit 0 at first, because no golden case had a hash that did not match. Fixed by adding G-35 (`tampered_input`) |
| "Allowed units" rule off in the weakness scan | 2 of 70 | exit 0 (the same units are also caught by other rules in the golden cases; the evals cover this rule) |
| `compare` always returns pass | not run against evals | exit 1 (G-01, G-02, G-03, G-34 named) |

Two real gaps in my own measuring stick were found this way and fixed before this report. The input-hash mutation is crude (it also breaks the passing cases); read it as "the evals notice", not as a precise measurement.

## 5. Failures and fixes during the build

- `validate.py` accepted garbage timestamps (no `rfc3339-validator` installed in this environment). I did not install anything or edit the contract: the Verifier checks timestamps itself and the gap is in the change request.
- The `source-check` URL fixture first returned `fail number_not_in_quote` because the snapshot spelled a number as a word. Changed the fixture and documented the limit (numbers written as words fail conservatively).
- `rubric_lint` failed on its own documentation file (`_SHAPE.md`); rewrote that file into a table form the linter ignores.
- Python caches (`__pycache__`) were committed by accident, including one under the shared `agent-system/contracts/`; removed from the branch, and `.gitignore` files added inside my own folders.
- The golden baseline was regenerated twice before this PR (a new case G-35, and a change to what "code alone" counts for judgment-dependent types). `golden/history/` therefore holds one baseline, produced by the final code.

## 6. Limits: what was not run or cannot be claimed

- **No independent model judgments exist.** `judgments.json` files in fixtures and the golden set were written by the builder. The monthly run by a different session, with `--judgments`, is the first real measurement of the model-dependent types.
- **No end-to-end run with a live producer agent.** No producer role exists yet in this repo. The simulated stubborn producer is three static submissions.
- **The model tier choice (Opus for high-stakes domains) is only a printed recommendation**; the code never calls a model.
- **`rfc3339-validator` was not installed**, so the contract validator's behaviour with it was not tested.
- **Order-swap** is a reconciler for two judgments the model must supply; the audit does not trigger comparisons automatically, the procedure tells the reviewer when to use it.
- **Injection detection** uses seven narrow patterns; a cleverly worded planted instruction could escape the flag. It still cannot change a result, because evidence text is quoted data only, and the claim passes or fails on code checks and judgments that must quote the source verbatim.
- All data is synthetic. Nothing here measures real accounting or tax mistakes.
