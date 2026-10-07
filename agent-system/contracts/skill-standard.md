# Skill standard

Every skill built for this system follows this. A skill is one unit: one purpose, one owner role, its own tests.

## Location and shape

```
.claude/skills/<skill-name>/
  SKILL.md              required: frontmatter plus instructions (keep it short)
  reference.md          optional: detail loaded only when needed
  scripts/              deterministic work (math, validation, parsing); no tokens
  fixtures/             synthetic inputs only; never real financial or personal data
  evals/                cases: input, expected output, why
```

Claude Code finds project skills in `.claude/skills/<name>/SKILL.md`. The frontmatter needs `name` and `description`. The description is what triggers the skill, so lead with the main use case and include natural trigger phrases; keep it under about 1,500 characters.

## SKILL.md sections

1. **Purpose** in one or two sentences
2. **Inputs** (what it needs, where from, what to do if missing)
3. **Procedure** (numbered; mark which steps are scripts and which are judgment)
4. **Evidence rules** (every claim becomes a row that fits `claim-ledger.schema.json`; unevidenced claims are `blocked`)
5. **Outputs** (an envelope that fits `agent-envelope.schema.json`)
6. **Side effects** (list each with its action class from `autonomy-matrix.md`; R2+ means a Preflight Brief at planning time)
7. **Escalation** (when to stop and ask, and exactly what to ask for)
8. **Knowledge use** (look up `knowledge/` first; write findings back through the write gate)

## Rules

- Compute with code. Any number the skill reports comes from a script whose inputs and outputs are logged.
- Never invent a source, a number, or a policy. If it cannot be evidenced, say so and escalate.
- No secrets in any file. No real financial, personal, supplier or order data in this public repo.
- Each skill declares a **model tier** (Sonnet by default; Opus only where its brief says; Haiku for high-volume checks) and why.
- Each skill ships evals. At minimum: a normal case, a missing-data case, a seeded-error case that the skill must catch or refuse, and an adversarial case (the input contains an instruction the skill must treat as data and ignore).
- Third-party skills are reviewed per `reusable-skills.md` before reuse. Pin to a commit SHA and record it.
- Author with the `skill-creator` skill where available, and research current authoring best practice first.

## Agent card

Each role also ships `agents/NN-<role>/CARD.md` with: mission, skills (names), inputs, outputs, schedule, model and why, action classes used, dependencies on other roles, known limits. The Chief of Staff builds its registry from these cards.
