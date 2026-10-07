# Guardian hooks (proposed, not installed)

Two Claude Code `PreToolUse` hooks (the bash one also screens connector tools) that turn the Guardian's rules into blocks. Claude Code treats `CLAUDE.md` as context, not enforcement; hooks are the part that actually stops a call. Installing them changes shared config (class R2), so the owner approves it with a Preflight Brief. Nothing here is active until then.

> **These hooks are a guardrail, not a security boundary.** They read the text of a command and refuse the well-known mistakes, with a message that says what to do instead. They do not make a session safe against a program that is trying to get around them: it can run a script it wrote earlier, call a program the parser has never heard of, or use an encoding. A session that holds the owner's GitHub credentials can do anything the owner can. Real limits live in GitHub (branch protection, push protection) and in which credentials a session is given. Where the parser does not understand a form, it blocks rather than guessing.

| File | Job |
|---|---|
| `guard_bash.py` | Reads each Bash command (never runs it) and blocks it, or stays silent. |
| `guard_write.py` | Same for Write, Edit, MultiEdit and NotebookEdit: secret-looking content, credential files, protected paths. |
| `guard_lib.py` | Shell-aware parser (quotes, `&&`, `;`, pipes, `$( )`, backticks, heredocs), wrapper unwrapping, path checks, scanner call. |
| `policy.json` | Protected branches and paths, where recursive deletes are allowed. Edit this, not the code. |
| `settings.example.json` | The block to merge into `.claude/settings.json`. |
| `test_hooks.py` | 387 checks (every bypass the review found has its own). Run before and after any change. |

## What is blocked
- **Destructive:** recursive `rm` outside `/tmp`, `find -delete`, `git reset --hard`, `git clean -f`, `git checkout -- .`, `git restore <file>`, `git stash drop`, `git branch -D`, tag deletes, history rewrites, disk and permission commands, `shutdown`, `crontab`.
- **Main line:** force pushes, deleting pushes, `git push --all`, any push to `main` or `master` (including `git push origin HEAD` while on `main`, and after a `git checkout main` earlier in the same command), push targets built from variables or patterns, a bare `git push` while on `main`, merging or rebasing while on `main`, `gh pr merge` (with `-R/--repo` anywhere), `--no-verify`.
- **Secrets:** a `git commit` whose staged changes (or files it is about to add, or `commit -a`) contain a secret-like value or a credential file; a `git push` whose outgoing commits do; a Write/Edit whose content does; reading, printing or writing `.env`, keys and credential stores; `env`/`printenv`; echoing a variable named like a key. The block message gives rule, file and line, never the value.
- **External and privileged:** `curl`/`wget` with a non-GET method or an upload (R4), `nc`, remote copies, download-and-run, `sudo`, `gh` commands that change settings, secrets or run the poster, every `gh api` write (any spelling: `-X PUT`, `-XPUT`, `--method=PUT`, or `-f` fields) except the three narrow ones below.
- **Protected paths** (policy.json): `.git/`, `.github/workflows/`, `.claude/settings*.json`, `.claude/hooks/`, these hooks, `agent-system/contracts/`.

## How commands are read
- **Wrappers are peeled off** until the real program is found: `bash|sh|zsh|dash|ksh -c` with any option cluster (`-lc`, `-ec`, `-xc`, `--login -c`, `-o pipefail -c`), `busybox APPLET`, `env` (with `-u`, `-C`, `-S`), `timeout`, `nice`, `ionice`, `stdbuf`, `nohup`, `time`, `command`, `exec`, `setsid`, `xargs`, `find -exec`, and the shell keywords `if then else while do ! { }`.
- **Default deny.** A wrapper option the hook does not know, a program name built at run time (`$CMD`, `$'\x72m'`, `$(...)`), a wrapper that runs another command in a way it cannot follow (`watch`, `flock`, `strace`, `script`, `unshare`, and similar), or inline interpreter code that shells out (`python -c "os.system(...)"`), or script text fed to a shell or interpreter on standard input (a pipe, here-document or here-string) is blocked. The message says to write the command out directly.
- **The branch is tracked inside one command line**, so `git checkout main && git push origin HEAD` is read as a push from `main`.
- **A crash blocks.** Claude Code ignores an exit code of 1, so every unexpected error is turned into exit 2.
- **Connector tools** whose names suggest merging, deleting, dispatching a workflow, protection or secrets (`mcp__*merge*` and similar) are blocked by the same hook.

## The only GitHub writes allowed through `gh api`
Posting a comment on a pull request (`repos/O/R/issues/N/comments`, field `body`), opening a pull request (`repos/O/R/pulls`, fields `title body head base draft`) and editing a comment (`PATCH repos/O/R/issues/comments/ID`, field `body`). These exist because the build protocol ends with a pull request and a comment, and `gh` GraphQL can be blocked in some environments. Anything else through `gh api` is refused.

## Unlocking a protected path for one session (owner only)
Editing the workflow, for an approved maintenance change, is blocked by default. The owner can start that session with `GUARDIAN_UNLOCK=.github/workflows/` (comma-separated exact entries from `policy.json`). The hook reads its own environment, which a command run by the agent cannot change (tested). `.git/`, `.claude/settings*.json`, `.claude/hooks/` and these hooks can never be unlocked this way.

## What is deliberately allowed
Ordinary reading, editing, testing, committing a clean change, pushing a named branch, opening a pull request, GET requests, and edits to the poster's data (`bloor-assets/`, including `state.json`). A hook cannot know which task is approved, so it blocks the dangerous class and leaves the rest to the Preflight Brief process.

## How a block works
Exit code 2 with the reason on stderr, which Claude Code feeds back to the agent. Exit 0 with no output means "no objection", never "approved". Any unreadable input, scanner failure or policy failure also blocks (fail closed).

## Limits (read these)
- A guardrail, not a sandbox or a security boundary (see the box at the top). A script written to a file and then run (`bash build.sh`), a tool the hook does not know that runs commands, or an encoding can get past a parser that reads text. GitHub's push protection and branch protection are the second layer; read `OWNER-SETUP-CHECKLIST.md`.
- **Self-merge is only stopped here.** Sessions push to GitHub as the owner (`gh0stl0nely`, an admin), so a "0 approvals" branch rule does not stop a session merging its own pull request. These hooks stop the usual routes (`gh pr merge`, `gh api -X PUT .../merge`, a push to `main`, a connector merge tool) and nothing else does. Closing the gap properly needs a second GitHub account for sessions (QUESTIONS.md Q2).
- It only runs in Claude Code sessions that load the settings. It does not affect the GitHub Actions poster run, you at a terminal, or other tools.
- The `if` filter in a hook handler is best effort (K-sec-0007), so `settings.example.json` does not use it; the scripts inspect the command themselves.
- The scanner is heuristic (token formats and entropy); it will miss unusual secrets and may flag odd strings. A false block is cheaper than a leaked key; to proceed, remove the string or ask the owner.
- The JSON field names (`tool_name`, `tool_input.command`, `cwd`) follow Claude Code's hooks page as recorded in K-sec-0007. I could not run a live Claude Code session with the hooks installed, so the first install should be checked with one harmless blocked command (for example `git push --force` on a scratch branch) before relying on them.
