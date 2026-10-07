# Eval report: 03 Guardian

**Run:** 2026-10-07, Python 3.13, jsonschema 4.26, no network. **Command:** `python3 agents/03-guardian/run_evals.py --log agents/03-guardian/eval-log.txt`. The full output of the last run is in `eval-log.txt`. Every result below is from that run; none is assumed.

## Result: 857 of 857 checks pass (round 2, after the review of PR #2; round 1 was 605)

| Suite | Checks | Covers |
|---|---|---|
| risk-classify | 81 | 45 fixture actions (all seven classes, 13 ambiguous) and 17 review actions (3 quoted by the reviewer, 14 builder stand-ins); never below expected class; 62 actions x 16 decorations never lowers a class; unsure results go up, not down, and need the owner's explicit yes; instruction-like and hidden-character text; secret-like value in a description; blank input; envelope and claim-row validation against the contracts |
| secrets-hygiene | 56 | 13 seeded fake token formats built at run time; diff, staged, path and plan-text modes; risky file names; binary, suppressed and skipped files; placeholders and `.env.example`; the 7 files in `contracts/examples` produce zero findings; the report never contains a value |
| preflight-brief | 74 | 7 fixture plans R2 to R6 build, validate and produce envelopes with `preflight_id`; missing fields; pending, blocked, failed-verification and unknown claims rejected; a forged "pass" in a hand-written brief rejected; class below R1/R2 and below the computed class rejected; injected text and secrets in a plan blocked |
| rollback-plan | 60 | 7 acceptable and 20 defective rollback plans; every fixture brief's rollback has a test step and the same text with the test sentence removed is flagged; class-specific needs (backup, recall, revoke, cancel); injection and secrets |
| skill-vetting | 124 | all ten AST items present with checks and evidence for a benign and a malicious skill; the seeded malicious skill rejected, with 18 named rules found; run-time variants (hidden characters, symlink, ELF, `.pyc`, binary, non-UTF-8, oversize, deep folder, `.git`, fake secret, bad metadata, tools, pinning, drift, collisions); nothing in the skill is run |
| hooks | 387 | 199 commands that must be blocked (each with its expected rule), 100 that must be allowed, plus pushes and merges while on `main` (including after a checkout in the same command), the owner-only unlock, a crash exits 2, connector tools, secret-in-commit in five command forms, secret in push, write hook, poster-state allowed, malformed input fails closed |
| poster-state (simulation) | 20 | the current workflow step fails under simulated protection; the branch flow keeps the save working, fails closed on a missing or invalid branch, and merges rather than overwrites. **It does not show that a failed save is safe**: round 1 asserted only an exit code and a message there; the claim "survives an outage" was wrong and is withdrawn |
| poster fail-closed (simulation) | 55 | the real `post_threads.py` patched with `post_threads.gate.patch`, against a fake Threads and a local bare repository; the reviewer's three failure paths and 10 more (below) |

## Acceptance criteria

| # | Criterion | Result | Where it is shown |
|---|---|---|---|
| 1 | Classifies 30+ fixtures correctly, never rounds down | Met on the 45 fixtures and, after round 2, on 17 more plus a 992-case decoration test. The reviewer's held-out run found 3 of 17 fell to R2; fixed. The remaining 14 of the reviewer's wordings were not in the comment, so my stand-ins are regression evidence only | risk-classify `E-normal`, `review-heldout`, `never-round-down` checks |
| 2 | Briefs from fixtures validate; a brief citing an unverified claim is rejected | Met | preflight-brief `normal:` and `seeded-error:` checks |
| 3 | Scanner catches seeded fakes; does not flag `contracts/examples` | Met | secrets-hygiene `false-positive: contracts/examples has zero findings (7 files)`; hooks `committing a copy of agent-system/contracts/examples is allowed` |
| 4 | Skill-vetting maps every AST item to a check with pass/fail evidence and flags the seeded malicious skill | Met | skill-vetting `AST map` and `seeded-error` checks |
| 5 | Every rollback plan has a test step; one without it is flagged | Met | rollback-plan `seeded-error/brief:` checks, 7 of 7 |
| 6 | Hooks block a seeded fake secret commit and a destructive command; allow a normal commit | Met in test. Not run inside a live Claude Code session (see below) | hooks `secret:`, `deny[...]`, `normal:` checks |
| 7 | Checklist accurate for a public repo, states paid-plan needs, keeps the poster's state commit working | Met on paper and in simulation, after round 2 corrections (secret scanning is disabled today; self-merge gap; do not protect `main` first). The real GitHub behaviour is not confirmed (below) | `OWNER-SETUP-CHECKLIST.md`; both poster suites |
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

