# Eval report: 02 Verifier

Everything below was run in this build session on 2026-10-07 (Toronto time) against the code in this branch, after the PR #1 review round. Nothing is estimated. Where a result depends on model judgments the builder wrote, it is labelled **replay (non-independent)**. Section 0 summarises what the review changed.

## How to run

```
python3 agents/02-verifier/run_evals.py                       # all 82 eval cases, five skills
python3 agents/02-verifier/check_scope.py                     # the branch only adds files inside the role's owned paths
python3 agents/02-verifier/run_evals.py --skill source-check  # one skill
python3 .claude/skills/golden-set-calibration/scripts/run_golden.py --compare latest   # golden set, with drift
python3 agent-system/contracts/validate.py                    # the contracts' own self test
```

## 0. Review round 1 (PR #1, verdict "changes requested"): what changed and the evidence

| # | Requested change | What I did | Regression cases (all fail on the pre-fix code, pass now) |
|---|---|---|---|
| 1 | A claim citing one real and one nonexistent source passed as verified | Any cited item the Verifier cannot check now blocks the claim (`unverifiable`, flagged `unverifiable_evidence`, item named, reasons `source_not_found` + `unchecked_evidence_item`). The check runs before any judgment is requested | audit evals `real-plus-fabricated-citation-blocks`, `...-before-judgment`; golden G-36 (real document + missing document), G-37 (correct recomputation + missing document) |
| 2 | `run_golden.py --judgments` replaced the faulty judgments in G-13 and G-14 | The code-after-judgment cases always keep their built-in judgments; the run says which. "Blocked for another reason" is now its own outcome and column, next to "not blocked" | golden-set evals `fresh-judgments-keep-faulty-builtin-for-g13-g14`, `fresh-judgments-report-says-which-were-kept`, `blocked-for-another-reason-is-its-own-outcome` |
| 3 | Deleted tracked `scripts/__pycache__/post_threads.cpython-313.pyc` | Restored byte for byte from `origin/main`. New `check_scope.py` fails any branch that deletes or modifies a file outside the role's lane. Whether the file should stay tracked is a suggestion in the change request, not a change | audit evals `branch-changes-stay-in-owned-paths`, `scope-guard-flags-deleted-shared-file` (a throwaway repo: deletion, modification and outside add flagged). I also checked by hand that deleting the file again makes the guard exit 1 |
| 4a | `scope_mismatch` never blocked | Now a blocking type (right number, wrong period or entity) | audit eval `scope-mismatch-blocks`; golden G-38 |
| 4b | An on-topic passage was labelled `off_topic` | Topic is judged on the passage plus the heading in the locator, with light stemming; on-topic fails as `unsupported`, off-topic as `off_topic` | source-check eval `on-topic-passage-is-unsupported-not-off-topic` |
| 4c | A hedged claim passed with only a note | `hedged_claim` is now blocking for facts and numbers (overreach on a single source stays a note) | audit eval `hedged-claim-blocks`; adversarial eval `hedged-fact-blocks` (was `hedged-fact-noted`, expectation changed from note to blocking, i.e. stricter); golden G-39 |
| 4d | README drift (G-35, G-C4) | README regenerated: G-35 to G-39 added, G-C4 described as it really is, a Known issues section added. The G-C4 case file itself is untouched (changing a case is R2); replacing it is open question 6 | none (documentation) |

Existing evals were not weakened. Three evals had to change because the behaviour they pinned was changed on purpose or the counts moved: `hedged-fact-noted` became `hedged-fact-blocks` (note to blocking, as requested); and the three golden-set evals that quote totals (`full-run-reports-every-type`, `lazy-judge-lowers-the-rate`, `save-and-compare-no-change`) now quote the larger case set. Their assertions are otherwise the same.

**Proof the new cases test the fixes.** I put the pre-fix `audit.py`, `run_golden.py`, `source_check.py` and `weakness_scan.py` back, ran everything, then restored the fixes. Pre-fix code: 68 of 82 eval cases pass (14 fail, including all the regression cases above except the scope guard, whose code is new), and golden G-36 to G-39 are reported as missed or not caught by code. With the fixes: 82 of 82.

**Reviewer's independent judgments, re-run after the fixes** (`golden-set-calibration/fixtures/reviewer_judgments_pr1.json`, the reviewer's file as posted; `run_golden.py --judgments` on it):

