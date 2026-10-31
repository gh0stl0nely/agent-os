# rollback-plan reference

## Checks (names appear in findings)
`class`, `instruction-like-text`, `secrets`, `action`, `no-steps`, `vague-step`, `no-owner`, `no-duration`, `no-test-step`, `untestable`, `weak-test`, `test-where`, `test-on-live`, `no-backup` (R3), `no-external-recall` (R4), `r5-no-revoke`, `r6-no-cancel`, `irreversible-unjustified`, `irreversible-declared`, `thin` (free text).

## What each class needs
- **R2**: steps, owner, duration, a test on a copy or scratch space.
- **R3**: also a backup taken first (what, where), and never a test on the live target.
- **R4**: also how the effect is recalled or limited (delete a post, edit before the cutoff). If it cannot be, declare it irreversible with a reason.
- **R5**: revoke or rotate at the provider. The owner does it; the agent only writes the steps.
- **R6**: how to cancel and what is refunded.

## Test locations
`copy`, `scratch`, `sandbox`, `dry-run`, `documentation` (read the vendor's own page and confirm the option exists), `live` (R2 only, and discouraged).

## Limits
The checker proves the plan is complete and specific, not that it works. The test step must actually be run, and the Verifier checks that result. Vague-step detection is heuristic: short steps and stock phrases are caught; a long but wrong step is not.