## Review round 2: each finding, what changed, the evidence

| # | Finding (severity) | What I did | Evidence |
|---|---|---|---|
| 1 | Poster double-post if the save fails; stale branch; bad rollback (High) | Did not touch `.github/workflows/`, `scripts/` or `bloor-assets/`. Wrote a change request with a fail-closed design (claim before posting by a non-force push; point of no return; unconfirmed claim blocks) and a 20-line patch, and tested it by applying the patch to a copy of the real script. Rewrote the checklist: do not protect `main` until you approve and test it. | `test_fail_closed.py`, 55 checks. S0 reproduces the finding (old flow: 2 posts live). S2/S6/S8: the post is live and unrecorded, the backup crons exit 11, one post stays live. S4: claim cannot be written, nothing posts. S5: failure before publish releases the claim and the backup posts once. S9: two simultaneous claims, one wins. S10: stale branch, restore and claim both refuse. S11: naive rollback posts a third time; export-then-PR rollback does not. S12: `--dry-run` and `--check` never reach the gate. |
| 2 | `bash -lc`, `-ec`, `sh -ec`, `zsh -lc` bypassed every check (High) | Any option cluster containing `c` is read as `-c`; `-o NAME`, `--login`, nesting and `busybox` handled; unknown wrapper options and unknown wrappers are refused (default deny). | hooks: each variant has its own `deny[...]` test, plus neighbouring spellings (busybox, env, timeout, nice, xargs, nested shells) |
| 3 | `gh -R/--repo ... pr merge`, `gh api -XPUT` and `--method=PUT`, `git push origin HEAD` on `main`, `busybox rm -rf` (High) | `gh` parser skips `-R/--repo`; every method spelling is read; `HEAD` resolves to the current branch, which is tracked across a `git checkout main &&` in the same command; `--all`, variable and pattern push targets are refused. While fixing: stdin-fed shells (`bash <<EOF`, `... | sh`), `git -c alias.x=...`, `find -exec`, shell keywords (`if/then/do/{`), run-time program names, inline interpreter code, connector merge tools, and a crash exiting 1 (which Claude Code ignores) were closed too. README now says: a guardrail, not a security boundary. | hooks: 387 checks, 168 new. Every bypass the review named is a `deny[...]` row. |
| 4 | Checklist said secret scanning "runs on its own" (Medium) | Corrected: both secret scanning and push protection read `disabled` (my own read-only API call, 2026-10-07); GitHub's page says partner secrets go to the provider, not your alerts. Steps and sources added. New record K-sec-0009 (supersedes K-sec-0003 for this repo). | checklist steps 1 and 2; `K-sec-0009` |
| 5 | Identity and the self-merge gap (Medium) | Recommended rule changed to: require a pull request with 0 approvals, block force pushes and deletions, do not allow bypassing. Recorded that sessions push as the owner, so only the hooks or a second GitHub account (approvals 1; token is R5) stop a session merging its own PR. The choice is QUESTIONS.md Q2. | checklist step 7; `K-sec-0010`; QUESTIONS Q2 |
| 6 | Three risk-classify misses (Medium) | Widened the rules (dispatch/trigger/re-run a workflow, send a message, team and group-chat recipients, bump/upgrade a plan or tier, automatic payments, grant access, ask/tell/ping); an unrecognised action with a dangerous word anywhere goes up to R3/R4/R6; `needs_review` and flagged text now need the owner's explicit yes. Found by my own probing: an adverb ("Quietly delete...") rounded R3/R4 down to R2 for 10 of 45 fixtures; fixed and covered by a decoration test. | risk-classify: 81 checks; `fixtures/review-heldout.json`. Only 3 of the 17 reviewer wordings were quoted in the comment; the other 14 are mine (QUESTIONS Q9). |
| 7 | Hooks block the REST comment fallback and workflow edits; step order; dry run does not exercise the push (Low) | Narrow `gh api` allow: comment on a PR, open a PR, edit a comment, each with only its own fields. Owner-only `GUARDIAN_UNLOCK` for a protected path (agent cannot set it; git internals, settings and hooks never unlockable). Real-GitHub probe moved after protection, runs the gate (not a force-push) on a throwaway branch. Checklist says the dry run does not exercise any push. | hooks `unlock:` and allow rows; `test_fail_closed.py` S12b |

