# Build protocol

How to turn a planned role in `ROLES.md` into a working agent. One session builds one role.

## Steps

1. **Pick the role.** Take the next `planned` role in `ROLES.md`, set its status to `building`, and create the branch `role/<id>`.
2. **Write the definition** at `.claude/agents/<id>.md` from the template below. Fill in every section; delete nothing.
3. **Build its skills** in `.claude/skills/<skill>/`: `SKILL.md`, `scripts/` for anything deterministic (every reported number comes from a script), `fixtures/` with synthetic data only, `evals/cases.json`. Claude Code only finds skills in `.claude/skills/`, so they live there, and the definition lists the ones the role uses.
4. **Put role-only material** (rubrics, examples, references, golden cases) in `agents/<id>/`.
5. **Write evals** for each skill: at least a normal case, a missing-data case, a seeded-error case the skill must catch or refuse, and an adversarial case whose input contains an instruction the skill must ignore. `python3 agents/verifier/run_evals.py` runs every skill's evals.
6. **Third-party skills and repos:** read every file first, pin to a commit, and record source, license and verdict in `shared/external-resources.md` and the role's entry in `ROLES.md`.
7. **Open a pull request.** The description holds the build notes: what was built, decisions made, eval results, and open questions. Open questions also become GitHub issues labelled `role:<id>`. CI must pass. The owner merges.
8. **After merge,** set the status to `active` in both `ROLES.md` and the definition, and shorten the `ROLES.md` entry to a pointer.

Never commit secrets or real business data (the repo is public for now). Ask instead of guessing a critical fact: open an issue and keep building what does not depend on it.

## Role definition template

Fields in the header above the line `# fields below are read by contracts/check_roles.py` are read by Claude Code. The ones below it are ours; Claude Code ignores them.

```markdown
---
name: <id>
description: <What it does and when to use it, with the phrases a caller would use. This decides when it gets called.>
model: sonnet
tools: Read, Grep, Glob, Bash, Skill        # minimum needed; add Agent only if can_call is not empty
skills: [<skill>, <skill>]                   # preloaded at start
mcpServers: [<server>]                       # only the connectors this role needs
maxTurns: 40
# fields below are read by contracts/check_roles.py
status: building
trigger: <schedule, "called by other roles", or "issue labelled role:<id>">
runs_on: cloud | server | local-device | caller   # caller = runs inside whoever calls it
can_call: [verifier]
autonomy_max: R1
---

## Role
One or two sentences: who you are and what you own.

## Definition of done
What a successful run produces, in checkable terms.

## Context map
What to read, and when. Pointers, not contents.

## How you work
The workflow and the heuristics that matter. Steps where order matters; judgment where it does not.

## Calling other roles
Who you call, for what, and what you hand over. Longer work goes to a GitHub issue labelled `role:<id>`.

## Boundaries
- Never: hard limits, also enforced by `tools`, `mcpServers` and credentials.
- Needs the owner's yes: anything R2 or above (Preflight Brief at planning time).
- When stuck: stop and name exactly what is missing. Do not guess.

## Output contract
Format, location, and what you report back to the caller or the issue.

## Memory
What to read at the start, what to save, what never to save.

## Examples
One to three canonical examples, or a pointer to `agents/<id>/examples/`.
```

## Keep it small
- The definition loads on every call, so keep it under about 100 lines. Standards that change go in `shared/` or `agents/<id>/`, not in the definition.
- Add a rule only after a real failure, and add an eval case with it.
