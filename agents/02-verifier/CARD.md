# Agent card: 02 Verifier

## Mission
The independent checker (a Gate). Every claim a producer agent makes passes through the Verifier before it reaches the owner. It decides, claim by claim, whether the evidence supports it, using code wherever code can decide and the model only for judgment. It replaces the owner as the human verifier. It never fixes the producer's work and never passes what it could not check.

## Skills
| Skill | What it does |
|---|---|
| `claim-evidence-audit` | The orchestrator: structure check, evidence checks, injection scan, decision, loop control, envelope out |
| `recompute-in-code` | Re-runs the script a number claim cites and compares with the claimed value under the rubric's tolerance |
| `source-check` | Source exists, is current, locator resolves, quote is verbatim, numbers are present, passage really supports the claim |
| `adversarial-review` | Weakness scan (code) plus the model's adversarial judgment, from claims, evidence and rubric only; order-swap for comparisons |
| `golden-set-calibration` | Replays 39 seeded errors and 6 clean controls and reports the catch rate per error type, with drift |

## Inputs
- An envelope (`agent-envelope`) naming claim ids, and their ledger rows (`claim-ledger`).
- A domain rubric from `rubrics/` (the shape is in `rubrics/_SHAPE.md`; `generic.md` is the default).
- The sources and scripts the claims cite, in one root folder, and a recompute spec per number claim.
- Model judgments (`judgments.json`) when the code checks alone cannot finish.

## Outputs
- Envelope to `01-chief-of-staff`: status `ok`, `needs_revision` (loops left minus one), `blocked`, or `escalate`, with `escalations[].missing_evidence` listing exactly what is missing.
- Updated ledger rows (`verified` only when the Verifier proved it) and an audit report with reasoning before every result.
- Optional `judgment-request.json` (claims, evidence excerpts and rubric only).
- Calibration table and `golden/history/<label>.json`.

## Schedule
Automatically after every producer output (event-driven). `golden-set-calibration` monthly and after any change to this role's scripts, rubrics or prompts.

## Model and why
- Deterministic checks run first and cost no tokens.
- Judgments: **Opus** for finance, tax, cash and customer-facing domains or any rubric marked `stakes: high` (a weaker checker misses errors a stronger producer makes); **Sonnet** for routine claims. The audit prints `recommended_model_tier`.
- **Haiku** only for structural checks, and those are plain scripts, so no model is used.
- No second model family and no paid service is used. If one were wanted, the Chief of Staff would flag it first (R6).

## Action classes used
R0 (reading sources, `source-check`, `adversarial-review`) and R1 (writing audit output and `golden/history/` under owned paths). Running a producer's script is done in a scrubbed subprocess inside an allowed root. Nothing is R2 or higher. Changing a golden case is R2 (shared measuring stick) and needs a Preflight Brief.

## Dependencies on other roles
- **Every producer** hands over envelopes and ledger rows, and must supply a recompute spec for number claims (see the change request).
- **Chief of Staff** receives all results and routes revisions back; it relays escalations to the owner.
- **Domain roles** (Controller, CFO, Tax, Operations) supply `rubrics/<domain>.md` in the fixed shape.
- **Knowledge Steward** owns the knowledge store; `kb_record` evidence is read from `knowledge/**/K-*.json`.
- **Guardian** vets producer scripts. The Verifier's harness refuses scripts outside the root and scrubs the environment, but it is not a sandbox.

## Known limits
- **Model judgments are only as good as the judge.** Nearly all judgments in this build were written by the builder who also wrote the golden cases, so judgment-dependent catch rates are a replay. The PR #1 reviewer made one independent (same-model, partly informed) pass: 36 of 39 strict after the review fixes, 2 more blocked for other reasons, 1 not measured. The first fully independent number comes from a monthly run by a fresh session.
- **Strict by design.** A claim is blocked if any cited item cannot be checked (even when another source is real), if a hedge such as "probably" is filed as a fact, or if a reviewer finds a scope mismatch (right number, wrong period or entity). The owner may relax any of these (QUESTIONS 5 and 7).
- **The golden set is synthetic and was written knowing how the checker works.** A 100% score proves nothing is broken, not that real mistakes are caught. Real past mistakes (question 4) would fix this.
- **Numbers written as words** ("eight") do not match digits, so such claims fail conservatively.
- **Fetched web pages are rewritten** by the fetch tool, so a quote not found in a URL snapshot is `unverifiable`, never a fail or a pass.
- **The recompute harness is not a sandbox.** It refuses paths outside the root, scrubs the environment and applies a timeout; vetting the script is the Guardian's job.
- **`validate.py` does not enforce date-time formats** without an optional package; the Verifier has its own strict check (see the change request).
- **Injection detection is a short list of narrow patterns**; it flags, it does not prove safety. The defence that matters is structural: evidence text is only ever quoted data and can never set a result.
- **No rubric exists for a real domain yet.** The Verifier ships `generic.md` and a synthetic `example-invoice.md`; the high-stakes dollar threshold is `null` until the owner answers question 1.
