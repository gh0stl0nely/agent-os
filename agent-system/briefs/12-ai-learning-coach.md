# Brief 12: AI Learning Coach

**Status:** ready, but **discovery first**
**Wave:** 4   **Branch:** `build/12-ai-learning-coach`   **Build with:** Sonnet 5.5   **Runtime type:** Agent

## Mission
Coach the owner toward being a top-tier expert at using AI agents to create business impact: a curriculum, a weekly digest of what matters, summaries of papers and documentation, build challenges, and a portfolio of proof.

## Why it exists
The owner's long-term goal is to be an AI product engineer who controls agents around real business purposes and adds measurable value. Building this system is itself the best training, so the coach ties learning to the system's real builds and results.

## Discovery first
Interview the owner: current skill level and gaps, how many hours a week they can spend, preferred formats, what they want to be able to demonstrate in a year. Write answers to `agents/12-ai-learning-coach/DISCOVERY.md`.

## Read first (after the BUILD-PROTOCOL reading order)
1. Anthropic's engineering and documentation pages on agents, skills, evals and context engineering (primary sources; grade A)
2. The system's own contracts and protocols, since they are the first curriculum
3. `OWNER-CONTEXT.md` goals

## You own
`agents/12-ai-learning-coach/**`; skills `curriculum-builder`, `weekly-ai-digest`, `paper-and-doc-summary`, `build-challenge`, `portfolio-tracker`; knowledge namespace `ai-learning`.

## Skills to build
| Skill | Trigger | Inputs | Output | Evidence rule | Highest class |
|---|---|---|---|---|---|
| curriculum-builder | Monthly | Skill gaps, goals | A learning plan tied to real builds | Each item cites why and a source | R1 |
| weekly-ai-digest | Weekly | Primary sources | A short digest ranked by relevance to the owner's goals | Each item links a primary source with its date; no copied passages | R0 |
| paper-and-doc-summary | On request | A paper or document | A summary in original words with what to try | The source and locator are cited | R0 |
| build-challenge | Weekly | The curriculum | A concrete exercise with acceptance criteria | Criteria are testable | R1 |
| portfolio-tracker | Monthly | Build results, eval reports | A record of proven work (no private data) | Each entry links to a real eval result | R1 |

## Reuse and wrap
`skill-creator` and the Librarian's research pattern.

## Interfaces
Consumes: Librarian. Produces: digests and plans to the Chief of Staff. Feeds the Venture Architect with proven capabilities.

## Runtime spec
Weekly digest; monthly project. Model: Sonnet; Opus only for deep reading the owner requests.

## Role-specific guardrails
Summaries paraphrase and cite; never reproduce passages. Digest length must fit the owner's time budget.

## Acceptance criteria
1. `DISCOVERY.md` exists.
2. The digest links a dated primary source for every item and fits the stated time.
3. Summaries contain no copied passages (checked by script on fixtures).
4. Every build challenge has testable acceptance criteria.
5. Portfolio entries link to real eval reports and contain no private data.
6. Outputs validate against the contracts.

## Out of scope
Doing the owner's work for them; paid courses.

## Questions for the owner
Gather them in discovery.