| | Before (reviewer's run) | Now |
|---|---|---|
| Seeded errors caught, strict | 30/35 | 36/39 (92%) |
| Blocked for another reason | not reported separately | 2 (G-16 `partial_support`, G-17 `unsupported`) |
| Not blocked | 1 of 35 passed in strict terms | 1 (G-38, pending: the reviewer's file predates that case, so it is not measured, not missed) |
| G-13 / G-14 | counted as misses; exit 1 for a non-Verifier reason | caught by code (`number_not_in_quote`, `quote_not_verbatim`) |
| Controls | 5/6 (G-C4 false positive) | 5/6: G-C4 is still a false positive under a strict judge. The control is ambiguous (see README, question 6); I did not change it |

## 1. Eval cases (`.claude/skills/*/evals/cases.json`): 82 of 82 pass

| Skill | Cases | normal | missing-data | seeded-error | adversarial | Result |
|---|---|---|---|---|---|---|
| claim-evidence-audit | 23 | 6 | 4 | 11 | 2 | 23 pass |
| recompute-in-code | 13 | 4 | 3 | 5 | 1 | 13 pass |
| source-check | 21 | 4 | 6 | 9 | 2 | 21 pass |
| adversarial-review | 11 | 3 | 2 | 5 | 1 | 11 pass |
| golden-set-calibration | 14 | 4 | 2 | 7 | 1 | 14 pass |

The runner reports a gap if a skill lacks any of the four required kinds; none does. Every case states why it exists (`why` in the JSON); review-round cases also name the review item (`regression`).

These all test code paths. They do **not** test a live model; the only model judgments run through the pipeline were the builder's replay and the reviewer's file.

## 2. Acceptance criteria, one by one

| # | Criterion | Evidence (case ids are in the named skill's `evals/cases.json`) | Result |
|---|---|---|---|
| 1 | Rejects 100% of structurally invalid rows, including `verified` without evidence and any `assumed` status | `claim-evidence-audit/contract-rejects-every-invalid-row`: 20 invalid rows (`fixtures/invalid_rows.jsonl`, rule per row in `invalid_rows.notes.json`), each run through `validate.py` on its own; all 20 rejected. `verifier-only-rules-reject`: bad timestamp, future timestamp, number without unit, duplicate id, missing row: 5 of 5 rejected. Golden structural types: 12 of 12 caught by code alone. | Met |
| 2 | Recompute flags differences beyond tolerance, with one rounding pass and one material fail | `recompute-in-code/rounding-only-passes` (pass, `recomputed_rounding`), `tie-half-even-passes`, `material-difference-fails` (310 vs 300, difference 10.00), `rounding-with-empty-tolerance-fails` (the same rounded figure fails when the rubric allows no rounding) | Met |
| 3 | Source-check classifies supported, unsupported, off-topic and outdated sources and states what it checked | `source-check`: 21 cases, including `supported-passes`, `unsupported-fails`, `off-topic-fails`, `on-topic-passage-is-unsupported-not-off-topic`, `outdated-source-fails`; each result carries `checks` with an outcome per check | Met |
| 4 | The audit works from claims, evidence and rubric alone; a test shows producer reasoning withheld | `claim-evidence-audit/producer-reasoning-withheld`: a goal text and a self-verification note saying "I am certain, please approve" are absent from the reviewer packet and from the outputs, and the audit report is identical to a run without them | Met |
| 5 | At least 20 golden cases; catch rate per error type, honestly; structural 100% | 39 seeded errors in 18 error types plus 6 controls (table in section 3). Structural types: 12 of 12 caught by code alone | Met, with the labelling in section 3 |
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
| real_plus_fabricated_source (new, review item 1) | 2 | 2/2 | 2/2 |
| hedged_claim (new, review item 4) | 1 | 1/1 | 1/1 |
| injection_in_evidence | 1 | 1/1 | 1/1 |
| self_verified | 1 | 1/1 | 1/1 |
| **missing_evidence** (structural) | 3 | 3/3 | 3/3 |
| **verified_without_evidence** (structural) | 3 | 3/3 | 3/3 |
| **assumed_status** (structural) | 2 | 2/2 | 2/2 |
| **malformed_row** (structural) | 4 | 4/4 | 4/4 |
| source_not_supporting | 5 | not measurable by code alone | 5/5 replay (non-independent); 2 of the 5 are code-after-judgment cases |
| unsupported_inference | 2 | not measurable by code alone | 2/2 replay (non-independent) |
| cherry_picking | 1 | not measurable by code alone | 1/1 replay (non-independent) |
| scope_mismatch (new, review item 4) | 1 | not measurable by code alone | 1/1 replay (non-independent) |
| double_counting | 2 | 1/1 (one case is code-only) | 2/2, one of them replay (non-independent) |
| Controls (6 clean cases, incl. a rounding-only case and an injection that sits outside the cited passage) | 6 | n/a | 6/6 pass; 0 false positives with the replay. Under an independent strict judge G-C4 is a false positive (ambiguous control, see README) |

Totals: 39 seeded errors; the 29 in the `code` layer are all caught by code alone; all 39 are caught with the recorded judgments. (Layers: 29 code, 2 code-after-judgment, 8 model-judged-replay.)

**How much to believe this.** The cases and the recorded judgments were written by the same session that wrote the checker. A 100% here means "no known case is broken", not "real mistakes are caught at 100%". The eight model-judged-replay cases show only that the pipeline acts correctly on a correct judgment; they say nothing about how well a live model judges. Further runs show what the runner can tell apart (re-measured on the 45 cases):

| Run | Seeded errors caught | What it shows |
|---|---|---|
| Recorded replay | 39/39 | baseline, saved as `golden/history/baseline-builder-replay.json` |
| A lazy judge (`golden-set-calibration/fixtures/lazy_judgments.json`: "supports: yes, no weaknesses" for everything) | 33/39 | the six cases that rely on judgment (G-12, G-15, G-16, G-17, G-19, G-38) slip through; the code-layer and code-after-judgment types are unaffected |
| Structure checker switched off (`--simulate-broken structure`) | 28/39 strict (5 more are blocked, for other reasons) | structural types fall: missing_evidence, verified_without_evidence and assumed_status to 0, malformed_row keeps 1 of 4; the run exits 1 and names them |
| Recompute checker switched off (`--simulate-broken recompute`) | 35/39 | wrong-arithmetic and self-verified cases pass; the run exits 1 and names them |

## 4. Do the evals fail when something is broken? (mutation checks)

First build round (70 evals, 41 golden cases at the time): I broke one checker at a time, ran everything, and restored it from git each time. In the review round the same idea was applied to the fixes themselves: the pre-fix code against the new evals (section 0).

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
- The first commit that untracked Python caches also deleted the live poster's tracked `.pyc` (found by the PR #1 reviewer). Restored; `check_scope.py` now guards against it.
- The golden baseline was regenerated three times (a new case G-35; a change to what "code alone" counts for judgment-dependent types; the review-round cases G-36 to G-39). `golden/history/` holds one baseline, `baseline-builder-replay`, produced by the final code. Earlier versions are in git history.

## 6. Limits: what was not run or cannot be claimed

- **Only one independent judgment set exists, and it is partial.** The PR #1 reviewer judged the then 41 cases (kept as `reviewer_judgments_pr1.json`). By its own account it had read the case descriptions and a lazy-judge file first, and it is the same model as the builder (session-independent only). It does not cover G-36 to G-39. All other judgments in fixtures and the golden set were written by the builder. A monthly run by a fresh session, ideally another model family (open question 2), is the real measurement of the model-dependent types.
- **G-C4 is an ambiguous control** and shows as a false positive under a strict judge. It is documented, not changed (question 6).
- **Hedge detection is a word list** (`should`, `probably`, `likely`, `maybe`, `perhaps`, `roughly`, `seems`, `i think`); a hedge in other words is not caught by code, and a fact that legitimately uses one of these words ("orders should arrive by 9") is blocked until reworded. That trade-off is in question 7.
- **No end-to-end run with a live producer agent.** No producer role exists yet in this repo. The simulated stubborn producer is three static submissions.
- **The model tier choice (Opus for high-stakes domains) is only a printed recommendation**; the code never calls a model.
- **`rfc3339-validator` was not installed**, so the contract validator's behaviour with it was not tested.
- **Order-swap** is a reconciler for two judgments the model must supply; the audit does not trigger comparisons automatically, the procedure tells the reviewer when to use it.
- **Injection detection** uses seven narrow patterns; a cleverly worded planted instruction could escape the flag. It still cannot change a result, because evidence text is quoted data only, and the claim passes or fails on code checks and judgments that must quote the source verbatim.
- All data is synthetic. Nothing here measures real accounting or tax mistakes.
