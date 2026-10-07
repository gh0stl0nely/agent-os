# Skill inventory

The record of every skill that is allowed into `.claude/skills/` and where it came from. Installing a skill is an R2 action (Preflight Brief), and no third-party skill goes in without a row in table 1 whose `status` ends in the owner's written decision. Format and the checks behind it: `.claude/skills/skill-vetting/reference.md`.

**Rules (from `agent-system/reusable-skills.md`, enforced by the Guardian):** read every file; pin to a full 40-character commit SHA; re-review on every change (a changed content hash fails AST07); a pattern scan is never an approval; only the owner approves.

## 1. Third-party skills

| skill | source | commit | content sha256 | license | reviewed by | reviewed at | status |
|---|---|---|---|---|---|---|---|
| *(none installed or approved)* | | | | | | | |

No third-party skill has been vetted, installed or approved as of 2026-10-07. The candidates named in `agent-system/reusable-skills.md` have **not** been run through `skill-vetting`; treat all of them as not vetted and do not install any until a row above exists.

### Format example (a fixture, not installed)
The benign fixture `skill-vetting/fixtures/sample-notes`, run through the vetting script on 2026-10-07. The commit is all zeros because a fixture has no upstream; a real row carries the real SHA. `needs-manual-review` is the best result the script can give: it means no check failed and a person still has to read the files.

| skill | source | commit | content sha256 | license | reviewed by | reviewed at | status |
|---|---|---|---|---|---|---|---|
| sample-notes (EXAMPLE) | this repo, `.claude/skills/skill-vetting/fixtures/sample-notes` | `0000000000000000000000000000000000000000` | `971f4ef486c015b6b4c04b88eadc5e8bfc84f1715ad157ba89ddb21fe4a0b076` | MIT | 03-guardian (proposal) | 2026-10-07 | needs-manual-review; example only, never installed |

## 2. First-party skills built in this repository (Guardian)

These were written by the Guardian session in this pull request, so there is no outside source to pin; the commit is the merge commit and is filled in by the owner or the review session when the pull request is merged. The hash lets a later session see whether a skill changed: regenerate with `python3 -I .claude/skills/skill-vetting/scripts/vet_skill.py .claude/skills/<name> --source https://github.com/gh0stl0nely/business-assets --commit <sha> --reviewer <name>` and compare `content_sha256`.

| skill | source | content sha256 | files | vetting script flags (expected, see note) |
|---|---|---|---|---|
| risk-classify | `agents/03-guardian` (this repo) | `d9a763bd299b161d851ca7fb4afa89f5244338b1ca2fa7d95a2b7a16e509434a` | 6 | exec, persistence, secrets, injection |
| secrets-hygiene | `agents/03-guardian` (this repo) | `0cb2eb66d00835854dd1d169d4debeb1d44e22cb2e3396fcb97f9c7b73f8f30a` | 4 | exfil, secrets, hidden-intent, injection |
| preflight-brief | `agents/03-guardian` (this repo) | `567b0c432e0270d8d00679f8e5a2fbe10bc2dc7fb03dafb36fa521bbc771e173` | 8 | injection |
| rollback-plan | `agents/03-guardian` (this repo) | `c2024ef799001287564b16b38a35ce7c4e9da032c2dd545546055912777feba8` | 5 | injection |
| skill-vetting | `agents/03-guardian` (this repo) | `86e4f738650328e7344f9fbab5f3975a5827c2982bfa512978819dbca763a387` | 12 | exec, exfil, obfuscation, persistence, secrets, follow-remote, hidden-intent, injection, scope, selfupdate |

**Why the vetting script flags our own skills.** They are security tools: their rule tables, fixtures and tests contain the very patterns the script looks for (destructive commands, injection phrases, credential file names, zero-width characters), written on purpose to prove the checks work. The script correctly reports them as findings and gives a `reject` verdict. That is a property of the scanner reading attack strings, not evidence of a bad skill, and it is the reason first-party skills get a review-session read instead of a scan verdict. Files with a failed check, from the run on 2026-10-07 (the number is how many failed evidence lines):
- risk-classify: `fixtures/actions.json` (5), `evals/cases.json` (7), `evals/run_evals.py` (1), `scripts/classify.py` (1, the rule table).
- secrets-hygiene: `scripts/scan_secrets.py` (5, the pattern table), `evals/run_evals.py` (5), `SKILL.md` (2) and `reference.md` (1), where the text names credential files and secret-like words to explain the job.
- preflight-brief: `evals/run_evals.py` (3, injected sentences used as test input).
- rollback-plan: `fixtures/rollbacks.json` (1), `evals/run_evals.py` (2).
- skill-vetting: `scripts/vet_skill.py` (34, the rule table), `evals/run_evals.py` (15), `reference.md` (4) and `SKILL.md` (1), plus the deliberately malicious fixtures (22).
A reviewer should open these lines and confirm each is a pattern or a test input, not behaviour.

## 3. Fixtures and the load path
Test skills live under `.claude/skills/skill-vetting/fixtures/` with a `.fixture` suffix on every file so Claude Code cannot load them as real skills. Never remove the suffix inside the repo; the evals do it in a temp folder.
