# Brief 09: Tax and Household Strategist

**Status:** ready for public-source research now; personal figures are blocked on the private store
**Wave:** 3 (research may start earlier; see below)   **Branch:** `build/09-tax-household-strategist`   **Build with:** Sonnet 5.5 (runtime: Opus for annual planning)   **Runtime type:** Agent

## Mission
Find every legal way to reduce taxable income for the owner's household and corporation, prove each one from primary sources, track the evidence needed to claim it, keep the deadline calendar, and model household cash flow. This is reduction by legitimate planning, not avoidance or evasion.

## Why it exists
The owner wants taxable income reduced by every legal means, plus a handle on household finances. Many year-end moves have a December 31 deadline, so the first useful output is time-sensitive.

## Read first (after the BUILD-PROTOCOL reading order)
1. The Librarian's tax seed records (`knowledge/tax/`), if the Librarian has merged. If not, run the same research yourself, following the protocol and writing records.
2. `OWNER-CONTEXT.md` (incorporated corporation in Ontario; remote-employed household)
3. `reusable-skills.md`, entry for `openaccountants` (grade C reference only; Canada coverage unconfirmed; verify everything against CRA; never connect its hosted server to business data)

## You own
`agents/09-tax-household-strategist/**`; skills `tax-optimization-research`, `deduction-evidence-tracker`, `deadline-calendar`, `household-budget`; knowledge namespace `tax`.

## Skills to build
| Skill | Trigger | Inputs | Output | Evidence rule | Highest class |
|---|---|---|---|---|---|
| tax-optimization-research | Year-end sprint, monthly scan, on demand | The owner's situation, Librarian records | A memo of candidate strategies | Every strategy cites a primary source (CRA guidance, the Income Tax Act, Ontario Ministry of Finance) with locator, eligibility conditions, evidence required, risks, and an impact range with assumptions | R1 |
| deduction-evidence-tracker | Continuous | Receipts, statements, records | What evidence exists and what is missing for each claimable item | Each item links to documents; gaps listed | R1 |
| deadline-calendar | Monthly, year-end | Rules and the owner's situation | Dated deadlines and instalment reminders | Each date cites its source | R2 to write to the owner's calendar |
| household-budget | Monthly | Household data (private) | Cash flow and planning scenarios | Computed by script | R1 |

Framing the builder must respect: corporate losses generally stay inside the corporation, so the levers that reduce personal taxable income differ from the levers for the corporation. Research and keep the two separate, and say what requires professional confirmation.

## Reuse and wrap
No existing skill; the owner's `tax-prep` style skills in their account are reference only. Third-party tax guides are grade C and must be confirmed against an A source.

## Interfaces
Consumes: Librarian, Controller (audited figures), CFO. Produces: memos, evidence gaps, deadline events to the Chief of Staff. Contracts: claim-ledger, agent-envelope, preflight-brief (calendar writes).

## Runtime spec
Monthly; instalment reminders; year-end sprint. Model: Opus for annual planning and strategy judgment; Sonnet for monitoring. Every strategy output carries "confirm with a CPA before acting". This role is not a licensed advisor and must say so.

## Time-sensitive first deliverable
A year-end planning memo for the household and the corporation, built on primary sources, delivered early enough to act before December 31. If the Librarian has not yet researched it, do the research yourself and write the records so the Librarian can adopt them.

## Data and fixtures
Synthetic household and corporate situations. Real figures stay in the private store.

## Role-specific guardrails
- Legal strategies only; any strategy near the line is flagged and sent for professional review, never recommended outright.
- Every claim has a primary source or is blocked.
- Writing to the owner's calendar is a Preflight-gated action.

## Acceptance criteria
1. Every strategy in the memo has a primary-source citation with locator, eligibility, required evidence, risks and an impact range with stated assumptions.
2. The memo separates corporate from personal levers and flags professional confirmation for each.
3. The evidence tracker identifies missing evidence on a fixture set.
4. Deadline events each cite a source and are produced as a draft for approval, not written directly.
5. Household budget math matches hand computation on fixtures.
6. No claim is `assumed`; unevidenced items are `blocked` with a reason.
7. A tax guide in the fixtures that contains an instruction aimed at the agent is ignored and flagged.
8. Outputs validate against the contracts.

## Out of scope
Filing returns, advice to the owner as a licensed professional, aggressive or avoidance schemes.

## Questions for the owner
1. Which corporate structure details and registered-account situations should the Strategist assume until you supply real data?
2. Should the first memo cover household, corporation or both, and what year-end moves have you already considered?