### Failures found while fixing, and what I did (none left open)

| Found by | Failure | Fix |
|---|---|---|
| fail-closed suite | Save pushed a second commit after a normal post because the merged file listed days in a different order | Days are kept sorted and compared as data, not text |
| fail-closed suite | A test expected the claim step to refuse in a case where the script's own check already prevented the post | Test rewritten to a day only the gate can catch |
| hooks tests | `eval "$(...)"` became "unparseable" instead of its own rule | The eval substitution rule runs first |
| hooks tests | Checks for "moving off main" and "unlock `.claude/settings.json`" had wrong setups (a branch that did not exist; a path that did not match) | Tests corrected; the hook was right |
| risk-classify probe | Fillers before a verb hid it from the rule (R3/R4 became R2) | Fillers allowed; perturbation test added |
| risk-classify fixtures | "Wipe the poster-state branch" was classed R4 because "poster" matched the live-poster rule | Rule requires the word `poster` not followed by a hyphen |

### Still not shown
- The poster gate on real GitHub (checklist steps 4 to 6 are that trial).
- The hooks inside a live Claude Code session; the `GUARDIAN_UNLOCK` variable reaching the hook process is by Claude Code's documented design but was tested only by setting it on the hook process.
- The reviewer's other 14 held-out wordings.

## What these results do not show

- **Hooks in a live session.** The hook scripts were tested by feeding them JSON shaped as Claude Code's hooks page documents (K-sec-0007). I did not run a Claude Code session with the hooks installed. First install: run one harmless blocked command to confirm.
- **GitHub behaviour.** The poster-state suite simulates protection with a local pre-receive hook. It proves the scripts' logic. Whether the workflow's bot could bypass a rule (K-sec-0006) and the exact menu names were not observed. `test-poster-state.yml.proposed` is the real check, to be run by the owner.
- **Real third-party skills.** None was vetted. The malicious sample is synthetic and written by me, so a pass on it shows the checks fire on what I thought of, not on what an attacker would write. The vetting report says so on every run (AST08, always manual).
- **Pattern limits.** The classifier, scanner and vetting rules are heuristics. Wording the classifier does not recognise is classed R2 with `needs_review`: for example "Create a new draft file in my own folder" is R2 here, although the matrix would call it R1. That is a deliberate round-up.
- **Cross-check by another party.** A builder is not a reviewer. These are my own evals; the review session should re-run them and try a case I did not (for example a command shape the hook parser may misread).
- **First-party skills trip the vetting tool.** They contain the attack strings they test for (see `skill-inventory.md`). That is expected, but it means the tool cannot give them a clean verdict.
- **Git history scan** covered the 9 commits of a shallow clone only (no secret-like value found).
