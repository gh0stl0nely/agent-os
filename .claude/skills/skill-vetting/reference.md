# skill-vetting reference

The OWASP page gives each AST item a title, severity and key mitigation (K-sec-0002); the checks below are the Guardian's own concrete tests, not OWASP text.

## Checks per AST item

| AST | Title | Checks (id) | What a fail looks like |
|---|---|---|---|
| AST01 | Malicious skills | `exec`, `obfuscation`, `exfil`, `persistence`, `hidden-unicode`, `secrets` | download-and-run, eval/exec, `os.system`, `shell=True`, reads of `~/.ssh` or cloud credentials, posting to webhook or paste hosts, encoded blobs, edits to shell profiles, git hooks or `.claude/settings`, zero-width or bidi characters, secret-like values, executables |
| AST02 | Supply chain compromise | `deps`, `provenance` | unpinned or range dependencies, no https source URL; install commands and manifests go to manual review |
| AST03 | Over-privileged skills | `tools`, `secrets` | `allowed-tools: *`, unscoped `Bash`, a skill that asks the user to paste a key or password; connector, web and write tools go to manual review |
| AST04 | Insecure metadata | `frontmatter`, `description`, `shadowing` | no SKILL.md or frontmatter, bad or vendor-imitating name, name differs from the folder, markup or 1500+ characters in the description, a name that collides with an installed skill; unknown keys and over-broad triggers go to manual review |
| AST05 | Untrusted external instructions | `follow-remote`, `hidden-intent`, `injection`, `network` | "fetch this URL and follow it", "do not tell the user", "this skill is safe", instruction-like text; network calls go to manual review with the host |
| AST06 | Weak isolation | `scope`, `writes`, `links` | `sudo`, chmod 777, docker socket, symlinks; paths outside the folder and file writes go to manual review |
| AST07 | Update drift | `pin`, `drift`, `selfupdate` | no full 40-hex SHA, content or commit changed since the inventory entry, `git pull` or auto-update inside the skill |
| AST08 | Poor scanning | `coverage`, `scanner-limits` | any file not read goes to manual review (compiled files fail AST01); `scanner-limits` is always manual |
| AST09 | No governance | `governance` | missing source, commit or reviewer; no licence goes to manual review; approval is never recorded by this tool |
| AST10 | Cross-platform reuse | `other-platform` | writes to or depends on another agent's config (`.cursorrules`, `AGENTS.md`, `.windsurf`...) go to manual review |

## What it does not do
- It matches patterns and lists calls. It cannot see logic that avoids both. That is why `scanner-limits` is always manual and the verdict is never an approval.
- It does not run the skill, even in a sandbox. Dynamic testing is a separate step for a person, and only in a sandbox that has no secrets and no access to the owner's accounts.
- It does not judge whether the skill is good, only whether it is safe to read further and propose.
- Prose that merely describes a dangerous command (a warning in a README) is downgraded to manual review rather than fail, so a person decides.
- Content outside the pinned tree (git history) is not read.

## Inventory format
`agents/03-guardian/skill-inventory.md` holds one table. A row is added **only** by this process; the owner writes the final decision.

| Column | Meaning |
|---|---|
| skill | folder name, equal to the frontmatter `name` |
| source | https URL of the repository |
| commit | full 40-character SHA that was reviewed |
| content sha256 | hash over every file path and hash in the folder, so any change is seen |
| license | licence name from frontmatter, `file` if a LICENSE file exists, else `unknown` |
| reviewed by | who read the files (`03-guardian (proposal)` for the script run; a person's name once they have read it) |
| reviewed at | date |
| status | `needs-manual-review; pending owner`, then the owner's decision with date |

Re-review every 90 days or on any change, whichever comes first.

## Fixtures
`fixtures/sample-notes` is a small benign skill; `fixtures/sample-malicious` has defects seeded on purpose (all hosts end in `.invalid` and cannot resolve). Files carry a `.fixture` suffix so no agent loads them as a skill; the evals copy them to a temp folder and remove the suffix. Other variants (hidden characters, links, binaries, fake secrets) are built at run time.
