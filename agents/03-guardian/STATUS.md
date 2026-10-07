# Status: 03 Guardian

- **State:** review round 2 done; all findings of the review of PR #2 addressed in the same pull request (builder stops here, does not merge)
- **Branch:** `build/03-guardian`
- **Last updated:** 2026-10-07 America/Toronto

## Done
- PLAN.md, 10 validated knowledge records in `knowledge/security/` (K-sec-0009 and 0010 added in round 2).
- Five skills with scripts, fixtures and evals: `risk-classify`, `secrets-hygiene`, `preflight-brief`, `rollback-plan`, `skill-vetting`.
- Proposed hooks (`hooks/`): wrapper and shell-option unwrapping, `gh -R`/`api` method parsing, branch tracking, default deny for forms it cannot read, owner-only unlock, crash exits 2; 387 tests. README states they are a guardrail, not a security boundary.
- Fail-closed poster design (`poster-state/poster_gate.py`, `post_threads.gate.patch`, wrappers, workflow text, probe workflow), a change request for the maintenance session, and a 55-check simulation of the reviewer's three failure paths plus ten more. **No live poster file was edited.**
- Owner setup checklist rewritten: do not protect `main` first; secret scanning and push protection are disabled today; rule is PR with 0 approvals, no force pushes or deletions, no bypassing; the self-merge gap and its two mitigations.
- `skill-inventory.md` (risk-classify hash regenerated), `CARD.md`, `QUESTIONS.md`, `EVAL-REPORT.md`, `eval-log.txt`, two change requests.
- All 857 checks pass (`python3 agents/03-guardian/run_evals.py`).

## Next steps (for others)
1. Review session: re-run the evals; confirm the finding-by-finding table in the PR comment; supply the 14 held-out wordings missing from the first review (QUESTIONS Q9).
2. Owner: answer `QUESTIONS.md` (Q2 identity option, Q3 poster change), enable secret scanning and push protection (checklist steps 1 and 2), then follow `OWNER-SETUP-CHECKLIST.md` in its order.
3. Maintenance session (R2, after the owner approves): apply `agent-system/change-requests/03-guardian-poster-fail-closed.md`. **Protect `main` only after that has run for a real post.**
4. Owner decision: install the hooks (R2, Preflight Brief), after the poster change.

## Blockers
- None.
- Open: the reviewer's 14 other held-out wordings were not in the review comment (stand-ins are labelled). Real GitHub behaviour of the poster gate and the hooks in a live Claude Code session are not yet observed.
