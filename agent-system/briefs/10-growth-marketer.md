# Brief 10: Growth Marketer

**Status:** ready, but **discovery first**: the owner deferred the detail, so interview them before building
**Wave:** 4   **Branch:** `build/10-growth-marketer`   **Build with:** Sonnet 5.5   **Runtime type:** Workflow

## Mission
Drive traffic to the shop and increase sales through content: ideas, calendar, copy, and performance review, using online tools instead of manual work. Anything that goes public is flagged first.

## Why it exists
The owner spends time deciding what to post and posting it. They want tools to do it, with the owner approving rather than creating.

## Discovery first
Before building, interview the owner (use the question tool). Cover: the shop's customers and location context, which platforms matter, what has and has not worked with numbers if any, brand voice and what must never be said, how much approval they want per post, and which tools they will pay for. Write the answers into `agents/10-growth-marketer/DISCOVERY.md`. Only then plan and build. Deferred by the owner: this was explicitly left for later, so do not assume.

## Read first (after the BUILD-PROTOCOL reading order)
1. `bloor-assets/README.md` and `scripts/post_threads.py` (the live poster: a queue, a manifest with expiry, a pause switch, the token held as a CI secret, a guard against posting twice in a day)
2. The owner's existing marketing and social skills and connectors (reference)
3. `contracts/autonomy-matrix.md` (a public post is class R4)

## You own
`agents/10-growth-marketer/**`; skills `content-ideation`, `calendar-build`, `copywriting`, `performance-review`; knowledge namespace `marketing`. The existing poster files are read-only to you; propose changes to them as a change request.

## Skills to build
| Skill | Trigger | Inputs | Output | Evidence rule | Highest class |
|---|---|---|---|---|---|
| content-ideation | Weekly | Sales trends, past results, seasonality | Ranked ideas with the reason for each | Reasons cite data from the ledger or from performance history | R1 |
| calendar-build | Weekly | Approved ideas | A posting calendar | No claims about the shop's offers without a source | R1 |
| copywriting | Per post | Idea, brand voice | Drafts | Offers, prices and hours match the source of truth | R1 |
| performance-review | Weekly | Post results | What worked and why, with numbers | Numbers from the platform data by script | R0 |

Publishing is the existing poster's job; the Guardian reviews anything new before it is queued.

## Reuse and wrap
The live Threads poster as the executor. The owner's marketing and content skills and the social-scheduler and design connectors where they exist.

## Interfaces
Consumes: Business Advisor, Data Steward (sales), Guardian. Produces: calendar and drafts to the Chief of Staff for approval. Contracts: agent-envelope, preflight-brief.

## Runtime spec
Weekly planning; daily posting through the existing poster after approval. Model: Sonnet.

## Role-specific guardrails
Every public post is class R4: flagged early, approved before it is queued. Image and video assets must respect the manifest expiry. Never state an offer, price or hour that is not in the source of truth.

## Acceptance criteria
1. `DISCOVERY.md` exists with the owner's answers.
2. Ideas cite the data behind them; an idea without a reason is dropped.
3. The calendar and drafts pass the Verifier, and copy that states a price, hour or offer matches the source of truth (tested).
4. No post can be queued without an approved Preflight Brief (tested).
5. Asset expiry is respected in tests.
6. Performance review numbers come from a script.
7. Outputs validate against the contracts.

## Out of scope
Paid advertising, changing the live poster's code, new platforms the owner did not ask for.

## Questions for the owner
Gather them in discovery.
