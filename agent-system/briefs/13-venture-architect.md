# Brief 13: Venture Architect

**Status:** ready, but **discovery first**; its strongest outputs depend on proof produced by the other roles
**Wave:** 4   **Branch:** `build/13-venture-architect`   **Build with:** Sonnet 5.5 (runtime: Opus for strategy sessions)   **Runtime type:** Agent

## Mission
Map where money flows in industries the owner could serve, find where their tools and consulting would sit in that flow, design offers, and turn proven internal results into case studies. The aim is a venture that sits in the flow of money the way payment networks and banks do.

## Why it exists
The owner's 1 to 2 year goal is remote AI agent consulting and AI tools that solve real business problems, positioned where money flows. Any offer to other businesses needs proof from the system working on their own life and shop first; the sale price of the shop and any pricing for clients come later and need data.

## Discovery first
Interview the owner: which industries they know or want, which skills they most want to sell, constraints on time and capital, how they want to be paid, and what "proof" a client would need to see. Write answers to `agents/13-venture-architect/DISCOVERY.md`.

## Read first (after the BUILD-PROTOCOL reading order)
1. `OWNER-CONTEXT.md` goals; `roster.md` success metrics (the proof the system must produce)
2. The portfolio and eval reports from roles 12, 06 and 07 once they exist
3. Librarian records: how payment and money flows work in Canada (Payments Canada, Bank of Canada, BIS, vendor documentation; grade A) and in the owner's candidate industries

## You own
`agents/13-venture-architect/**`; skills `money-flow-mapping`, `opportunity-scoring`, `offer-design`, `case-study-builder`, `pilot-design`; knowledge namespace `ventures`.

## Skills to build
| Skill | Trigger | Inputs | Output | Evidence rule | Highest class |
|---|---|---|---|---|---|
| money-flow-mapping | Per target industry | Public sources | A map of who pays whom, where fees and friction sit, and where a tool could fit | Each flow cites a primary source | R0 |
| opportunity-scoring | After mapping | Maps, the owner's strengths | A ranked list with an explicit, versioned rubric | Scores cite the evidence | R1 |
| offer-design | For a chosen opportunity | Opportunity, constraints | An offer: scope, outcome, how success is measured, what proof is needed | Claims about outcomes cite internal proof or are labelled hypotheses | R1 |
| case-study-builder | When a role has measured results | Verified metrics from the ledger | A case study | Every number links to a ledger row; no private data | R1 (publishing is R4) |
| pilot-design | For a first client | Offer | A low-risk pilot plan with success criteria | Criteria are measurable | R1 |

## Reuse and wrap
Competitive-brief and research skills; the Librarian for sources.

## Interfaces
Consumes: Librarian, Business Advisor, AI Learning Coach, verified metrics from the ledger. Produces: strategy memos and case studies to the Chief of Staff. Contracts: claim-ledger, agent-envelope.

## Runtime spec
Biweekly scan; project-based sessions. Model: Sonnet for research; Opus for strategy sessions.

## Role-specific guardrails
- Never claim a result the ledger does not show. A hypothesis is labelled as one.
- Publishing a case study or offer is class R4: flagged early.
- Client or shop data is never included without the owner's explicit approval and removal of identifying detail.

## Acceptance criteria
1. `DISCOVERY.md` exists.
2. Each money-flow map cites a primary source for every flow.
3. The opportunity rubric is explicit and versioned; scoring a fixture reproduces by script.
4. Every case-study number links to a verified ledger row; a number with none is rejected (tested).
5. Offers separate proven claims from hypotheses.
6. Outputs validate against the contracts.

## Out of scope
Setting prices before there is data, contacting prospects.

## Questions for the owner
Gather them in discovery.
