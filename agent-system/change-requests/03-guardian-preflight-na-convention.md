# Change request: how a Preflight Brief marks a safety check that cannot apply

- **From:** 03 Guardian builder session
- **Contract:** `agent-system/contracts/preflight-brief.md` (section "Safety checks done")
- **Priority:** low; the Guardian's skills work today with a convention that fits the current template.

## What is needed
The template shows four unchecked boxes and says nothing about a check that cannot apply. Two of them regularly cannot: "Dry run or preview completed" (a password change, a trial sign-up and a file copy have no preview mode) and sometimes "Rollback tested" (R4/R5 actions). Without a rule, planners either tick a box that is not true or leave it unticked, and the Guardian cannot tell the two apart.

## What the Guardian does now (convention, not contract)
A check is either ticked, `- [x] <label> - <what was done>`, or marked `- [ ] <label> - N/A: <reason of ten or more characters>`. The `preflight-brief` skill (`scripts/check_brief.py`) rejects a brief where a box is neither. Any of the four may carry N/A if a reason is given; the reason is shown to the owner.

## Proposed contract text
Add under the checklist: "A box may be left unticked only when it cannot apply. Write `N/A: ` and the reason on the same line. A brief with an unticked box and no reason is incomplete."

## Which examples would change
None of the bundled examples use the checklist; `contracts/examples/` needs no edit.

## If declined
`check_brief.py` reads its rules from one function; the N/A branch can be removed in a small change and plans would then need all four boxes ticked.
