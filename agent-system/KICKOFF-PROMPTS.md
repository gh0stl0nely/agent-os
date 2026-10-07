# Kickoff prompts

Copy one prompt into a fresh Claude Code session on this repo. The session loads `CLAUDE.md` automatically, so the shared context is identical for every role; the prompt only says which role to build and where to start.

Start one session per role. Never reuse a builder's session as its reviewer. Recommended ceiling: two build sessions at once (Claude Pro usage is shared and capped). Order and reasons are in [BUILD-PLAN.md](BUILD-PLAN.md).

## Builder prompts

Each prompt is the same shape. The role and brief file are the only differences.

| # | Role | Prompt to paste |
|---|---|---|
| 01 | Chief of Staff | `You are the builder session for role 01, Chief of Staff, in this repo. Follow agent-system/BUILD-PROTOCOL.md exactly, starting with agent-system/briefs/01-chief-of-staff.md. Build only what your brief assigns. Open a pull request and stop; do not merge.` |
| 02 | Verifier | `You are the builder session for role 02, Verifier, in this repo. Follow agent-system/BUILD-PROTOCOL.md exactly, starting with agent-system/briefs/02-verifier.md. Build only what your brief assigns. Open a pull request and stop; do not merge.` |
| 03 | Guardian | `You are the builder session for role 03, Guardian, in this repo. Follow agent-system/BUILD-PROTOCOL.md exactly, starting with agent-system/briefs/03-guardian.md. Build only what your brief assigns. Open a pull request and stop; do not merge.` |
| 04 | Librarian | `You are the builder session for role 04, Librarian, in this repo. Follow agent-system/BUILD-PROTOCOL.md exactly, starting with agent-system/briefs/04-librarian.md. Build only what your brief assigns. Open a pull request and stop; do not merge.` |
| 05 | Data Steward | `You are the builder session for role 05, Data Steward, in this repo. Follow agent-system/BUILD-PROTOCOL.md exactly, starting with agent-system/briefs/05-data-steward.md. Build only what your brief assigns. Open a pull request and stop; do not merge.` |
| 06 | Operations Manager | `You are the builder session for role 06, Operations Manager, in this repo. Follow agent-system/BUILD-PROTOCOL.md exactly, starting with agent-system/briefs/06-operations-manager.md. Build only what your brief assigns. Open a pull request and stop; do not merge.` |
| 07 | Controller | `You are the builder session for role 07, Controller, in this repo. Follow agent-system/BUILD-PROTOCOL.md exactly, starting with agent-system/briefs/07-controller.md. Build only what your brief assigns. Open a pull request and stop; do not merge.` |
| 08 | CFO | `You are the builder session for role 08, CFO, in this repo. Follow agent-system/BUILD-PROTOCOL.md exactly, starting with agent-system/briefs/08-cfo.md. Build only what your brief assigns. Open a pull request and stop; do not merge.` |
| 09 | Tax and Household Strategist | `You are the builder session for role 09, Tax and Household Strategist, in this repo. Follow agent-system/BUILD-PROTOCOL.md exactly, starting with agent-system/briefs/09-tax-household-strategist.md. Build only what your brief assigns. Open a pull request and stop; do not merge.` |
| 10 | Growth Marketer | `You are the builder session for role 10, Growth Marketer, in this repo. Follow agent-system/BUILD-PROTOCOL.md exactly, starting with agent-system/briefs/10-growth-marketer.md. Build only what your brief assigns. Open a pull request and stop; do not merge.` |
| 11 | Business Advisor | `You are the builder session for role 11, Business Advisor, in this repo. Follow agent-system/BUILD-PROTOCOL.md exactly, starting with agent-system/briefs/11-business-advisor.md. Build only what your brief assigns. Open a pull request and stop; do not merge.` |
| 12 | AI Learning Coach | `You are the builder session for role 12, AI Learning Coach, in this repo. Follow agent-system/BUILD-PROTOCOL.md exactly, starting with agent-system/briefs/12-ai-learning-coach.md. Build only what your brief assigns. Open a pull request and stop; do not merge.` |
| 13 | Venture Architect | `You are the builder session for role 13, Venture Architect, in this repo. Follow agent-system/BUILD-PROTOCOL.md exactly, starting with agent-system/briefs/13-venture-architect.md. Build only what your brief assigns. Open a pull request and stop; do not merge.` |

## Resume prompt (a builder ran out of usage or was interrupted)

```
You are resuming the builder session for role NN, <Role>, in this repo. Read agents/NN-<role>/STATUS.md and PLAN.md first and continue from "Next steps". Follow agent-system/BUILD-PROTOCOL.md. Open a pull request when done and stop; do not merge.
```

## Review prompt (a fresh session, one per pull request)

```
You are the review session for the pull request on branch build/NN-<role-slug>. You did not build it. Follow the "Review session" section of agent-system/BUILD-PROTOCOL.md against agent-system/briefs/NN-<role>.md. Re-run the evals yourself, test one case the builder did not, and post your verdict as a PR comment. Do not edit the builder's files and do not merge.
```

## If a builder needs real data

Do not paste it into chat or commit it. Attach the file to that session, or attach the owner's private repo to it. The session must keep real data out of this repo.
