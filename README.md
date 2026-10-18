# agent-os

Role agents for Isabella's Donuts and the owner's household. Each agent mirrors a human role, works from evidence, and checks its claims with an independent Verifier before anything reaches the owner.

## Status
- **Active:** `verifier` (5 skills, 80 eval cases, golden set of 39 seeded errors).
- **Next:** `operations-manager`, the nightly supplier order.
- **Live outside the agent system:** the daily Threads poster (`bloor-assets/`, `scripts/post_threads.py`).

The full plan is in [ROLES.md](ROLES.md). How it fits together: [ARCHITECTURE.md](ARCHITECTURE.md).

## Layout

| Path | What it holds |
|---|---|
| `CLAUDE.md` | Rules every agent follows (kept short: it loads on every run) |
| `ROLES.md` | Every planned role, its status and build order |
| `ARCHITECTURE.md` | Diagrams: how runs flow, call depth, where every file goes, a role's lifecycle |
| `BUILD-PROTOCOL.md` | How to build a role, and the role definition template |
| `.claude/agents/<id>.md` | One definition per built role: instructions, tools, skills, connectors, who it may call |
| `.claude/skills/` | Skills, each with scripts, synthetic fixtures and evals |
| `agents/<id>/` | Role-only material: rubrics, examples, golden cases |
| `shared/` | Owner context, autonomy matrix, Preflight Brief template, knowledge rules, external resources |
| `contracts/` | JSON schemas for claims, knowledge records and handoffs, plus `validate.py` and `check_roles.py` |
| `knowledge/` | Sourced, dated knowledge records agents check before researching |

## How agents work together
- **Direct call:** a role invokes another role (for example the Verifier) as a subagent in the same run. Each definition lists who it may call in `can_call`.
- **Handoff:** longer work goes to a GitHub issue labelled `role:<id>`, picked up on that role's next run.

## Checks (also run in CI on every pull request)

```
pip install -r requirements.txt
python3 contracts/check_roles.py
python3 contracts/validate.py
python3 agents/verifier/run_evals.py
python3 .claude/skills/golden-set-calibration/scripts/run_golden.py
```

## Never committed here
Secrets, tokens, passwords, financial statements, bank or card data, tax filings, income figures, debt terms, supplier prices or order history, staff personal data, health or family data. Those belong in the private store.
