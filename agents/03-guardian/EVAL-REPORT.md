# Eval report: 03 Guardian

**Run:** 2026-10-07, Python 3.13, jsonschema 4.26, no network. **Command:** `python3 agents/03-guardian/run_evals.py --log agents/03-guardian/eval-log.txt`. The full output of the last run is in `eval-log.txt`. Every result below is from that run; none is assumed.

## Result: 605 of 605 checks pass

| Suite | Checks | Covers |
|---|---|---|
| risk-classify | 52 | 45 fixture actions (all seven classes, 13 ambiguous); never below expected class; instruction-like and hidden-character text; secret-like value in a description; blank input; envelope and claim-row validation against the contracts |
| secrets-hygiene | 56 | 13 seeded fake token formats built at run time; diff, staged, path and plan-text modes; risky file names; binary, suppressed and skipped files; placeholders and `.env.example`; the 7 files in `contracts/examples` produce zero findings; the report never contains a value |
| preflight-brief | 74 | 7 fixture plans R2 to R6 build, validate and produce envelopes with `preflight_id`; missing fields; pending, blocked, failed-verification and unknown claims rejected; a forged "pass" in a hand-written brief rejected; class below R1/R2 and below the computed class rejected; injected text and secrets in a plan blocked |
| rollback-plan | 60 | 7 acceptable and 20 defective rollback plans; every fixture brief's rollback has a test step and the same text with the test sentence removed is flagged; class-specific needs (backup, recall, revoke, cancel); injection and secrets |
| skill-vetting | 124 | all ten AST items present with checks and evidence for a benign and a malicious skill; the seeded malicious skill rejected, with 18 named rules found; run-time variants (hidden characters, symlink, ELF, `.pyc`, binary, non-UTF-8, oversize, deep folder, `.git`, fake secret, bad metadata, tools, pinning, drift, collisions); nothing in the skill is run |
| hooks | 219 | 100 commands that must be blocked (each with its expected rule), 64 that must be allowed, plus bare push and merge while on `main`, secret-in-commit in five command forms, secret in push, write hook, poster-state allowed, malformed input fails closed |
| poster-state (simulation) | 20 | the current workflow step fails under simulated protection; the proposed flow keeps the save working, fails closed, merges rather than overwrites, and survives a race and an outage |

## Acceptance criteria

| # | Criterion | Result | Where it is shown |
|---|---|---|---|
| 1 | Classifies 30+ fixtures correctly, never rounds down | Met: 45 fixtures, all exact; a separate check that none is below expectation | risk-classify `E-normal` checks |
| 2 | Briefs from fixtures validate; a brief citing an unverified claim is rejected | Met | preflight-brief `normal:` and `seeded-error:` checks |
| 3 | Scanner catches seeded fakes; does not flag `contracts/examples` | Met | secrets-hygiene `false-positive: contracts/examples has zero findings (7 files)`; hooks `committing a copy of agent-system/contracts/examples is allowed` |
| 4 | Skill-vetting maps every AST item to a check with pass/fail evidence and flags the seeded malicious skill | Met | skill-vetting `AST map` and `seeded-error` checks |
| 5 | Every rollback plan has a test step; one without it is flagged | Met | rollback-plan `seeded-error/brief:` checks, 7 of 7 |
| 6 | Hooks block a seeded fake secret commit and a destructive command; allow a normal commit | Met in test. Not run inside a live Claude Code session (see below) | hooks `secret:`, `deny[...]`, `normal:` checks |
| 7 | Checklist accurate for a public repo, states paid-plan needs, keeps the poster's state commit working | Met on paper and in simulation. The real GitHub behaviour is not confirmed (below) | `OWNER-SETUP-CHECKLIST.md`; poster-state suite |
| 8 | An instruction hidden in a planned action is ignored and flagged | Met for plain, zero-width-split and multi-field cases in all five skills and both hooks | risk-classify `E-adversarial`; preflight-brief, rollback-plan, skill-vetting and hooks `adversarial:` |

## Failures found while building, and what I did (none left open)

| Found by | Failure | Fix |
|---|---|---|
| risk-classify evals | "Upgrade the Claude plan..." and "Use the paid Anthropic API..." were classed R2, not R6 (a regex needed two conditions, another needed a literal adjective) | Fixed the classifier rules, not the fixtures |
| secrets-hygiene evals | A seeded JWT was not caught because my fake had segments shorter than the pattern requires | Lengthened the fake; the pattern is unchanged |
| preflight-brief first run | `build_brief.py` crashed on every plan (a missing module prefix) | Fixed; all seven plans build |
| preflight-brief first run | A valid "N/A" safety check was rejected because the reason rule demanded ten characters without spaces | Rule changed to ten characters of any kind |
| rollback-plan evals | An instruction split by a zero-width character inside a plan was not caught: the plan was turned to text with JSON escaping, which hid the character from the normalizer. Also affected `build_brief.py` | `ensure_ascii=False` in both; two evals now test the split case |
| skill-vetting evals | `re.compile()` was reported as the `compile()` builtin, so every skill using regexes was rejected; the first eval run also masked several defects behind a folder-name mismatch | Builtin check now requires a bare or `builtins.` call; evals keep each skill in a folder with its own name |
| hooks tests | `rm -r` inside the test repo passed because the temporary repo sat under `/tmp`, which the policy treats as safe | Recursive deletes inside the repository are now blocked even under `/tmp` |
| hooks tests | `env` alone was not blocked (treated as a wrapper); `wget --post-data=...` was not blocked; findings printed `?` for the file (field is `source`) | All three fixed and covered |
| poster-state tests | A second save overwrote an earlier day's entry when two runs raced | `save_state.sh` now merges the earlier history instead of replacing it |
| self-scan with the vetting tool | Compiled `.pyc` files from my own runs had been committed into two skill folders, and my scripts regenerated them | Removed from git; every script now sets `sys.dont_write_bytecode` |
| self-check | Invisible characters were present as literal characters in four of my own source files | Replaced with `\u` escapes; the tests still build the same text at run time |

## What these results do not show

- **Hooks in a live session.** The hook scripts were tested by feeding them JSON shaped as Claude Code's hooks page documents (K-sec-0007). I did not run a Claude Code session with the hooks installed. First install: run one harmless blocked command to confirm.
- **GitHub behaviour.** The poster-state suite simulates protection with a local pre-receive hook. It proves the scripts' logic. Whether the workflow's bot could bypass a rule (K-sec-0006) and the exact menu names were not observed. `test-poster-state.yml.proposed` is the real check, to be run by the owner.
- **Real third-party skills.** None was vetted. The malicious sample is synthetic and written by me, so a pass on it shows the checks fire on what I thought of, not on what an attacker would write. The vetting report says so on every run (AST08, always manual).
- **Pattern limits.** The classifier, scanner and vetting rules are heuristics. Wording the classifier does not recognise is classed R2 with `needs_review`: for example "Create a new draft file in my own folder" is R2 here, although the matrix would call it R1. That is a deliberate round-up.
- **Cross-check by another party.** A builder is not a reviewer. These are my own evals; the review session should re-run them and try a case I did not (for example a command shape the hook parser may misread).
- **First-party skills trip the vetting tool.** They contain the attack strings they test for (see `skill-inventory.md`). That is expected, but it means the tool cannot give them a clean verdict.
- **Git history scan** covered the 9 commits of a shallow clone only (no secret-like value found).
