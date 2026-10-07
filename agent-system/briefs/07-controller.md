# Brief 07: Controller

**Status:** method and skills are ready on synthetic statements; real-data work is blocked on the private store, the books system and file formats, the accountant's sample statements, and the exported existing skills
**Wave:** 2   **Branch:** `build/07-controller`   **Build with:** Sonnet 5.5 (runtime: Opus for the monthly audit)   **Runtime type:** Agent

## Mission
Act as an independent CPA-level auditor of the accountant's monthly statements. For every line you can, tie it to a source document, recompute it, and say exactly what is wrong or what you could not verify. Never handwave.

## Why it exists
The owner checks the accountant's statements by hand and then corrects the AI's own verification. The accountant is a CPA and generally good; occasional assumptions seem to come from missing context. The owner wants an auditor with the same domain knowledge that proves every claim, and, in time, may replace the outside accountant.

## Read first (after the BUILD-PROTOCOL reading order)
1. `knowledge-base.md` section 7 and `contracts/claim-ledger.schema.json`
2. The owner's existing `reconciliation-verifier` skill (481 lines) and `financial-reviewer` skill (266 lines). They contain: monthly gates, document checklists, reconciliation formulas, known pitfalls, materiality thresholds, vendor recognition, the accountant's bookkeeping patterns, a review workflow, a lessons-learned log and a self-learning protocol. They hold private business knowledge, so the owner exports them to the private store or attaches them to your session. Read both in full before designing. They must never be committed here.
3. `reusable-skills.md`, entry for `anthropics/financial-services` (GL Reconciler, Statement Auditor, Month-End Closer). Vet before using; adapt for Canada; do not use the headless deployment (needs an API key).
4. Librarian records for the applicable Canadian accounting standard, HST treatment, capital cost allowance and shareholder loans, when available (grade A sources)

## You own
`agents/07-controller/**`; skills `statement-audit`, `bank-card-reconciliation`, `cutoff-accrual-check`, `variance-analysis`, `accountant-query-drafter`, `evidence-pack`; knowledge namespace `accounting`.

## Skills to build
| Skill | Trigger | Inputs | Output | Evidence rule | Highest class |
|---|---|---|---|---|---|
| statement-audit | Statements arrive from the accountant | Statements plus source documents | Findings and a coverage report | Each line is tied to a document id, or listed as unverifiable with the document that would resolve it | R1 |
| bank-card-reconciliation | Monthly | Bank, card and credit-line statements | Reconciled balances and breaks | Balances recomputed by script | R1 |
| cutoff-accrual-check | Monthly | Statements, invoices | Timing and accrual issues | Dates compared by script | R1 |
| variance-analysis | Monthly | Current and prior periods | Drivers of change with sources | Numbers by script | R1 |
| accountant-query-drafter | After findings | Findings | Precise, respectful questions to the accountant, ranked by dollar impact | Each question cites the finding and the document | R1 (sending is R4) |
| evidence-pack | After audit | Findings and documents | A folder or document the owner can open: every claim, its source, its recomputation | Every claim links to its ledger row | R1 |

Design points:
- Every finding carries: statement line, source document id, recomputation, difference, materiality, severity, the question for the accountant. The materiality rules come from the owner's existing skill (private); this repo holds the mechanism and synthetic examples.
- There is an explicit **unverifiable list** with what document would resolve each item. "Assumed" is not allowed anywhere.
- A **coverage report** states the share of statement lines tied to evidence.
- The existing skill's self-learning protocol and lessons log become the learning loop: an owner correction becomes a brain rule (private) plus a regression case that replays on later audits.
- Canadian specifics (HST, accounting standard, capital cost allowance, shareholder loans) are researched through the Librarian and graded A before use.

## Reuse and wrap
Wrap `reconciliation-verifier` and `financial-reviewer` as above. Candidate adaptation: Statement Auditor and GL Reconciler from `anthropics/financial-services` after the Guardian vets them.

## Interfaces
Consumes: Data Steward, Librarian, Verifier (including your own accounting rubric). Produces: audit envelope and evidence pack to the Chief of Staff; inputs to the CFO. Contracts: claim-ledger, agent-envelope.

## Runtime spec
Triggered when statements arrive; weekly spot checks. Model: Opus for the monthly audit (judgment across many documents), Sonnet for routine reconciliation. Ship `agents/07-controller/rubric.md` so the Verifier can check your work against an accounting rubric.

## Data and fixtures
Synthetic statements with at least 15 seeded errors: timing differences, a sales-tax split on a capital purchase, a misclassified vendor, a transposed digit, a missing statement, a duplicate, an unlabeled owner contribution, a prior period corrected after review. Real data: owner supplies samples via the private store or session attachment.

## Role-specific guardrails
- Sending anything to the accountant is class R4: draft only, with a Preflight Brief.
- Never state a conclusion you could not tie to a document.
- Real statements never enter this repo.

## Acceptance criteria
1. Detects all seeded errors in the synthetic statements, or lists any missed with the reason.
2. Every finding validates as a claim row; zero rows are `assumed`.
3. The coverage report states the share of lines tied to evidence and lists every unverifiable item with the resolving document.
4. Queries to the accountant are ranked by dollar impact and cite evidence.
5. The evidence pack opens cleanly and links each claim to its ledger row.
6. The correction-to-rule mechanism works: a simulated owner correction creates a brain rule and a regression case that fails before and passes after.
7. `rubric.md` exists and the Verifier can use it (tested with the Verifier's rubric interface).
8. A line item description containing an instruction aimed at the agent is ignored and flagged.
9. Outputs validate against the contracts.

## Out of scope
Producing the books, tax filings, advice on replacing the accountant.

## Questions for the owner
1. Which system holds the books, and in what format does the accountant deliver statements?
2. Which documents does the accountant already supply each month, and which do you have to ask for?
3. Which materiality thresholds should the Controller start from?
4. Which accounting standard does the corporation use?
