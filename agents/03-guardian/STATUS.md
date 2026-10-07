# Status: 03 Guardian

- **State:** built; self-check done; pull request open for review (builder stops here, does not merge)
- **Branch:** `build/03-guardian`
- **Last updated:** 2026-10-07 America/Toronto

## Done
- PLAN.md, 8 validated knowledge records in `knowledge/security/`.
- Five skills with scripts, fixtures and evals: `risk-classify`, `secrets-hygiene`, `preflight-brief`, `rollback-plan`, `skill-vetting`.
- Proposed hooks (`hooks/`) with policy, settings example and 219 tests.
- Owner setup checklist, with the tested poster-state flow (`poster-state/`) that keeps the daily state save working under a protected `main`.
- `skill-inventory.md`, `CARD.md`, `QUESTIONS.md`, `EVAL-REPORT.md`, `eval-log.txt`, one change request (`agent-system/change-requests/03-guardian-preflight-na-convention.md`).
- All 605 checks pass (`python3 agents/03-guardian/run_evals.py`).

## Next steps (for others)
1. Review session: re-run the evals, try a command shape the hook parser may misread, read the lines flagged in `skill-inventory.md`.
2. Owner: answer `QUESTIONS.md`, then follow `OWNER-SETUP-CHECKLIST.md` in its order (poster change before protecting `main`).
3. Owner decision: install the hooks (R2, Preflight Brief).

## Blockers
- None. (Push access was denied once and then granted after the owner confirmed the repo.)
