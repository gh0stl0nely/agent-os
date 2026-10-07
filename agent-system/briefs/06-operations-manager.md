# Brief 06: Operations Manager

**Status:** forecast, recommend, backtest and reconcile are ready on synthetic data; `submit-order` is blocked on the owner's submission decision; real-data work needs the private store and the exported `item-ordering` skill
**Wave:** 2   **Branch:** `build/06-operations-manager`   **Build with:** Sonnet 5.5   **Runtime type:** Workflow (fixed pipeline, model reasoning at set steps)

## Mission
Run the nightly donut order: validate the data, research tomorrow's conditions, forecast per flavour, explain the numbers with evidence, get the owner's approval, and submit before the supplier cutoff. Also own inventory reconciliation and waste review.

## Why it exists
The owner runs this by hand every evening. The current output is slightly off per flavour (over on some, under on others) and arrives without proof of why. The owner wants it to run automatically on a schedule, with reasoning and research (weather, events, holidays, weekday versus weekend, past orders of the same or similar flavours), and a measurable track record.

## Read first (after the BUILD-PROTOCOL reading order)
1. `architecture.md` diagram 3 (the nightly timeline) and diagram 2 (the verification gate)
2. `README.md` open decisions (order submission)
3. The owner's existing `item-ordering` skill (282 lines plus references). It holds accumulated rules and a verification checklist. The owner exports it to the private store or attaches it to your session. Read it in full before designing anything. If it is not yet available, build against the spec below and say so in `STATUS.md`.
4. Knowledge records from the Librarian for weather, events and holiday sources and their usage terms (when available)

## You own
`agents/06-operations-manager/**`; skills `forecast-demand`, `recommend-order`, `submit-order`, `inventory-reconcile`, `waste-review`, `backtest`; knowledge namespace `ordering`.

## Skills to build
| Skill | Trigger | Inputs | Output | Evidence rule | Highest class |
|---|---|---|---|---|---|
| backtest | Weekly, and before any model or rule change | Historical ordered, sold and waste per flavour | Per-flavour error, bias, and result versus the naive baseline | Rolling replay of past weeks; numbers from a script | R1 |
| forecast-demand | Nightly after the data check | Clean data, dated condition facts (weather, events, holidays), brain rules | Per-flavour forecast with uncertainty | Math in code; every adjustment cites a claim id with a source | R1 |
| recommend-order | After the forecast | Forecast, constraints | Per-flavour order number, baseline, each adjustment with its evidence, and the verification checklist | Verifier pass required before it goes to the owner | R1 |
| submit-order | Approval received | Approved order | Submits (or prepares) the order and logs confirmation | Preflight Brief written at planning time, never at 7:44 | R4 |
| inventory-reconcile | Daily | Inventory log, POS, orders | Differences and likely causes | Computed differences | R0 |
| waste-review | Weekly | Waste history | High-waste flavours and what drove them | Computed from data | R0 |

Design points the builder must respect:
- **Baseline first.** The naive baseline is a trailing same-weekday average. No signal (weather, event, holiday) enters the forecast unless the backtest shows it improves on the baseline. If nothing beats the baseline, recommend the baseline.
- **Weekday and weekend demand are modelled separately**, as the existing skill does.
- **New or returning flavours** with little history use the relative-demand fallback in the existing skill (historical popularity share combined with current demand), not stale absolute numbers.
- **Explicit owner targets override computed numbers**, as in the existing skill; preserve that mechanism.
- **Error analysis.** The owner says the output is slightly off per flavour and may be missing something. Produce a report of which signals correlate with the error, flavour by flavour. That report is a primary deliverable.
- **Waste and stockout costs are asymmetric.** The cost parameters come from the owner; do not invent them.
- Numbers that include real business figures live in the private store. This repo holds the mechanism, synthetic examples, and nothing proprietary.

## Reuse and wrap
Wrap `item-ordering`: decompose it into (a) brain rules, (b) deterministic scripts, (c) the verification checklist, (d) the skill wrapper. Also `staff-scheduler` and `menu-update` are related but out of scope for this build.

## Interfaces
Consumes: Data Steward (clean data or blocked), Librarian (dated facts), Verifier, Guardian. Produces: recommendation envelope to the Chief of Staff; order confirmation; ledger entries. Contracts: agent-envelope, claim-ledger, preflight-brief, autonomy-matrix.

## Runtime spec
Proposed times, to tune: data check 6:30pm, forecast 6:50, recommendation to the Verifier 7:10, push to the owner 7:15, answer due 7:30, nudge 7:40, submit by 7:45, supplier cutoff 8:00. Weekly backtest. Model: Sonnet; the Verifier reviews on top. If the owner has not answered, apply their standing approval if one covers it; otherwise do nothing and alert.

## Submission (blocked)
Build `submit-order` in "prepare only" mode: produce the exact order and a clearly marked unverified cart link attempt if the supplier portal supports it; leave the real submission adapter as a stub with a documented interface. The decision is the owner's: (A) prepare and the owner taps, (B) drive the owner's already-signed-in browser (requires that browser to be running; agents must not type the password), or (C) another channel the supplier accepts. Do not choose for the owner.

## Data and fixtures
Synthetic ordered, sold and waste data across multiple flavours and weeks, with weekday and weekend patterns, a holiday, a weather shock, and a new flavour. A simulated clock for the deadline logic.

## Role-specific guardrails
- Submission is class R4: the Preflight Brief is written when the order is planned, not at the deadline.
- Never submit without the owner's approval or a valid standing approval.
- Never place an order that the ledger cannot justify.

## Acceptance criteria
1. The backtest runs on fixtures and reports per-flavour error, bias, and comparison with the baseline.
2. A recommended order is exactly reproducible from its logged inputs.
3. Every adjustment to the baseline cites a claim id with a source; an adjustment without evidence is dropped, not softened.
4. A signal that does not beat the baseline in the backtest is not used (tested).
5. The new-flavour fallback works on a fixture and is labelled as lower confidence.
6. The deadline logic passes a simulated-clock test: push at 7:15, nudge at 7:40, no submission after 7:45, correct fallback behavior.
7. `submit-order` in prepare-only mode produces the exact order, requires approval, and never contacts the supplier.
8. The error-analysis report exists and ties error to signals per flavour.
9. An instruction hidden in a weather or event data field is ignored and flagged.
10. Outputs validate against the contracts.

## Out of scope
Scheduling staff, menu changes, marketing, the accountant's statements.

## Questions for the owner
1. Shelf life per flavour and what counts as waste versus a sale-day leftover?
2. Supplier minimums, lead times, and the exact cutoff?
3. The relative cost of one wasted donut versus one missed sale, per flavour group?
4. Which order submission option (A, B or C), and the fallback if no answer by 7:45?
5. Which flavours are new or seasonal?
