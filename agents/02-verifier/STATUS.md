# Status: 02 Verifier

- **State:** review round 1 fixed; waiting for the reviewer to re-check PR #1 (not merged)
- **Branch:** `build/02-verifier`
- **Last updated:** 2026-10-07 (Wed), Toronto time

## Done
- Five skills with scripts, fixtures and evals: `claim-evidence-audit`, `recompute-in-code`, `source-check`, `adversarial-review`, `golden-set-calibration`.
- Rubric shape, a generic rubric, a synthetic example rubric, and `rubric_lint.py`.
- Golden set: 39 seeded errors across 18 types plus 6 clean controls, a runner with history and drift comparison, and a baseline.
- Eval runner: 82 eval cases, all passing (`python3 agents/02-verifier/run_evals.py`); `check_scope.py` guards the role's lane.
- Seven research records in `knowledge/verification/`; all validate against the contract.
- `PLAN.md`, `QUESTIONS.md`, `CARD.md`, `EVAL-REPORT.md`, and the contract change request at `agent-system/change-requests/02-verifier-contract-gaps.md`.
- **Review round 1 (PR #1, "changes requested") fixed, in the requested order, each with regression cases (details and evidence in `EVAL-REPORT.md` section 0):**
  1. A claim citing one real and one nonexistent source is now blocked and flagged, not verified.
  2. `run_golden.py --judgments` keeps the built-in faulty judgments for G-13 and G-14; "blocked for another reason" is its own outcome.
  3. The deleted tracked `scripts/__pycache__/post_threads.cpython-313.pyc` is restored; removal is only a suggestion in the change request.
  4. `scope_mismatch` blocks; an on-topic passage is `unsupported`, not `off_topic`; a hedged claim blocks; golden README fixed (G-35 to G-39, G-C4).

## Next steps
1. Reviewer re-checks PR #1 against the comment listing each change.
2. Owner answers `QUESTIONS.md` in one batch. New this round: 5 (block on any unchecked citation), 6 (replace the ambiguous control G-C4; needs a Preflight Brief), 7 (scope mismatch and hedges block).
3. Fully independent calibration: a fresh session, ideally another model family, runs `run_golden.py --judgments FILE` (the reviewer's file covers the first 41 cases only, not G-36 to G-39).
4. Domain roles supply their rubrics in the shape in `rubrics/_SHAPE.md`.

## Blocked
Nothing was blocked by a permission prompt or the auto-mode classifier, in the first build or in this round. Nothing is waiting on an approval.
- Environment note, not a permission block: `gh pr create` returned HTTP 403 in the first round because GitHub GraphQL is not available from these sessions; the PR was opened once through the REST API instead, as the error message directs. This round's PR comment is posted the same way.
- Not done by choice: `pip install rfc3339-validator` (it would change the shared environment); the gap is in the change request.
