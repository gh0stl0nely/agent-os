# Questions for the owner: 02 Verifier

Answer once, in one batch. Each says what I need, why, and what I do meanwhile.

1. **High-stakes threshold (from the brief).** At what dollar amount or consequence does a claim count as high-stakes and get the Opus review?
   *Meanwhile:* a rubric marks its own domain `stakes: high` (finance, tax, cash and anything customer-facing default to high, so Opus), and the dollar threshold in `rubrics/*.md` is `null`, meaning the domain alone decides. The code reads the threshold when you set one.

2. **Second model family (from the brief).** Is a second family ever acceptable for review if it adds cost?
   *Meanwhile:* none is used. The Verifier never incurs spend (class R6); it would only flag it.

3. **Where a revision request goes.** I address every output envelope to the Chief of Staff (the brief says so), including `needs_revision`, and the Chief of Staff routes it back to the producer. Do you prefer the Verifier to send revisions straight to the producer? It is a one-flag change.
   *Meanwhile:* Chief of Staff routing.

4. **Real data for calibration.** The golden set is synthetic and was written by the builder. The monthly calibration is only independent when a different session judges real, de-identified examples of past producer mistakes. Are you willing to supply a handful (for example, past cases where you caught the AI out) through the private store, never this repo?
   *Meanwhile:* synthetic cases only, results labelled non-independent.

5. **A claim that cites something the Verifier cannot check (from the PR #1 review).** I now block a claim when any cited item cannot be checked (a missing file, an unreadable page), even if another cited source is real, and flag it `unverifiable_evidence` with the item named. The reviewer would block too. Do you agree, or would you rather it be a flag only on a claim that otherwise passes?
   *Meanwhile:* blocked.

6. **Replace the ambiguous golden control G-C4.** Its case is two claims about the same line, one worded "(restated)", which the source never says; a strict independent judge fairly fails it. Changing a golden case is R2 (it changes the measuring stick), so it needs a Preflight Brief and your yes. Proposal: replace it with two genuinely different quantities that happen to be equal, cited from different lines.
   *Meanwhile:* the case is unchanged; its README row now says what it really is, and the runner reports it as a false positive under a strict judge.

7. **Scope mismatch and hedged claims now block (from the PR #1 review).** A reviewer-found `scope_mismatch` (right number, wrong period or entity) and a hedge such as "probably" on a claim filed as a fact both fail the claim instead of passing with a note. Say so if you would rather either be a note.
   *Meanwhile:* blocking.
