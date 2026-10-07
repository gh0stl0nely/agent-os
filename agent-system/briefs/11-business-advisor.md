# Brief 11: Business Advisor

**Status:** ready, but **discovery first**; it depends on data and outputs from roles 05 to 08
**Wave:** 4   **Branch:** `build/11-business-advisor`   **Build with:** Sonnet 5.5 (runtime: Sonnet monthly, Opus quarterly)   **Runtime type:** Agent

## Mission
Keep the shop on a path to a sale in about five years, and keep the owner's bigger goal in view. Track the KPIs, pricing and margin, product mix and competitors, and score readiness for a sale, always from verified data.

## Why it exists
The shop is three months old. The owner needs a business advisor's view of whether the business is healthy and what would make it more valuable, while the end goal (a sale after about five years, then their own venture) stays in sight. The sale price is to be decided later and needs data and justification.

## Discovery first
Interview the owner before building: what "ready to sell" means to them, the KPIs they already watch, competitors they worry about, pricing history, what they have tried. Write the answers to `agents/11-business-advisor/DISCOVERY.md`. Do not assume.

## Read first (after the BUILD-PROTOCOL reading order)
1. The merged cards and outputs of roles 05, 07 and 08 (data quality, audited numbers, cash and unit economics)
2. The owner's existing `cogs-calculator`, `product-cost-manager`, `daily-sales-report`, and competitive-brief skills (reference)
3. Librarian records for Canadian small-business benchmarks (Statistics Canada, BDC); grade A or B, stated plainly

## You own
`agents/11-business-advisor/**`; skills `kpi-dashboard`, `margin-and-pricing`, `competitor-scan`, `exit-readiness-score`; knowledge namespace `strategy`.

## Skills to build
| Skill | Trigger | Inputs | Output | Evidence rule | Highest class |
|---|---|---|---|---|---|
| kpi-dashboard | Monthly | Verified numbers | KPIs with trend and the figure's source | Every figure links to a ledger row | R1 |
| margin-and-pricing | Monthly, on request | Cost and price data | Margin by product and the effect of price changes | Computed by script; assumptions stated | R1 |
| competitor-scan | Quarterly | Public competitor information | What changed and why it matters | Public sources cited with dates | R0 |
| exit-readiness-score | Quarterly | KPIs, documentation, trends | A scored readiness checklist with gaps | The scoring rubric is explicit and versioned; each score cites evidence | R1 |

## Reuse and wrap
`cogs-calculator`, `product-cost-manager`, `daily-sales-report`, competitive-brief skills.

## Interfaces
Consumes: Data Steward, Controller, CFO, Growth Marketer. Produces: monthly and quarterly reviews to the Chief of Staff. Contracts: claim-ledger, agent-envelope.

## Runtime spec
Monthly review; quarterly strategy. Model: Sonnet monthly; Opus quarterly for synthesis.

## Role-specific guardrails
No valuation or sale price advice without data and justification; flag as an estimate with its assumptions. No real figures in the repo.

## Acceptance criteria
1. `DISCOVERY.md` exists with the owner's answers.
2. Every KPI figure links to a verified ledger row.
3. The exit-readiness rubric is explicit and versioned; scoring a synthetic fixture reproduces by script.
4. Competitor findings carry dated public sources.
5. Margin and pricing math matches hand computation on fixtures.
6. Outputs validate against the contracts.

## Out of scope
Setting a sale price, legal or tax structuring advice.

## Questions for the owner
Gather them in discovery.
