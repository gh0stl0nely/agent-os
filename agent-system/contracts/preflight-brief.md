# Preflight Brief (template)

Written by the agent that plans the action, reviewed by the Guardian, delivered to the owner through the Chief of Staff. One brief per action, or one batch brief for a set of like actions. Written at planning time, before anything runs. Short enough to review in under two minutes.

```markdown
# Preflight: <one-line action>

- **Brief id:** PF-YYYYMMDD-<n>
- **Requested by agent:** <role>
- **Action class:** R2 | R3 | R4 | R5 | R6   (see autonomy-matrix.md)
- **Decision needed by:** <date and time> (and why that deadline)
- **Default if no answer:** <what happens; "nothing" is the safest default>

## What exactly will happen
<Exact change, target, amounts, recipients. No vague verbs.>

## Why
<The goal this serves and the claim ids that justify it.>

## Evidence
| Claim id | Verifier result | Source |
|---|---|---|
| C-... | pass | ... |

## Alternatives considered
<At least one, including "do nothing".>

## Blast radius
<Who or what is affected if this is wrong.>

## Rollback
<Exact steps to undo, who does them, how long they take, or "not reversible" and why it is still justified.>

## Cost
<Money, tokens, time. Flag anything beyond the plan allowance (R6).>

## Safety checks done
- [ ] No secrets in the plan or output
- [ ] Target verified to exist and be the right one
- [ ] Dry run or preview completed, result attached
- [ ] Rollback tested or confirmed possible
```
