#!/usr/bin/env python3
"""PreToolUse hook for the Bash tool. PROPOSED by the Guardian; the owner installs it (see README.md).

Reads the tool call as JSON on stdin. Exit 0 with no output = no objection (it never approves anything).
Exit 2 with a reason on stderr = blocked. It reads the command; it never runs it.

Blocks: destructive commands, force pushes and pushes to main, merging, secret-looking content in a commit or push,
reading or printing credentials, download-and-run, external writes by curl, privilege escalation, edits to protected
paths. Rules and paths come from policy.json.
"""
import os
import re
import subprocess
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import guard_lib as g  # noqa: E402

SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "python", "python3", "node", "perl", "ruby", "php"}
READERS = {"cat", "less", "more", "head", "tail", "grep", "egrep", "rg", "ag", "sed", "awk", "cp", "mv", "scp", "rsync", "base64", "xxd", "od", "strings", "tar", "zip", "open", "bat", "nl", "tee", "curl", "wget", "source", "."}
MUTATORS = {"rm", "mv", "cp", "tee", "truncate", "install", "ln", "chmod", "chown", "touch", "patch", "shred", "unlink", "rmdir", "mkdir", "dd", "rsync"}
SECRET_VAR = re.compile(r"\$\{?[A-Za-z0-9_]*(?:KEY|TOKEN|SECRET|PASSW(?:OR)?D|CREDENTIAL|PRIVATE)[A-Za-z0-9_]*\}?", re.I)
INTERPRETERS = {"python", "python3", "python2", "node", "nodejs", "perl", "ruby", "php", "deno", "bun", "lua"}
INLINE_FLAG = re.compile(r"(?:^|\s)(?:-[A-Za-z]*[ceE]|--eval|--command)\b")
INLINE_SHELLOUT = re.compile(r"os\.system|os\.popen|os\.exec|os\.spawn|subprocess|popen|\bexec\s*\(|child_process|\bsystem\s*\(|\bexecSync|spawnSync|shutil\.rmtree|os\.remove|os\.unlink|\bunlink\s*\(|rmtree|`[^`]+`|Deno\.run|Deno\.Command|Bun\.spawn|io\.popen|\bqx\b")
FORK_BOMB = re.compile(r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:")


def flags_of(args):
    short, long_, rest, done = set(), set(), [], False
    for a in args:
        if done or not a.startswith("-") or a == "-":
            rest.append(a)
        elif a == "--":
            done = True
        elif a.startswith("--"):
            long_.add(a.split("=")[0])
        else:
            short.update(a[1:])
    return short, long_, rest


def git_parts(args):
    """(global C dir or None, subcommand, subcommand args, the `-c key=value` settings given before the subcommand)."""
    i, cdir, cvals = 0, None, []
    while i < len(args):
        a = args[i]
        if a == "-C" and i + 1 < len(args):
            cdir = args[i + 1]; i += 2
        elif a == "-c" and i + 1 < len(args):
            cvals.append(args[i + 1]); i += 2
        elif a in ("--git-dir", "--work-tree", "--namespace") and i + 1 < len(args):
            i += 2
        elif a.startswith("-"):
            i += 1
        else:
            return cdir, a, args[i + 1:], cvals
    return cdir, "", [], cvals


def current_branch(cwd):
    p = subprocess.run(["git", "-C", cwd, "symbolic-ref", "--short", "-q", "HEAD"], capture_output=True, text=True)
    return p.stdout.strip() if p.returncode == 0 else ""


def check_rm(prog, args, cwd, root, pol):
    short, long_, targets = flags_of(args)
    rec = bool(short & set("rR")) or "--recursive" in long_
    for t in targets:
        p = g.resolve(t, cwd)
        if p is not None and g.is_protected(p, root, pol):
            g.deny("protected-path", f"{prog} would remove {os.path.relpath(p, root)}, a protected path.", "Ask the owner to change it.")
        if p is not None and (p == "/" or p == os.path.expanduser("~") or p == root):
            g.deny("delete-root", f"{prog} would remove {'the repository' if p == root else p}.")
        if t in ("*", ".*", "/*", "~", "~/", "."):
            g.deny("delete-wildcard", f"{prog} with the target '{t}' removes everything in a folder.")
    if rec:
        roots = pol["safe_delete_roots"]
        for t in targets:
            p = g.resolve(t, cwd)
            ok = p is not None and not (p == root or p.startswith(root.rstrip("/") + "/")) and any(p.startswith(r) and p.rstrip("/") + "/" != r for r in roots)
            if not ok:
                g.deny("recursive-delete", f"{prog} -r on '{t}' is an irreversible delete (R3), outside the temporary folders {roots}.",
                       "Write a Preflight Brief with a backup and rollback step, or delete only below /tmp.")
        if not targets:
            g.deny("recursive-delete", f"{prog} -r with no clear target.")


def check_git(args, cwd, root, pol, seg_has_add, state):
    cdir, sub, a, cvals = git_parts(args)
    if any(re.match(r"(?i)(alias\.|core\.(hookspath|fsmonitor|sshcommand|pager|editor)|credential\.|url\.|http\.|include|protocol\.)", v) for v in cvals):
        g.deny("git-config", "a one-off git setting (-c) can define an alias or hook that runs any command, or redirect where git sends data (R2/R5).")
    if cdir:
        cwd = g.resolve(cdir, cwd) or cwd
    short, long_, rest = flags_of(a)
    # The branch this command will be on when git runs. An earlier `git checkout main` in the SAME command line
    # changes it, so track that; "?" means unknown and is treated as the protected branch.
    branch = state.setdefault("branch", {}).get(cwd) or current_branch(cwd)
    prot = pol["protected_branches"]
    on_prot = branch in prot or branch == "?"
    if "--no-verify" in long_ or (sub == "commit" and "n" in short):
        g.deny("no-verify", "skipping git hooks (--no-verify) switches off the checks that protect this repo.")
    if sub == "push":
        if long_ & {"--force", "--force-with-lease", "--force-if-includes", "--mirror", "--delete", "--prune"} or "f" in short or "d" in short:
            g.deny("force-push", "a forced or deleting push rewrites or removes history on the remote (R3, default deny).", "Ask the owner; use a normal push or a new branch.")
        if "--all" in long_:
            g.deny("push-all", "git push --all pushes every local branch, including main.", "Push the one branch you built, by name.")
        refspecs = rest[1:] if len(rest) > 1 else []
        for r in refspecs:
            if r.startswith("+"):
                g.deny("force-push", f"refspec '{r}' forces the update.")
            if r.startswith(":"):
                g.deny("delete-remote-ref", f"refspec '{r}' deletes a remote branch.")
            if "$" in r or "`" in r or any(ch in r for ch in "*?["):
                g.deny("push-target-dynamic", f"the push target '{r}' is built at run time or is a pattern, so the hook cannot tell whether it is main.", "Write the branch name out.")
            dest = r.split(":")[-1]
            if dest in ("HEAD", "@"):  # HEAD means the branch that is checked out
                dest = branch if branch not in ("", "?") else "main" if branch == "?" else dest
            if re.sub(r"^refs/heads/", "", dest) in prot:
                g.deny("push-to-main", f"pushing to {dest} changes the main line directly. Builders push a branch and open a pull request; only the owner merges.")
        if not refspecs and on_prot:
            g.deny("push-to-main", f"the current branch is {branch}; pushing it changes the main line directly.", "Work on a branch and open a pull request.")
        state["scan_outgoing"] = cwd
    elif sub == "reset" and ("hard" in "".join(long_) or any(x == "--hard" for x in a)):
        g.deny("reset-hard", "git reset --hard throws away uncommitted work (R3).")
    elif sub == "clean" and (("f" in short) or "--force" in long_) and not ({"n"} & short or "--dry-run" in long_):
        g.deny("git-clean", "git clean -f deletes untracked files for good (R3). Run it with -n first and ask the owner.")
    elif sub == "checkout" and ("--" in a or "f" in short or "--force" in long_ or rest == ["."]):
        g.deny("discard-changes", "this checkout can overwrite uncommitted work (R3).")
    elif sub == "restore" and "--staged" not in long_ and "S" not in short and rest:
        g.deny("discard-changes", "git restore on working files discards edits (R3).")
    elif sub == "switch" and ("f" in short or "--discard-changes" in long_ or "--force" in long_):
        g.deny("discard-changes", "git switch -f discards uncommitted work (R3).")
    elif sub == "stash" and rest and rest[0] in ("drop", "clear"):
        g.deny("stash-drop", "dropping a stash cannot be undone (R3).")
    elif sub == "branch" and ("D" in short or (("d" in short or "--delete" in long_) and any(r in prot for r in rest))):
        g.deny("branch-delete", "deleting a branch is irreversible once its commits are unreachable (R3).")
    elif sub == "tag" and ("d" in short or "--delete" in long_):
        g.deny("tag-delete", "deleting a tag changes what a pinned reference means (R3).")
    elif sub in ("filter-branch", "filter-repo", "replace") or (sub == "reflog" and rest and rest[0] in ("expire", "delete")) or (sub == "gc" and any(x.startswith("--prune") for x in a)) or (sub == "update-ref" and "d" in short) or (sub == "prune"):
        g.deny("history-rewrite", f"git {sub} rewrites or discards history (R3).")
    elif sub == "merge" and on_prot:
        g.deny("merge-into-main", f"merging while on {branch} puts changes on the main line. Open a pull request; the owner merges.")
    elif sub == "rebase" and on_prot:
        g.deny("rebase-main", f"rebasing {branch} rewrites the main line.")
    elif sub == "config" and any(re.search(r"core\.hooksPath|core\.fsmonitor|credential\.helper|url\..*insteadof|core\.sshCommand|^alias\.", x, re.I) for x in a):
        g.deny("git-config", "this setting changes which hooks, helpers or hosts git trusts (R2/R5).")
    elif sub == "remote" and rest and rest[0] in ("set-url", "set-head", "rename", "remove", "rm"):
        g.deny("git-remote", "changing a remote can send commits somewhere else (R2).")
    if sub in ("rm", "mv"):
        for t in rest:
            p = g.resolve(t, cwd)
            if p is not None and g.is_protected(p, root, pol):
                g.deny("protected-path", f"git {sub} would change {os.path.relpath(p, root)}, a protected path.")
    if sub in ("checkout", "switch"):
        names = [x for x in rest if x != "--"]
        creating = bool(short & set("bBcC"))
        if names and "--" not in a:
            target = names[0]
            if target in ("-", "@{-1}") or "$" in target:
                state["branch"][cwd] = "?"
            elif creating or any(subprocess.run(["git", "-C", cwd, "show-ref", "--verify", "-q", ref], capture_output=True).returncode == 0
                                 for ref in (f"refs/heads/{target}", f"refs/remotes/origin/{target}")):
                state["branch"][cwd] = target  # a file name, not a branch, leaves the branch unchanged
        elif creating:
            state["branch"][cwd] = "?"
    if sub == "add":
        state["adds"] = True
    if sub == "commit":
        state["commit_cwd"] = cwd
        state["commit_all"] = "a" in short or "--all" in long_
    return


def scan_commit(state, root):
    cwd = state["commit_cwd"]
    ok, f, err = g.run_scanner(["--staged"], cwd)
    if not ok:
        g.deny("scanner-unavailable", err)
    if f:
        g.deny("secret-in-commit", g.describe(f) + ". Nothing was committed.",
               "Unstage it (git restore --staged <file>), remove the value, and tell the owner to revoke it if it was ever real; secrets are the owner's (R5).")
    if state.get("adds") or state.get("commit_all"):
        p = subprocess.run(["git", "-C", cwd, "status", "--porcelain", "-z", "--untracked-files=all"], capture_output=True, text=True)
        files = []
        for entry in p.stdout.split("\0"):
            if len(entry) > 3 and entry[:2] != "D ":
                path = entry[3:]
                if " -> " in path:
                    path = path.split(" -> ")[-1]
                files.append(os.path.join(root, path))
        if files:
            ok, f, err = g.run_scanner(["--paths", *files], cwd)
            if not ok:
                g.deny("scanner-unavailable", err)
            if f:
                g.deny("secret-in-commit", g.describe(f) + " in files this command would add. Nothing was committed.",
                       "Remove the value from the file first; tell the owner to revoke it if it was ever real.")


def scan_outgoing(cwd):
    for base in ("@{u}", "origin/main", "origin/master"):
        p = subprocess.run(["git", "-C", cwd, "rev-parse", "--verify", "-q", base], capture_output=True, text=True)
        if p.returncode == 0:
            d = subprocess.run(["git", "-C", cwd, "diff", f"{base}...HEAD"], capture_output=True, text=True)
            ok, f, err = g.run_scanner(["--diff", "-"], cwd, stdin=d.stdout)
            if not ok:
                g.deny("scanner-unavailable", err)
            if f:
                g.deny("secret-in-push", g.describe(f) + " in commits that would be pushed.", "Do not push. Tell the owner: treat the value as exposed once it leaves this machine.")
            return


def check_segment(sg, cwd, root, pol, state, prev):
    raw = [t for t in sg.tokens if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", t)]
    if raw and os.path.basename(raw[0]) in ("env", "printenv") and not [x for x in raw[1:] if not x.startswith("-")]:
        g.deny("env-dump", "printing the environment can show tokens; agents never see secret values (R5).")
    prog, args = g.program_and_args(sg.tokens)
    if not prog:
        for op, target in sg.redirects:
            check_redirect(op, target, cwd, root, pol)
        return
    short, long_, rest = flags_of(args)
    for op, target in sg.redirects:
        check_redirect(op, target, cwd, root, pol)
    if prog in ("sudo", "doas", "su", "pkexec"):
        g.deny("privilege-escalation", f"{prog} runs a command with higher privileges (R2/R5).")
    if prog in g.UNKNOWN_WRAPPERS:
        g.deny("unrecognised-wrapper", f"{prog} runs another command in a way this hook cannot follow, so what it would run is unknown.", "Write the inner command directly, without the wrapper.")
    if prog in INTERPRETERS and INLINE_FLAG.search(" ".join(a for a in args if a.startswith("-") and not a.startswith("--") or a in ("--eval", "--command"))):
        code = " ".join(args)
        if INLINE_SHELLOUT.search(code):
            g.deny("inline-code", f"{prog} was given inline code that runs another command or deletes files; the hook cannot read what that command is.", "Put the command in the shell where it can be checked, or write a script file and review it.")
    if prog == "cd" and rest:
        p = g.resolve(rest[0], cwd)
        if p:
            state["cwd"] = p
        return
    if prog in ("rm", "unlink", "shred", "rmdir"):
        check_rm(prog, args, cwd, root, pol)
    elif prog == "find" and ("-delete" in args or "-exec" in args or "-execdir" in args):
        if "-delete" in args or any(a in ("rm", "shred", "unlink") for a in args):
            starts = [a for a in args if not a.startswith(("-", "(", "!")) and a not in ("rm", "shred", "unlink", "{}", ";", "+")][:1] or ["."]
            p = g.resolve(starts[0], cwd)
            if p is None or p == root or p.startswith(root.rstrip("/") + "/") or not any(p.startswith(r) and p.rstrip("/") + "/" != r for r in pol["safe_delete_roots"]):
                g.deny("recursive-delete", "find with -delete or -exec rm removes files in bulk (R3) outside the temporary folders.")
    elif prog == "git":
        check_git(args, cwd, root, pol, False, state)
    elif prog == "gh":
        check_gh(args)
    elif prog in ("mkfs", "mkfs.ext4", "mkfs.xfs", "mkswap", "fdisk", "parted", "wipefs") or prog.startswith("mkfs"):
        g.deny("disk-format", f"{prog} changes disk structure (R3).")
    elif prog == "dd" and any(a.startswith("of=/dev/") for a in args):
        g.deny("disk-write", "dd writing to a device overwrites a disk (R3).")
    elif prog in ("chmod", "chown", "chgrp") and (("R" in short or "--recursive" in long_) and any(r in ("/", "~", ".", "..") or r == root for r in rest) or "777" in rest or "a+rwx" in rest):
        g.deny("permissions", f"{prog} here opens or changes access to many files (R2).")
    elif prog in ("shutdown", "reboot", "halt", "poweroff", "init"):
        g.deny("power", f"{prog} stops the machine.")
    elif prog == "crontab" and "l" not in short:
        g.deny("persistence", "changing a crontab sets up something that runs later (R2).")
    elif prog == "export" and "p" in short or prog in ("declare", "typeset") and "x" in short or prog == "set" and not args:
        g.deny("env-dump", "printing the environment can show tokens; agents never see secret values (R5).")
    elif prog in ("echo", "printf", "cat") and any(SECRET_VAR.search(a) for a in args):
        g.deny("print-secret-variable", "this prints a variable whose name looks like a key, token or password; agents never see secret values (R5).")
    elif prog in ("security", "secret-tool", "pass", "gpg") and (rest[:1] in (["find-generic-password"], ["find-internet-password"], ["lookup"], ["show"]) or "d" in short or "--decrypt" in long_):
        g.deny("credential-store", "reading a credential store is an R5 action: the owner does it.")
    elif prog in ("curl", "wget", "http", "https", "xh", "nc", "ncat", "socat", "ssh", "scp", "sftp", "ftp", "rsync") and pol.get("block_external_writes", True):
        check_net(prog, args, short, long_)
    if prog in READERS:
        for t in rest:
            tt = t[1:] if t.startswith("@") else t
            if g.risky_name(tt) and not tt.endswith((".example", ".sample", ".template")):
                g.deny("read-credential-file", f"'{tt}' is a file that normally holds a secret; agents never see secret values (R5).", "Ask the owner to read or move it.")
    if prog in MUTATORS or (prog in ("sed", "perl", "awk") and ("i" in short or any(a.startswith("-i") for a in args))):
        for t in rest:
            p = g.resolve(t, cwd)
            if p is not None and g.is_protected(p, root, pol):
                g.deny("protected-path", f"{prog} would change {os.path.relpath(p, root)}, a protected path.", "Propose the change in a change request; the owner applies it.")
    if prog in SHELLS and sg.piped and prev is not None:
        pprog = g.program_and_args(prev.tokens)[0]
        if pprog in ("curl", "wget", "base64", "http", "xh", "nc"):
            g.deny("download-and-run", f"piping {pprog} output into {prog} runs code nobody has read (R2/R5).")
    stdin_fed = sg.piped or any(op == "<" for op, _ in sg.redirects)
    if stdin_fed and (prog in g.SHELL_NAMES and g.shell_command_string(args) is None or prog in INTERPRETERS and (not rest or rest == ["-"])):
        g.deny("shell-from-stdin", f"{prog} would run script text given on its standard input (a pipe, here-document or here-string), which the hook cannot read.",
               "Write the commands as separate lines in the shell, or save a script file, review it, and run the file.")
    if prog in ("source", ".") and any(t.startswith("/dev/") or t.startswith("/proc/") for t in rest):
        g.deny("shell-from-stdin", f"{prog} would run text from {rest[0]}, which the hook cannot read.")
    if prog == "eval" and any("$(" in t or "`" in t for t in args):
        g.deny("eval-substitution", "eval of a command substitution runs text built at run time.")


def check_redirect(op, target, cwd, root, pol):
    if op != ">" or target in ("/dev/null", "/dev/stdout", "/dev/stderr", "&1", "&2"):
        return
    if target.startswith("/dev/") and not target.startswith("/dev/null"):
        g.deny("device-write", f"redirecting output to {target} writes to a device.")
    p = g.resolve(target, cwd)
    if p is not None and g.is_protected(p, root, pol):
        g.deny("protected-path", f"redirecting output to {os.path.relpath(p, root)} would change a protected path.")
    if g.risky_name(target) and not target.endswith((".example", ".sample", ".template")):
        g.deny("write-credential-file", f"writing to '{target}' stores a secret-bearing file; credentials are the owner's to place (R5).")


def check_net(prog, args, short, long_):
    if prog in ("nc", "ncat", "socat", "ssh", "scp", "sftp", "ftp", "rsync"):
        if prog in ("nc", "ncat", "socat"):
            g.deny("raw-network", f"{prog} opens a raw network connection (R4).")
        if prog in ("ssh", "scp", "sftp", "ftp", "rsync") and any(":" in a and not a.startswith("-") for a in args):
            g.deny("remote-copy", f"{prog} to another machine is an external write (R4).")
        return
    method = None
    for i, a in enumerate(args):
        if a in ("-X", "--request") and i + 1 < len(args):
            method = args[i + 1].upper()
        elif a.startswith("--request="):
            method = a.split("=", 1)[1].upper()
        elif a.startswith("-X") and len(a) > 2:
            method = a[2:].upper()
    body = bool(short & set("dFT")) or any(a.split("=")[0] in ("--data", "--data-raw", "--data-binary", "--data-urlencode", "--data-ascii", "--form", "--form-string", "--upload-file", "--json", "--post-data", "--post-file", "--body-data", "--body-file") for a in args)
    if (method and method not in ("GET", "HEAD", "OPTIONS")) or body or prog in ("http", "https", "xh") and any(a in ("POST", "PUT", "PATCH", "DELETE") for a in args):
        g.deny("external-write", f"{prog} would send data or use a non-GET method. Anything that leaves the system is R4: Preflight Brief and an explicit yes first.")


GH_GROUPS_DENIED = ("pr merge", "repo delete", "repo archive", "repo rename", "repo edit", "repo transfer", "release delete", "secret set", "secret delete",
                    "secret remove", "variable set", "variable delete", "ssh-key", "gpg-key", "workflow run", "workflow enable", "workflow disable",
                    "run rerun", "auth token", "auth refresh", "auth login", "auth logout", "label delete", "ruleset", "alias", "extension", "codespace")
GH_API_FLAGS_WITH_VALUE = {"-X", "--method", "-f", "-F", "--field", "--raw-field", "-H", "--header", "-q", "--jq", "-t", "--template", "--cache", "--hostname", "--input", "-p", "--preview"}
# The only writes through `gh api` that a build session needs: comment on its own pull request, open a pull request, edit a comment.
GH_API_ALLOWED_WRITES = (
    (re.compile(r"^/?repos/[\w.-]+/[\w.-]+/issues/\d+/comments$"), {"POST"}, {"body"}),
    (re.compile(r"^/?repos/[\w.-]+/[\w.-]+/pulls$"), {"POST"}, {"title", "body", "head", "base", "draft"}),
    (re.compile(r"^/?repos/[\w.-]+/[\w.-]+/issues/comments/\d+$"), {"PATCH"}, {"body"}),
)


def gh_parts(args):
    """(command path, remaining args). `-R owner/repo` / `--repo x` may come before the subcommand and is skipped, so
    `gh -R o/r pr merge 5` is read as `pr merge`. `gh api` stops after the word api (its flags come next)."""
    i, path = 0, []
    while i < len(args) and len(path) < 2:
        a = args[i]
        if a in ("-R", "--repo"):
            i += 2
        elif a.startswith("--repo=") or (a.startswith("-R") and len(a) > 2):
            i += 1
        elif a.startswith("-"):
            if path:  # a flag between the group and the verb
                i += 1
            elif a in ("--help", "-h", "--version"):
                return [], []
            else:
                raise g.ParseError(f"gh was given a flag before its subcommand that this hook does not recognise ({a})")
        else:
            path.append(a)
            i += 1
            if path == ["api"]:
                break
    return path, args[i:]


def check_gh(args):
    path, rest = gh_parts(args)
    s2 = " ".join(path[:2])
    if path[:1] == ["api"]:
        return check_gh_api(rest)
    for d in GH_GROUPS_DENIED:
        if s2 == d or s2.startswith(d + " "):
            if d == "pr merge":
                g.deny("merge-pr", "merging a pull request is the owner's decision; builders open a PR and stop.")
            g.deny("gh-privileged", f"'gh {s2}' changes repository settings, secrets or tooling, runs the poster, or prints a token. These are R2 to R5 actions for the owner.")


def check_gh_api(rest):
    method, fields, positional, has_input, i = None, [], [], False, 0
    while i < len(rest):
        a = rest[i]
        if a in ("-X", "--method"):
            method = rest[i + 1] if i + 1 < len(rest) else ""
            i += 2
        elif a.startswith("--method="):
            method, i = a.split("=", 1)[1], i + 1
        elif a.startswith("-X") and len(a) > 2:
            method, i = a[2:].lstrip("="), i + 1
        elif a in ("-f", "-F", "--field", "--raw-field"):
            fields.append(rest[i + 1] if i + 1 < len(rest) else ""); i += 2
        elif a.startswith(("--field=", "--raw-field=")):
            fields.append(a.split("=", 1)[1]); i += 1
        elif len(a) > 2 and a[:2] in ("-f", "-F") and not a.startswith("--"):
            fields.append(a[2:]); i += 1
        elif a == "--input" or a.startswith("--input="):
            has_input = True
            i += 2 if a == "--input" else 1
        elif a in GH_API_FLAGS_WITH_VALUE:
            i += 2
        elif a.startswith("-"):
            i += 1
        else:
            positional.append(a); i += 1
    m = method.upper() if method is not None else None
    if m is not None and (not m or "$" in m or m not in ("GET", "HEAD", "POST", "PUT", "PATCH", "DELETE")):
        g.deny("gh-api-write", f"the HTTP method '{method}' is not a plain GET, so it is treated as a write (R2 to R4).")
    writes = (m not in (None, "GET", "HEAD")) or (m is None and (fields or has_input))
    if not writes or (m == "GET" and not has_input):
        return
    eff = m or "POST"
    names = {f.split("=", 1)[0] for f in fields}
    if not has_input and len(positional) == 1 and all(not f.startswith("$") for f in fields):
        for rx, methods, allowed in GH_API_ALLOWED_WRITES:
            if rx.match(positional[0]) and eff in methods and names <= allowed and fields:
                return
    g.deny("gh-api-write", f"a {eff} call to the GitHub API changes remote state (R2 to R4). Only these writes are allowed: comment on a pull request, open a pull request, edit a comment, each with only its own fields.",
           "Anything else (merging, dispatching a workflow, settings, labels) is the owner's decision.")


MCP_PRIVILEGED = re.compile(r"(?i)^mcp__.*(merge|delete|dispatch|workflow|ruleset|branch_protection|protect|secret|force|transfer|archive)")


def main():
    data = g.read_input()
    name = data.get("tool_name")
    if isinstance(name, str) and MCP_PRIVILEGED.search(name):
        g.deny("mcp-privileged", f"the tool {name} looks like it merges, deletes, dispatches a workflow or changes settings. Those are the owner's decisions (R2 to R5), and a connector tool would bypass the shell rules.", "Ask the owner.")
    if name not in (None, "Bash"):
        sys.exit(0)
    cmd = (data.get("tool_input") or {}).get("command", "")
    if not isinstance(cmd, str) or not cmd.strip():
        sys.exit(0)
    cwd = data.get("cwd") or os.getcwd()
    try:
        pol = g.load_policy()
    except RuntimeError as e:
        g.deny("policy-unreadable", str(e))
    if FORK_BOMB.search(cmd):
        g.deny("fork-bomb", "this command would exhaust the machine.")
    try:
        segs = g.all_segments(cmd)
    except g.ParseError as e:
        g.deny("unparseable", f"the hook could not read this command safely ({e}).", "Split it into simpler commands.")
    root = g.repo_root(cwd)
    state = {"cwd": cwd}
    prev = None
    try:
        for sg in segs:
            check_segment(sg, state["cwd"], root, pol, state, prev)
            prev = sg
    except g.ParseError as e:
        g.deny("unparseable", f"the hook could not read this command safely ({e}).", "Split it into simpler commands, or write names out in full.")
    if "commit_cwd" in state:
        scan_commit(state, root)
    if "scan_outgoing" in state:
        scan_outgoing(state["scan_outgoing"])
    sys.exit(0)


if __name__ == "__main__":
    g.run(main)
