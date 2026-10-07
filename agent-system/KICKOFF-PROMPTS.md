# Kickoff prompts

Copy one prompt into a fresh Claude Code session. Every prompt names the repository and tells the session to attach and clone it first, because a new session does not have the repo unless it was created on it. Once the repo is cloned, `CLAUDE.md` loads automatically, so the shared context is identical for every role; the prompt only says which role to build.

Start one session per role. Never reuse a builder's session as its reviewer. Recommended ceiling: two build sessions at once (Claude Pro usage is shared and capped). Order and reasons are in [BUILD-PLAN.md](BUILD-PLAN.md).

## Step 0: give the session the repo

Best: when you create the session, pick the repository `gh0stl0nely/business-assets` so it starts already cloned.

If the session starts without it (working directory is not a git repo, no `agent-system/` folder), the prompt below makes it attach the repo with push access and clone it. Approve the permission prompt when it appears. If the attach is denied, the session must stop and tell you rather than guess. Then check that GitHub is connected for your account under Settings, Connectors, and that it has access to this repository.

A session without the repo cannot read `CLAUDE.md` or its brief, so it cannot do the work.

## Builder prompts

Each block is complete and self-contained. Only the role line changes.

**01 Chief of Staff**
```
Repository: gh0stl0nely/business-assets (public GitHub repo, branch main).
Step 1: if your working directory is not a clone of that repo, attach it with push access and clone it. If that is denied, stop and tell me; do not guess.
Step 2: you are the builder session for role 01, Chief of Staff. Follow agent-system/BUILD-PROTOCOL.md exactly, starting with agent-system/briefs/01-chief-of-staff.md. Build only what your brief assigns. Open a pull request and stop; do not merge.
```

**02 Verifier**
```
Repository: gh0stl0nely/business-assets (public GitHub repo, branch main).
Step 1: if your working directory is not a clone of that repo, attach it with push access and clone it. If that is denied, stop and tell me; do not guess.
Step 2: you are the builder session for role 02, Verifier. Follow agent-system/BUILD-PROTOCOL.md exactly, starting with agent-system/briefs/02-verifier.md. Build only what your brief assigns. Open a pull request and stop; do not merge.
```

**03 Guardian**
```
Repository: gh0stl0nely/business-assets (public GitHub repo, branch main).
Step 1: if your working directory is not a clone of that repo, attach it with push access and clone it. If that is denied, stop and tell me; do not guess.
Step 2: you are the builder session for role 03, Guardian. Follow agent-system/BUILD-PROTOCOL.md exactly, starting with agent-system/briefs/03-guardian.md. Build only what your brief assigns. Open a pull request and stop; do not merge.
```

**04 Librarian**
```
Repository: gh0stl0nely/business-assets (public GitHub repo, branch main).
Step 1: if your working directory is not a clone of that repo, attach it with push access and clone it. If that is denied, stop and tell me; do not guess.
Step 2: you are the builder session for role 04, Librarian. Follow agent-system/BUILD-PROTOCOL.md exactly, starting with agent-system/briefs/04-librarian.md. Build only what your brief assigns. Open a pull request and stop; do not merge.
```

**05 Data Steward**
```
Repository: gh0stl0nely/business-assets (public GitHub repo, branch main).
Step 1: if your working directory is not a clone of that repo, attach it with push access and clone it. If that is denied, stop and tell me; do not guess.
Step 2: you are the builder session for role 05, Data Steward. Follow agent-system/BUILD-PROTOCOL.md exactly, starting with agent-system/briefs/05-data-steward.md. Build only what your brief assigns. Open a pull request and stop; do not merge.
```

**06 Operations Manager**
```
Repository: gh0stl0nely/business-assets (public GitHub repo, branch main).
Step 1: if your working directory is not a clone of that repo, attach it with push access and clone it. If that is denied, stop and tell me; do not guess.
Step 2: you are the builder session for role 06, Operations Manager. Follow agent-system/BUILD-PROTOCOL.md exactly, starting with agent-system/briefs/06-operations-manager.md. Build only what your brief assigns. Open a pull request and stop; do not merge.
```

**07 Controller**
```
Repository: gh0stl0nely/business-assets (public GitHub repo, branch main).
Step 1: if your working directory is not a clone of that repo, attach it with push access and clone it. If that is denied, stop and tell me; do not guess.
Step 2: you are the builder session for role 07, Controller. Follow agent-system/BUILD-PROTOCOL.md exactly, starting with agent-system/briefs/07-controller.md. Build only what your brief assigns. Open a pull request and stop; do not merge.
```

