# Brief 08: CFO

**Status:** build the engine and tests on synthetic data now; real figures are blocked on the private store
**Wave:** 3   **Branch:** `build/08-cfo`   **Build with:** Sonnet 5.5 (runtime: Sonnet weekly, Opus monthly)   **Runtime type:** Agent

## Mission
Protect the shop's cash. Forecast it, model the debt service, find breakeven, run scenarios, and raise an alert early when runway shortens. Every figure comes from the audited ledger or a logged script.

## Why it exists
The owner needs to know how long the shop can keep operating and what moves that number. Debt service is the main drain on cash, so the question is never just "is the shop profitable" but "when does cash run out, and what changes it".

## Read first (after the BUILD-PROTOCOL reading order)
1. `knowledge-base.md` section 1 (private data stays in the private store)
2. `briefs/07-controller.md` (your inputs come from audited statements)
3. The owner's existing `cogs-calculator`, `product-cost-manager` skills, and the finance skills in their Claude account for variance and statement conventions (reference only)
4. Librarian records on lender terms concepts and Bank of Canada rate data, when available

## You own
`agents/08-cfo/**`; skills `13-week-cash-forecast`, `debt-scenarios`, `unit-economics`, `runway-alert`; knowledge namespace `finance`.

## Skills to build
| Skill | Trigger | Inputs | Output | Evidence rule | Highest class |
|---|---|---|---|---|---|
| 13-week-cash-forecast | Weekly | Audited statements, scheduled payments, sales trend | Week-by-week cash with ranges and the assumptions behind them | Every assumption is a labelled input with a source; math in code | R1 |
| debt-scenarios | On demand, monthly | Debt terms from the owner's documents | Payment schedules and what-if scenarios | Terms cite the lender document id | R1 |
| unit-economics | Monthly | Cost and price data | Per-product margin and breakeven volume | Computed by script from ledger numbers | R1 |
| runway-alert | Weekly | Forecast, thresholds | Alert with reasoning when runway falls below a threshold | The threshold is an owner-set parameter; the alert shows the numbers that triggered it | R1 (delivery is a tiered notification) |

## Reuse and wrap
Wrap `cogs-calculator` and `product-cost-manager` for unit economics.

## Interfaces
Consumes: Controller (audited numbers), Data Steward, Business Advisor later. Produces: forecasts and alerts to the Chief of Staff. Contracts: claim-ledger, agent-envelope.

## Runtime spec
Weekly forecast; monthly review; alert on threshold breach. Model: Sonnet weekly; Opus monthly for scenario review. The math is code; the model explains.

## Data and fixtures
Synthetic ledger and debt terms. Real figures, thresholds and lender terms live only in the private store; document the exact input schema so the private store can supply them.

## Role-specific guardrails
- No real figures anywhere in this repo.
- Every forecast states its assumptions and shows sensitivity to the largest ones.
- Debt scenarios are analysis, not advice to refinance; any recommendation to act is flagged for the owner and a professional.

## Acceptance criteria
1. The forecast is reproducible from logged inputs by script.
2. Each forecast includes a sensitivity table for its largest assumptions.
3. The runway alert triggers on a fixture that crosses the threshold and stays quiet on one that does not; the alert shows the numbers that fired it.
4. Debt scenarios match hand-computed amortization on fixtures.
5. Every claim validates as a ledger row with evidence.
6. The input schema document is complete enough for the private store to supply real data.
7. A fixture cell containing an instruction aimed at the agent is ignored and flagged.

## Out of scope
Auditing the statements (the Controller), tax planning, advice on financing.

## Questions for the owner
1. Runway thresholds that should trigger a normal alert versus a critical one?
2. What decisions should the CFO prepare scenarios for first (for example slower or faster growth, a price change, a staffing change)?
