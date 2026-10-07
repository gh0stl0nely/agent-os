# Status: 02 Verifier

- **State:** built; pull request open for review (not merged)
- **Branch:** `build/02-verifier`
- **Last updated:** 2026-10-07 (Wed), Toronto time

## Done
- Five skills with scripts, fixtures and evals: `claim-evidence-audit`, `recompute-in-code`, `source-check`, `adversarial-review`, `golden-set-calibration`.
- Rubric shape, a generic rubric, a synthetic example rubric, and `rubric_lint.py`.
- Golden set: 35 seeded errors across 15 types plus 6 clean controls, a runner with history and drift comparison, and a baseline.
- Eval runner: 70 eval cases, all passing (`python3 agents/02-verifier/run_evals.py`).
- Seven research records in `knowledge/verification/`; all validate against the contract.
- `PLAN.md`, `QUESTIONS.md`, `CARD.md`, `EVAL-REPORT.md`, and the contract change request at `agent-system/change-requests/02-verifier-contract-gaps.md`.

## Next steps
1. Reviewer session re-runs the evals and compares with `EVAL-REPORT.md`.
2. Owner answers `QUESTIONS.md` in one batch.
3. First monthly calibration by a session that did not write the cases (`run_golden.py --judgments FILE`); that gives the first independent number for the judgment-dependent error types.
4. Domain roles supply their rubrics in the shape in `rubrics/_SHAPE.md`.

## Blocked
Nothing was blocked. No action in this build was stopped by a permission prompt or the auto-mode classifier, so nothing is listed here. (Not done by choice, not by a block: `pip install rfc3339-validator` was not run because that would change the environment other roles rely on; the gap is in the change request instead.)
