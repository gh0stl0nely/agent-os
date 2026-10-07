# Status: 03 Guardian

- **State:** in progress (planning done, building)
- **Branch:** `build/03-guardian` (local only so far; see Blockers)
- **Last updated:** 2026-10-07 14:35 America/Toronto

## Done
- Read the protocol, the brief, all contracts, roster rows, architecture, knowledge base and reusable-skills.
- Created the branch and this file.

## Next steps
1. Commit `PLAN.md`.
2. Research (OWASP LLM Top 10, OWASP Agentic Skills Top 10, GitHub secret scanning, push protection, branch protection and rulesets for a public repo, Claude Code hooks) and save knowledge records under `knowledge/security/`.
3. Build the five skills in this order: `risk-classify`, `secrets-hygiene`, `preflight-brief`, `rollback-plan`, `skill-vetting`.
4. Build the hooks proposals under `agents/03-guardian/hooks/` with tests.
5. Write the owner setup checklist (including the daily-poster state-commit path) and the skill inventory.
6. Run all evals, write `EVAL-REPORT.md`, `CARD.md`, `QUESTIONS.md`.
7. Self-check against the acceptance criteria, then open the pull request to `main` and stop.

## Blockers
- **Push access to `gh0stl0nely/business-assets` was denied** when the session asked for it (the repo is attached read-only). Work continues in a local clone at `/home/claude/gh0stl0nely/business-assets`. The branch cannot be pushed and the pull request cannot be opened until the owner grants push access or pushes the branch themselves.
