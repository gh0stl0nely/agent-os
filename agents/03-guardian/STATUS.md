# Status: 03 Guardian

- **State:** review round 3 done; the three fixes and four checklist wordings from the second review of PR #2 are in the same pull request (builder stops here, does not merge)
- **Branch:** `build/03-guardian`
- **Last updated:** 2026-10-08 America/Toronto

## Done
- PLAN.md, 10 validated knowledge records in `knowledge/security/` (K-sec-0009 and 0010 added in round 2).
- Five skills with scripts, fixtures and evals: `risk-classify`, `secrets-hygiene`, `preflight-brief`, `rollback-plan`, `skill-vetting`.
- Proposed hooks (`hooks/`): wrapper and shell-option unwrapping, `gh -R`/`api` method parsing, branch tracking, default deny for forms it cannot read, owner-only unlock, crash exits 2; **round 3:** no file of the agent's may be published through `gh` unless it is a scanner-clean file in the repo or `/tmp`, any program given a credential path is blocked (not a list of readers), pushes only to a configured remote, `git apply`/`git am`/`patch` are read for the files inside the patch, process substitution blocked; 645 tests (all 25 reviewer shapes H01-H25 included). README states they are a guardrail, not a security boundary, and has a **Known limits** section.
- Fail-closed poster design (`poster-state/poster_gate.py`, `post_threads.gate.patch`, wrappers, workflow text, probe workflow), a change request for the maintenance session, and an 80-check simulation of the reviewers' failure paths, **including a deleted, rewound or re-created `poster-state` on a day that already posted** (round 3: pause first, `complete` each posted day, `status`, unpause last; skipping that order posts again, which S15 and S17a show on purpose). **No live poster file was edited.**
- risk-classify redesigned (round 3): a script floor from a broad risky-verb/synonym/euphemism/passive lexicon, the model can only raise the class, compound actions are split and take the highest clause, only a narrow read-only or own-folder form is R0/R1, everything else goes up. 117 checks; all 61 of the reviewer's wordings and 88 of my own are fixtures.
- Owner setup checklist rewritten: do not protect `main` first; secret scanning and push protection are disabled today; rule is PR with 0 approvals, no force pushes or deletions, no bypassing; the self-merge gap and its two mitigations.
- `skill-inventory.md` (risk-classify hash regenerated), `CARD.md`, `QUESTIONS.md`, `EVAL-REPORT.md`, `eval-log.txt`, two change requests.
- All 1176 checks pass (`python3 agents/03-guardian/run_evals.py`): risk-classify 117, secrets-hygiene 56, preflight-brief 74, rollback-plan 60, skill-vetting 124, hooks 645, poster-state 20, poster fail-closed 80.

## Next steps (for others)
1. Review session: re-run the evals; confirm the finding-by-finding table in the PR comment; try wordings in styles not yet covered (QUESTIONS Q10) and shell shapes in `hooks/README.md` "Known limits".
2. Owner: answer `QUESTIONS.md` (Q2 identity option, Q3 poster change), enable secret scanning and push protection (checklist steps 1 and 2), then follow `OWNER-SETUP-CHECKLIST.md` in its order.
3. Maintenance session (R2, after the owner approves): apply `agent-system/change-requests/03-guardian-poster-fail-closed.md`. **Protect `main` only after that has run for a real post.**
4. Owner decision: install the hooks (R2, Preflight Brief), after the poster change.

## Blockers
- None.
- Open: my own 88 wordings are not independent evidence (4 of the first 48 and 10 of the next 40 were below their floor on first run, fixed). Risky vocabulary the lists have never seen lands at R2 with `needs_review`. Real GitHub behaviour of the poster gate and the hooks in a live Claude Code session are not yet observed. The hook bypass classes still open are listed in `hooks/README.md`.
