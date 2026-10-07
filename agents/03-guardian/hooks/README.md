# Guardian hooks (proposed, not installed)

Two Claude Code `PreToolUse` hooks that turn the Guardian's rules into hard blocks. Claude Code treats `CLAUDE.md` as context, not enforcement; hooks are the part that actually stops a call. Installing them changes shared config (class R2), so the owner approves it with a Preflight Brief. Nothing here is active until then.

| File | Job |
|---|---|
| `guard_bash.py` | Reads each Bash command (never runs it) and blocks it, or stays silent. |
| `guard_write.py` | Same for Write, Edit, MultiEdit and NotebookEdit: secret-looking content, credential files, protected paths. |
| `guard_lib.py` | Shell-aware parser (quotes, `&&`, `;`, pipes, `$( )`, backticks, `bash -c`, heredocs), path checks, scanner call. |
| `policy.json` | Protected branches and paths, where recursive deletes are allowed. Edit this, not the code. |
| `settings.example.json` | The block to merge into `.claude/settings.json`. |
| `test_hooks.py` | 219 checks. Run before and after any change. |

## What is blocked
- **Destructive:** recursive `rm` outside `/tmp`, `find -delete`, `git reset --hard`, `git clean -f`, `git checkout -- .`, `git restore <file>`, `git stash drop`, `git branch -D`, tag deletes, history rewrites, disk and permission commands, `shutdown`, `crontab`.
- **Main line:** force pushes, deleting pushes, any push to `main` or `master`, a bare `git push` while on `main`, merging or rebasing while on `main`, `gh pr merge`, `--no-verify`.
- **Secrets:** a `git commit` whose staged changes (or files it is about to add, or `commit -a`) contain a secret-like value or a credential file; a `git push` whose outgoing commits do; a Write/Edit whose content does; reading, printing or writing `.env`, keys and credential stores; `env`/`printenv`; echoing a variable named like a key. The block message gives rule, file and line, never the value.
- **External and privileged:** `curl`/`wget` with a non-GET method or an upload (R4), `nc`, remote copies, download-and-run, `sudo`, `gh` commands that change settings, secrets or run the poster, non-GET `gh api`.
- **Protected paths** (policy.json): `.git/`, `.github/workflows/`, `.claude/settings*.json`, `.claude/hooks/`, these hooks, `agent-system/contracts/`.

## What is deliberately allowed
Ordinary reading, editing, testing, committing a clean change, pushing a named branch, opening a pull request, GET requests, and edits to the poster's data (`bloor-assets/`, including `state.json`). A hook cannot know which task is approved, so it blocks the dangerous class and leaves the rest to the Preflight Brief process.

## How a block works
Exit code 2 with the reason on stderr, which Claude Code feeds back to the agent. Exit 0 with no output means "no objection", never "approved". Any unreadable input, scanner failure or policy failure also blocks (fail closed).

## Limits (read these)
- A speed bump, not a sandbox. A command built with variables, `eval` of a variable, or an encoded string can get past a parser that reads text. GitHub's push protection and branch protection are the second layer; read `OWNER-SETUP-CHECKLIST.md`.
- It only runs in Claude Code sessions that load the settings. It does not affect the GitHub Actions poster run, you at a terminal, or other tools.
- The `if` filter in a hook handler is best effort (K-sec-0007), so `settings.example.json` does not use it; the scripts inspect the command themselves.
- The scanner is heuristic (token formats and entropy); it will miss unusual secrets and may flag odd strings. A false block is cheaper than a leaked key; to proceed, remove the string or ask the owner.
- The JSON field names (`tool_name`, `tool_input.command`, `cwd`) follow Claude Code's hooks page as recorded in K-sec-0007. I could not run a live Claude Code session with the hooks installed, so the first install should be checked with one harmless blocked command (for example `git push --force` on a scratch branch) before relying on them.