**08 CFO**
```
Repository: gh0stl0nely/business-assets (public GitHub repo, branch main).
Step 1: if your working directory is not a clone of that repo, attach it with push access and clone it. If that is denied, stop and tell me; do not guess.
Step 2: you are the builder session for role 08, CFO. Follow agent-system/BUILD-PROTOCOL.md exactly, starting with agent-system/briefs/08-cfo.md. Build only what your brief assigns. Open a pull request and stop; do not merge.
```

**09 Tax and Household Strategist**
```
Repository: gh0stl0nely/business-assets (public GitHub repo, branch main).
Step 1: if your working directory is not a clone of that repo, attach it with push access and clone it. If that is denied, stop and tell me; do not guess.
Step 2: you are the builder session for role 09, Tax and Household Strategist. Follow agent-system/BUILD-PROTOCOL.md exactly, starting with agent-system/briefs/09-tax-household-strategist.md. Build only what your brief assigns. Open a pull request and stop; do not merge.
```

**10 Growth Marketer**
```
Repository: gh0stl0nely/business-assets (public GitHub repo, branch main).
Step 1: if your working directory is not a clone of that repo, attach it with push access and clone it. If that is denied, stop and tell me; do not guess.
Step 2: you are the builder session for role 10, Growth Marketer. Follow agent-system/BUILD-PROTOCOL.md exactly, starting with agent-system/briefs/10-growth-marketer.md. Build only what your brief assigns. Open a pull request and stop; do not merge.
```

**11 Business Advisor**
```
Repository: gh0stl0nely/business-assets (public GitHub repo, branch main).
Step 1: if your working directory is not a clone of that repo, attach it with push access and clone it. If that is denied, stop and tell me; do not guess.
Step 2: you are the builder session for role 11, Business Advisor. Follow agent-system/BUILD-PROTOCOL.md exactly, starting with agent-system/briefs/11-business-advisor.md. Build only what your brief assigns. Open a pull request and stop; do not merge.
```

**12 AI Learning Coach**
```
Repository: gh0stl0nely/business-assets (public GitHub repo, branch main).
Step 1: if your working directory is not a clone of that repo, attach it with push access and clone it. If that is denied, stop and tell me; do not guess.
Step 2: you are the builder session for role 12, AI Learning Coach. Follow agent-system/BUILD-PROTOCOL.md exactly, starting with agent-system/briefs/12-ai-learning-coach.md. Build only what your brief assigns. Open a pull request and stop; do not merge.
```

**13 Venture Architect**
```
Repository: gh0stl0nely/business-assets (public GitHub repo, branch main).
Step 1: if your working directory is not a clone of that repo, attach it with push access and clone it. If that is denied, stop and tell me; do not guess.
Step 2: you are the builder session for role 13, Venture Architect. Follow agent-system/BUILD-PROTOCOL.md exactly, starting with agent-system/briefs/13-venture-architect.md. Build only what your brief assigns. Open a pull request and stop; do not merge.
```

## Resume prompt (a builder ran out of usage or was interrupted)

```
Repository: gh0stl0nely/business-assets (public GitHub repo, branch main).
Step 1: if your working directory is not a clone of that repo, attach it with push access and clone it. If that is denied, stop and tell me; do not guess.
Step 2: you are resuming the builder session for role NN, <Role>. Check out branch build/NN-<role-slug> if it exists. Read agents/NN-<role>/STATUS.md and PLAN.md first and continue from "Next steps". Follow agent-system/BUILD-PROTOCOL.md. Open a pull request when done and stop; do not merge.
```

## Review prompt (a fresh session, one per pull request)

```
Repository: gh0stl0nely/business-assets (public GitHub repo, branch main).
Step 1: if your working directory is not a clone of that repo, attach it and clone it. If that is denied, stop and tell me; do not guess.
Step 2: you are the review session for the pull request on branch build/NN-<role-slug>. You did not build it. Follow the "Review session" section of agent-system/BUILD-PROTOCOL.md against agent-system/briefs/NN-<role>.md. Re-run the evals yourself, test one case the builder did not, and post your verdict as a PR comment. Do not edit the builder's files and do not merge.
```

## If a builder needs real data

Do not paste it into chat or commit it. Attach the file to that session, or attach the owner's private repo to it. The session must keep real data out of this repo.
