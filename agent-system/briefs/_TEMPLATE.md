# Brief NN: <Role>

**Status:** ready | blocked on <what> (build what is unblocked)
**Wave:** N   **Branch:** `build/NN-<role-slug>`   **Build with:** Sonnet 5.5 unless stated   **Runtime type:** Orchestrator | Gate | Workflow | Agent

## Mission
Two or three sentences: what this role does and for whom.

## Why it exists
The owner pain it removes, in the owner's terms (see `OWNER-CONTEXT.md`).

## Read first (after the BUILD-PROTOCOL reading order)
Role-specific files, sources and existing skills, in order.

## You own
Paths you may write: `agents/NN-<role>/**`, listed skills, listed knowledge namespaces. Everything else is read-only.

## Skills to build
| Skill | Trigger | Inputs | Output | Evidence rule | Highest action class |
|---|---|---|---|---|---|

## Reuse and wrap
Existing skills to wrap, third-party candidates (adopt, adapt or reject; vet per `reusable-skills.md`).

## Interfaces
Consumes (from which roles), produces (to which roles), contracts used.

## Runtime spec
Schedule, model tier and why, notification behavior, deadline logic.

## Data and fixtures
Synthetic fixtures to create. Real data needed (owner supplies via private store or attachment, never committed).

## Role-specific guardrails
What this role must never do, and which steps need a Preflight Brief.

## Acceptance criteria
Numbered and testable.

## Out of scope
What to leave alone.

## Questions for the owner
Put these in `agents/NN-<role>/QUESTIONS.md` at the start.
