# Plan: 02 Verifier

Written before building, as BUILD-PROTOCOL requires. Builder session: Sonnet 5.5, branch `build/02-verifier`, base `main` at `3cc9788`.

## Mission, in my own words

Be the independent checker that sits between every producer agent and the owner. A producer hands over an envelope that points at claim rows. For each claim I decide whether the evidence supports it, using code wherever code can decide (schema, recomputing numbers, source exists, source is current, quoted passage really is in the source) and the model only for judgment that code cannot do (does this passage actually support this claim, what is weak about the reasoning). I never see the producer's reasoning, I never fix their work, and I never pass something I could not check. Anything unprovable goes back with the exact list of what is missing. After two revise loops I escalate instead of looping.

## Assumptions (each is checkable, none is a hidden decision)

| # | Assumption | If wrong |
|---|---|---|
| A1 | Knowledge records are stored as one JSON file each, `knowledge/<namespace>/K-<id>.json`, because `contracts/validate.py` reads JSON and the schema calls the record "front matter of a small file". | Only the file wrapper changes; the fields are the schema's. |
| A2 | "Envelope with per-claim verdict" means: the envelope carries the status and claim ids, the per-claim verdicts live in the ledger rows (`status` plus `verification`) and in an audit report the envelope points to through `inputs`. The envelope schema has no verdict field and I may not edit it. | A change request (written, see below) would add a `verdicts` field. |
| A3 | The brief says I produce envelopes to the Chief of Staff, so every output envelope is addressed to `01-chief-of-staff`, including `needs_revision`. The Chief of Staff routes the revision to the producer. A flag `--revision-to producer` addresses it to the producer instead. | One-line change. Asked as a question to the owner. |
| A4 | The Verifier, and only the Verifier, sets `verified`. A row that arrives already marked `verified` is re-verified from scratch and its incoming `verification` block is discarded. | None needed; this is stricter, not looser. |
| A5 | Tolerance for recomputation comes from the rubric, never from the producer, so a producer cannot pass a wrong number by declaring a loose tolerance. | None. |
| A6 | Producer scripts are run only from inside an allowed root, with a scrubbed environment and a timeout. This is not a sandbox. Running unreviewed scripts is the Guardian's concern, so the harness refuses anything outside the root and the CARD says so. | Guardian can add stronger isolation. |
| A7 | WebFetch returns a model-written rendering of a page, not raw text. A quote can therefore fail a verbatim check against fetched text for innocent reasons. URL sources that fail the verbatim check are `unverifiable`, never `fail`, and never `pass`. | None. |
| A8 | The first real calibration needs a judge that did not write the cases. Cases here were written by the builder, so model-judged results in this build are a replay, not an independent measurement. The report says so on every affected number. | The first monthly run by a separate session provides the real number. |

## Reusable work reviewed

| Source | Commit | Decision | What I took or why not |
|---|---|---|---|
| `obra/superpowers`, skill `verification-before-completion` ([repo](https://github.com/obra/superpowers)) | `8ca22dba9a94f28898bbce59f2537ff4d87c747d` (HEAD of `main` when read; the file and the SHA were fetched a minute apart) | **Adapt** the pattern, install nothing | Rule "identify the proving check, run it fresh, read all of the output, only then claim" becomes `recompute-in-code` (always re-run, never trust a logged result) and the audit procedure (a claim passes only if a check was actually run). Its list of hedging words ("should", "probably") becomes a lint in `adversarial-review`. It targets software tests, so nothing is copied. The file carries no license text; the repo license (MIT per `reusable-skills.md`) was not independently confirmed, which is one more reason not to copy text. |
| `anthropics/skills`, skill `skill-creator` | `683bc88e56f3e09ba94f7055977f3d3aa499f202` (HEAD) | **Adopt as an authoring guide**, read only | Used for skill layout and description-writing advice. Not vendored into this repo. |
| `agent-system/contracts/validate.py` | repo `3cc9788` | **Reuse** unchanged | Imported by path for schema checks. Finding: without the optional `rfc3339-validator` package it accepts garbage `date-time` values (proved in this environment). I add my own strict timestamp check and file a change request rather than edit the contract. |
| Owner's private skills `reconciliation-verifier`, `financial-reviewer` | not in this repo | **Not used here** | They are accounting rubrics the Controller wraps. I only define the plug-in shape (`rubrics/<domain>.md`). |
| `anthropics/financial-services`, `openaccountants/*`, awesome lists | n/a | **Reject for this role** | Accounting and tax content is out of scope (Out of scope in the brief). |

Research records (grade A unless stated) are in `knowledge/verification/`. `knowledge/` was empty, so no earlier research existed to reuse.

## Design

Pipeline, in the order the brief requires (deterministic first, model second):

1. **Structure** (`claim-evidence-audit/scripts/structure_check.py`): contract schemas through `validate.py`, plus Verifier-only rules: strict timestamps, number claims need `value` and `unit`, ids unique and matching the envelope, producer self-verification discarded.
2. **Evidence checks**, per evidence item: `computation` goes to `recompute-in-code`; `document`, `url`, `owner_statement`, `kb_record` go to `source-check` (exists, current, locator resolves, quoted passage verbatim, numbers present, then the model's support judgment).
3. **Injection scan** over every piece of evidence text. Hits are reported and ignored; a hit inside the passage a claim relies on fails that claim.
4. **Adversarial review** over a packet that contains only claims, evidence and rubric (`build_packet.py` whitelists fields). A weakness scan in code runs first (unit, double counting, stale retrieval), then the model's judgment.
5. **Decision**: pass needs at least one evidence item that was actually checked and passed, no failing item, no blocking weakness. Output rows validate against the contracts before being written.
6. **Loop control**: status `ok`, `needs_revision` (loops left minus one), `blocked` (the audit itself cannot run), or `escalate` (loops exhausted, or evidence only the owner can supply) with the exact missing evidence.

Model judgments arrive through a `judgments.json` file whose entries must put `reasoning` before the result. Phase 1 (code) can finish alone when it already finds failures, which saves tokens. Otherwise it emits the exact judgment requests and phase 2 finishes.

## Skills, in build order

1. `claim-evidence-audit` (orchestrator, structure check, packet builder, injection scan, loop control)
2. `recompute-in-code` (harness plus tolerance comparison)
3. `source-check`
4. `adversarial-review` (weakness scan, order-swap reconciler)
5. `golden-set-calibration` (runner, history, drift)

Plus: `rubrics/_SHAPE.md`, `rubrics/generic.md`, `rubrics/example-invoice.md`, `rubric_lint.py`, a golden set of at least 20 seeded-error cases, `run_evals.py`, `CARD.md`, `EVAL-REPORT.md`.

## Risks

| Risk | Handling |
|---|---|
| Model judgments cannot run in CI | Split every metric by layer (code or model-judged replay) and never blend them. |
| Builder wrote the golden cases and also supplies the judgments | Disclosed as A8; model-judged rates are labelled non-independent. |
| Over-building | One orchestrator, small scripts, stdlib plus `jsonschema` only. Nothing beyond the brief. |
| A passing recompute from a script the producer controls | The harness hashes the logged inputs, runs only scripts inside the root, and takes the tolerance from the rubric. A script that simply prints the claimed value would pass, which is a known limit: the producer's script is the evidence, and `adversarial-review` plus the owner's sampling are the backstop. Stated in the CARD. |
| Contract gaps | Change request `agent-system/change-requests/02-verifier-contract-gaps.md`. |

## Questions for the owner

See `QUESTIONS.md` (two from the brief, plus those that came up while planning).
