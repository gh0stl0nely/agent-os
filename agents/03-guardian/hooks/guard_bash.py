#!/usr/bin/env python3
"""PreToolUse hook for the Bash tool. PROPOSED by the Guardian; the owner installs it (see README.md).

Reads the tool call as JSON on stdin. Exit 0 with no output = no objection (it never approves anything).
Exit 2 with a reason on stderr = blocked. It reads the command; it never runs it.

Blocks: destructive commands, force pushes and pushes to main or to any remote that is not already configured, merging,
secret-looking content in a commit or push, reading or printing credentials (any program given a credential path, not a
list of known readers), publishing a local file through gh, download-and-run, external writes by curl, privilege
escalation, edits to protected paths (including those made by git apply, git am and patch). Rules and paths come from
policy.json. See README.md, "Known limits", for what this does not catch.
"""
import os
import re
import subprocess
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import guard_lib as g  # noqa: E402

SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "python", "python3", "node", "perl", "ruby", "php"}
MUTATORS = {"rm", "mv", "cp", "tee", "truncate", "install", "ln", "chmod", "chown", "touch", "patch", "shred", "unlink", "rmdir", "mkdir", "dd", "rsync",
            "ed", "ex", "vi", "vim", "nvim", "nano", "pico", "emacs", "micro", "sponge"}
SECRET_VAR = re.compile(r"\$\{?[A-Za-z0-9_]*(?:KEY|TOKEN|SECRET|PASSW(?:OR)?D|CREDENTIAL|PRIVATE)[A-Za-z0-9_]*\}?", re.I)
INTERPRETERS = {"python", "python3", "python2", "node", "nodejs", "perl", "ruby", "php", "deno", "bun", "lua"}
INLINE_FLAG = re.compile(r"(?:^|\s)(?:-[A-Za-z]*[ceE]|--eval|--command)\b")
INLINE_SHELLOUT = re.compile(r"os\.system|os\.popen|os\.exec|os\.spawn|subprocess|popen|\bexec\s*\(|child_process|\bsystem\s*\(|\bexecSync|spawnSync|shutil\.rmtree|os\.remove|os\.unlink|\bunlink\s*\(|rmtree|`[^`]+`|Deno\.run|Deno\.Command|Bun\.spawn|io\.popen|\bqx\b")
# Programs that only NAME a path (or delete it) and never read what is inside. Everything else that is given a credential path,
# as an argument or as a `<` target, is refused: the list is of the harmless ones, not of the readers.
NAME_ONLY = {"ls", "dir", "stat", "test", "[", "[[", "echo", "printf", "rm", "unlink", "shred", "rmdir", "touch", "mkdir", "chmod", "chown", "chgrp",
             "pwd", "cd", "basename", "dirname", "realpath", "readlink", "which", "type", "true", "false", "git", "gh", "unset"}
# Git subcommands that print the contents of files or of commits; a credential path given to one of them is a read.
GIT_READ_SUBS = {"show", "cat-file", "diff", "log", "blame", "annotate", "grep", "archive", "difftool", "whatchanged", "format-patch", "diff-tree",
                 "diff-index", "diff-files", "fast-export", "show-branch", "range-diff", "bundle", "checkout-index"}
# Environment settings that redirect where git sends data or which program it runs.
ENV_DANGER = re.compile(r"GIT_(?:SSH|SSH_COMMAND|PROXY_COMMAND|ASKPASS|CONFIG_COUNT|CONFIG_PARAMETERS|CONFIG_GLOBAL|CONFIG_SYSTEM|CONFIG_KEY_\d+|CONFIG_VALUE_\d+|DIR|WORK_TREE|EXEC_PATH|EXTERNAL_DIFF|TEMPLATE_DIR)=.*|(?:LD_PRELOAD|BASH_ENV)=.*")
INLINE_CRED = re.compile(r"(?i)\.env\b(?!\.(?:example|sample|template|dist))|id_(?:rsa|dsa|ecdsa|ed25519)|\.ssh\b|\.aws\b|\.netrc|\.pypirc|\.npmrc|\.git-credentials|\.config/gh|hosts\.yml|\.pem\b|\.p12\b|\.pfx\b|\.keystore|credentials|service-account|/etc/shadow")
# Environment names `printenv NAME` may print. Anything else may be a token (round 4: an allow-list, not a list of bad names).
SAFE_ENV = {"HOME", "PATH", "USER", "LOGNAME", "SHELL", "PWD", "LANG", "LC_ALL", "TERM", "TMPDIR", "EDITOR", "HOSTNAME", "TZ", "PYTHONDONTWRITEBYTECODE", "CLAUDE_PROJECT_DIR"}
INLINE_ENV = re.compile(r"(?i)os\.environ|os\.getenv|\benviron\b|process\.env|\bENV\s*\[|\$ENV\s*\{|\bgetenv\s*\(|Deno\.env|Bun\.env|System\.getenv|ENV\.fetch|\bos\.Getenv")
INDIRECT_VAR = re.compile(r"\$\{!([A-Za-z_][A-Za-z0-9_]*)([*@])?\}")
SECRETY_PREFIX = re.compile(r"(?i)^(?:|GH|GITHUB|AWS|AZURE|GOOGLE|GCP|ANTHROPIC|OPENAI|NPM|PYPI|SLACK|STRIPE|SQUARE|NOTION|THREADS|TOKEN|KEY|SECRET|PASS|API|AUTH|CRED|PRIVATE|SSH)")
AWK_SHELLOUT = re.compile(r"\bsystem\s*\(|\|\s*getline|\|&|print[^;}]*\|\s*\"?\s*(?:sh|bash|zsh|cat|tee|mail)\b|\"\s*\|\s*getline")
# Programs that read whole folders; if one is pointed at a folder that holds a credential file, it reads the credential.
RECURSIVE_ALWAYS = {"tar", "bsdtar", "rg", "ag", "7z", "7za", "7zr", "cpio"}
GREP_FAMILY = {"grep", "egrep", "fgrep", "rgrep", "zgrep"}
EDITORS = {"ed", "ex", "vi", "vim", "nvim", "view", "nano", "pico", "emacs", "micro", "sponge"}
SERVER_PROGS = {"http-server", "live-server", "serve", "ngrok", "cloudflared", "localtunnel", "lt", "miniserve", "httpd", "nginx", "caddy", "simplehttpserver"}
CONTAINER_PROGS = {"docker", "podman", "nerdctl", "docker-compose", "podman-compose"}
CONTAINER_RISKY = {"run", "exec", "build", "buildx", "compose", "create", "start", "cp", "push", "login", "save", "load", "import", "commit", "up"}
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


def known_remotes(cwd):
    p = subprocess.run(["git", "-C", cwd, "remote"], capture_output=True, text=True)
    return set(p.stdout.split()) if p.returncode == 0 else set()


APPLY_READ_ONLY = {"--check", "--stat", "--numstat", "--summary"}
AM_STATE = {"--continue", "-r", "--resolved", "--skip", "--abort", "--quit", "--show-current-patch", "--retry"}
PATCH_SHORT_VAL = set("pdiorBVzFDYgx")
PATCH_LONG_VAL = {"--strip", "--directory", "--input", "--output", "--reject-file", "--prefix", "--suffix", "--basename-prefix", "--fuzz", "--ifdef", "--version-control", "--read-only", "--group", "--debug"}
MAX_PATCH = 8_000_000


def read_patch_text(token, cwd):
    """The text of the patch file `token` names. A file the hook cannot read (missing, a pipe, built at run time) is refused,
    because what it would change is then unknown."""
    p = g.resolve(token, cwd)
    if p is None:
        g.deny("patch-unreadable", f"the patch file '{token[:40]}' is named by something built at run time, so the hook cannot see which files it changes.", "Write the file name out.")
    try:
        files = sorted(os.path.join(p, f) for f in os.listdir(p))[:200] if os.path.isdir(p) else [p]
        text = ""
        for f in files:
            with open(f, "rb") as fh:
                chunk = fh.read(MAX_PATCH + 1)
            if len(chunk) > MAX_PATCH:
                g.deny("patch-unreadable", f"the patch file '{os.path.basename(f)}' is too large to check.")
            text += chunk.decode("utf-8", "replace") + "\n"
    except OSError:
        g.deny("patch-unreadable", f"the patch file '{token[:60]}' could not be read, so the hook cannot see which files it changes.",
               "Create the patch file in its own step first (it must exist before it is applied), then apply it.")
    return text


def check_patch(kind, args, sg, cwd, root, pol):
    """`git apply`, `git am` and `patch` write files named INSIDE the patch, not on the command line. Read the patch (never run
    it) and refuse when any file it touches is protected or holds credentials, at any strip level (-p)."""
    base, positional, i, src, extra_out = cwd, [], 0, None, []
    flags = set(args)
    if kind == "apply" and flags & APPLY_READ_ONLY and "--apply" not in flags:
        return
    if kind == "am" and flags & AM_STATE:
        return
    if kind == "patch" and ("--dry-run" in flags or "--check" in flags):
        return
    while i < len(args):
        a = args[i]
        if a == "--":
            positional += args[i + 1:]
            break
        val = None
        if kind == "patch":
            if a.startswith("--") and a.split("=")[0] in PATCH_LONG_VAL:
                name = a.split("=")[0]
                val = a.split("=", 1)[1] if "=" in a else (args[i + 1] if i + 1 < len(args) else ""); i += 1 if "=" in a else 2
                if name in ("--directory",):
                    base = g.resolve(val, cwd) or g.deny("patch-unreadable", "the patch directory is built at run time.")
                elif name == "--input":
                    src = val
                elif name in ("--output", "--reject-file"):
                    extra_out.append(val)
                continue
            if re.fullmatch(r"-[A-Za-z]+", a) and a[1] in PATCH_SHORT_VAL and not a.startswith("--"):
                flag = a[1]
                val = a[2:] if len(a) > 2 else (args[i + 1] if i + 1 < len(args) else ""); i += 1 if len(a) > 2 else 2
                if flag == "d":
                    base = g.resolve(val, cwd) or g.deny("patch-unreadable", "the patch directory is built at run time.")
                elif flag == "i":
                    src = val
                elif flag in ("o", "r"):
                    extra_out.append(val)
                continue
        else:
            if a.startswith("--directory"):
                val = a.split("=", 1)[1] if "=" in a else (args[i + 1] if i + 1 < len(args) else ""); i += 1 if "=" in a else 2
                base = g.resolve(os.path.join(base, val), cwd) or g.deny("patch-unreadable", "the patch directory is built at run time.")
                continue
        if a.startswith("-") and a != "-":
            i += 1
            continue
        positional.append(a)
        i += 1
    orig = None
    if kind == "patch":
        if src is None:
            redirected = [t for op, t in sg.redirects if op == "<"]
            if redirected:
                src = redirected[0]
                orig = positional[0] if positional else None
            elif len(positional) >= 2:
                orig, src = positional[0], positional[1]
            else:
                g.deny("patch-unreadable", "patch would read its instructions from a pipe or the terminal, so the hook cannot see which files it changes.", "Save the patch to a file first, then run: patch -p1 < file.")
        else:
            orig = positional[0] if positional else None
        texts = [read_patch_text(src, cwd)]
        for t in [orig] + extra_out:
            if t:
                pth = g.resolve(t, base)
                if pth is None or g.is_protected(pth, root, pol) or (g.risky_name(pth) and not pth.endswith(g.EXAMPLE_SUFFIXES)) or g.git_config_file(pth):
                    g.deny("patch-protected-path", f"patch would write {t}, a protected path or a file that holds credentials.", "Propose the change in a change request; the owner applies it.")
    else:
        files = [t for t in positional if t != "-"]
        if not files or "-" in positional:
            redirected = [t for op, t in sg.redirects if op == "<"]
            if redirected:
                files += redirected[:1]
            else:
                g.deny("patch-unreadable", f"git {kind} would read the patch from a pipe or the terminal, so the hook cannot see which files it changes.", f"Save the patch to a file first, then run: git {kind} file.")
        texts = [read_patch_text(t, cwd) for t in files]
    for text in texts:
        hit = g.patch_target_hits(g.patch_paths(text), base, root, pol)
        if hit:
            kind_, where = hit
            if kind_ == "protected":
                g.deny("patch-protected-path", f"this patch changes {where}, a protected path (the file names are inside the patch).", "Propose the change in agent-system/change-requests/ or ask the owner.")
            g.deny("patch-credential-file", f"this patch writes {where}, a file that holds credentials or git settings; those are the owner's (R5).")


def check_publish_file(v, cwd, root, pol, via):
    """A file that `gh` would post (a comment body, a pull request body, a field value read with @). The repository is public,
    so only a scanner-clean file inside the working tree or the temporary folders may be published, never a credential file."""
    if v == "-":
        return
    p = g.resolve(v, cwd)
    if p is None or "$" in re.sub(r"^\$\{?HOME\}?", "", v) or "`" in v:
        g.deny("publish-file", f"{via} names the file by a path built at run time ({v[:40]}), so the hook cannot tell what would be posted publicly.", "Write the path out in full.")
    real = os.path.realpath(p)
    for q in (p, real):
        if (g.risky_name(q) and not q.endswith(g.EXAMPLE_SUFFIXES)) or g.is_protected(q, root, pol) or g.is_protected(q, os.path.realpath(root), pol) or g.git_config_file(q):
            g.deny("publish-credential-file", f"{via} would post '{os.path.basename(q)}' into a public place: it is a credential, settings or protected file (R4/R5).",
                   "Put the text you want to post inline (--body 'text', or -f body=text for the API).")
    roots = [os.path.realpath(root)] + [os.path.realpath(r) for r in pol.get("publish_roots", [])]
    if not any(real == r.rstrip("/") or real.startswith(r.rstrip("/") + "/") for r in roots):
        g.deny("publish-outside-workspace", f"{via} would post '{v[:60]}', a file outside this repository and the temporary folders; this repository is public (R4).",
               "Copy the text you mean to post into a file under /tmp, or write it inline.")
    if os.path.isfile(real):
        ok, f, err = g.run_scanner(["--paths", real], cwd)
        if not ok:
            g.deny("scanner-unavailable", err)
        f = [x for x in f if x.get("rule") != "plan-handles-secret"]
        if f:
            g.deny("secret-in-publish", g.describe(f) + f" in the file {via} would post publicly.", "Remove the value first; tell the owner to revoke it if it was ever real.")


def check_write_target(prog, t, cwd, root, pol, how="write"):
    """A file `prog` is about to create or overwrite. Protected paths (symlinks followed), git settings files and
    credential files are refused."""
    p = g.resolve(t, cwd)
    if p is None:
        return
    if g.is_protected(p, root, pol):
        g.deny("protected-path", f"{prog} would {how} {os.path.relpath(p, root)}, a protected path.", "Propose the change in a change request; the owner applies it.")
    if g.git_config_file(p):
        g.deny("git-config", f"{prog} would {how} {t}, a git settings file that can redirect where pushes go (R2/R4).")
    real = os.path.realpath(p)
    if (g.risky_name(p) or g.risky_name(real)) and not p.endswith(g.EXAMPLE_SUFFIXES):
        g.deny("write-credential-file", f"{prog} would {how} '{t}', a file that normally holds a secret; credentials are the owner's to place (R5).")


def option_values(args, shorts=(), longs=()):
    """Values given to the options in `shorts` (-o X, -oX) and `longs` (--output X, --output=X)."""
    out, i = [], 0
    while i < len(args):
        a = args[i]
        if a in shorts or a in longs:
            if i + 1 < len(args):
                out.append(args[i + 1])
            i += 2
            continue
        for l in longs:
            if a.startswith(l + "="):
                out.append(a.split("=", 1)[1])
        for sh in shorts:
            if len(sh) == 2 and a.startswith(sh) and len(a) > 2 and not a.startswith("--"):
                out.append(a[2:])
        i += 1
    return out


def check_recursive_credentials(prog, args, short, long_, rest, cwd):
    """tar, cp -r, grep -r, find, zip -r, rsync -a ... pointed at a folder: refuse when the folder is, or holds, a credential
    file, or is the home folder (which holds ~/.ssh). The folder listing is read; no file is opened."""
    if prog in RECURSIVE_ALWAYS:
        on = True
    elif prog == "find":
        # find lists names; it reads contents only through an action. A bulk rm/-delete has its own rule.
        acts = {"-exec", "-execdir", "-ok", "-okdir", "-fprint", "-fprint0", "-fprintf", "-fls"}
        i_rm = any(a in ("-exec", "-execdir") and j + 1 < len(args) and os.path.basename(args[j + 1]) == "rm" for j, a in enumerate(args))
        on = bool(acts & set(args)) and "-delete" not in args and not i_rm
    elif prog == "zip":
        on = bool(short & set("rR")) or "--recurse-paths" in long_
    elif prog in ("cp", "rsync", "scp"):
        on = bool(short & set("rRa")) or bool(long_ & {"--recursive", "--archive"})
    elif prog in GREP_FAMILY:
        on = bool(short & set("rR")) or bool(long_ & {"--recursive", "--dereference-recursive"}) or any(a.startswith("--directories=recurse") for a in args)
    else:
        return
    if not on:
        return
    operands = rest[1:] if prog in GREP_FAMILY or prog in ("rg", "ag") else rest
    dirs = []
    for t in args:
        if t.startswith("-") and t != "-":
            continue
        p = g.resolve(t, cwd)
        if p and os.path.isdir(p):
            dirs.append((t, p))
    if prog in GREP_FAMILY or prog in ("rg", "ag"):
        if not operands:
            dirs.append((".", cwd))
    elif prog == "find":
        first = [a for a in args if not a.startswith(("-", "(", "!"))][:1]
        if not first:
            dirs.append((".", cwd))
    for t, p in dirs:
        if g.home_or_above(p):
            g.deny("read-credential-dir", f"{prog} would read every file under '{t}', which is the home folder (or contains it), and ~/.ssh, ~/.aws and ~/.config/gh are in there; agents never see secret values (R5).", "Name the project folder you mean.")
        hit = g.credential_below(p)
        if hit:
            g.deny("read-credential-dir", f"{prog} would read every file under '{t}', and '{os.path.relpath(hit, p)}' inside it normally holds a secret; agents never see secret values (R5).", "Name the files you need, or ask the owner to move the credential file out.")


def scan_message_file(path, cwd, via):
    p = g.resolve(path, cwd)
    if p is None or not os.path.isfile(p):
        return
    ok, f, err = g.run_scanner(["--paths", p], cwd)
    if not ok:
        g.deny("scanner-unavailable", err)
    f = [x for x in f if x.get("rule") != "plan-handles-secret"]
    if f:
        g.deny("secret-in-message", g.describe(f) + f" in the file {via} would use as a message, which becomes public in this repository.", "Remove the value first; tell the owner to revoke it if it was ever real.")


def check_more(prog, args, short, long_, rest, sg, cwd, root, pol):
    """Round 4: the review's shapes that were neither blocked nor listed."""
    # printing the environment or variables (a name outside a short safe list may be a token)
    if prog == "printenv":
        bad = [a for a in rest if a not in SAFE_ENV]
        if bad:
            g.deny("print-secret-variable", f"printenv {bad[0][:30]} prints an environment variable that may be a token; only {', '.join(sorted(SAFE_ENV)[:6])}... are allowed. Agents never see secret values (R5).")
    for t in sg.tokens:
        for m in INDIRECT_VAR.finditer(t):
            if not m.group(2) or SECRETY_PREFIX.match(m.group(1)):
                g.deny("print-secret-variable", f"'{m.group(0)[:30]}' reads variables by name (indirect expansion) or lists those with a key-like prefix; agents never see secret values (R5).")
    if prog in ("declare", "typeset", "readonly", "local") and ("p" in short or "x" in short or not args) or prog == "export" and ("p" in short or not args):
        g.deny("env-dump", f"{prog} would print variables, which can include tokens; agents never see secret values (R5).")
    if prog in ("awk", "gawk", "mawk", "nawk") and any(re.search(r"\bENVIRON\b", t) for t in args):
        g.deny("print-secret-variable", "awk's ENVIRON array holds every environment variable, tokens included; agents never see secret values (R5).")
    # reading the whole of a folder that holds a credential
    check_recursive_credentials(prog, args, short, long_, rest, cwd)
    # writers that reach a protected path without a redirect
    if prog == "dd":
        for a in args:
            if a.startswith("of="):
                check_write_target(prog, a[3:], cwd, root, pol)
    elif prog == "curl":
        for v in option_values(args, ("-o",), ("--output",)) + option_values(args, (), ("--output-dir",)):
            check_write_target(prog, v, cwd, root, pol)
        if (short & set("OJ") or "--remote-name" in long_) and (g.is_protected(cwd, root, pol)):
            g.deny("protected-path", "curl -O would save a file into the current folder, which is a protected path.")
    elif prog == "wget":
        for v in option_values(args, ("-O", "-o", "-a", "-P"), ("--output-document", "--output-file", "--append-output", "--directory-prefix")):
            check_write_target(prog, v, cwd, root, pol)
        if g.is_protected(cwd, root, pol):
            g.deny("protected-path", "wget would save a file into the current folder, which is a protected path.")
    elif prog in ("tar", "bsdtar") and ("x" in short or long_ & {"--extract", "--get"} or "x" in (args[0] if args and not args[0].startswith("-") else "")):
        for v in option_values(args, ("-C",), ("--directory",)):
            check_write_target(prog, v, cwd, root, pol, "extract into")
        if g.is_protected(cwd, root, pol) and not option_values(args, ("-C",), ("--directory",)):
            g.deny("protected-path", f"{prog} would extract into the current folder, which is a protected path.")
    elif prog == "unzip":
        for v in option_values(args, ("-d",), ()):
            check_write_target(prog, v, cwd, root, pol, "extract into")
    elif prog == "rsync" and any(a.startswith("--delete") or a in ("--del", "--remove-source-files") for a in args):
        dest = rest[-1] if rest else ""
        p = g.resolve(dest, cwd)
        if p is None or not any(p.startswith(r) and p.rstrip("/") + "/" != r for r in pol["safe_delete_roots"]):
            g.deny("recursive-delete", "rsync --delete removes files at the destination that are not at the source (R3), outside the temporary folders.", "Delete explicitly, below /tmp, or write a Preflight Brief with a backup.")
    elif prog == "shred":
        for t in rest:
            p = g.resolve(t, cwd)
            if p is None or not any(p.startswith(r) and p.rstrip("/") + "/" != r for r in pol["safe_delete_roots"]):
                g.deny("irreversible-overwrite", f"shred overwrites '{t}' so it cannot be recovered (R3), outside the temporary folders.", "Write a Preflight Brief with a backup and rollback step.")
    elif prog in ("awk", "gawk", "mawk", "nawk") and AWK_SHELLOUT.search(" ".join(args)):
        g.deny("inline-code", f"{prog} was given a program that runs another command; the hook cannot read what that command is.", "Put the command in the shell where it can be checked.")
    elif prog in ("ssh", "mosh", "telnet", "ssh-copy-id", "ssh-add", "ssh-keygen"):
        g.deny("remote-shell", f"{prog} opens a session on another machine, or creates or loads keys: it can run any command (including on this machine, via localhost) and touches credentials (R4/R5).", "The owner does this.")
    elif prog in CONTAINER_PROGS and rest[:1] and rest[0] in CONTAINER_RISKY:
        g.deny("container-run", f"{prog} {rest[0]} runs or builds code the hook cannot read, usually with the working folder mounted (R2/R5).", "Run the program directly where it can be checked.")
    elif prog in SERVER_PROGS or (prog.startswith("python") and any(a in ("http.server", "SimpleHTTPServer", "pyftpdlib", "smtpd") for a in args)) or (prog == "php" and "S" in short) or (prog == "ruby" and "httpd" in " ".join(args)):
        g.deny("serve-files", f"{prog} would serve the working folder to the network (or open a tunnel to it), which can expose files with secrets (R4/R5).", "Not from an agent session.")
    elif prog in ("pip", "pip3", "pipx", "uv", "uvx", "poetry", "npm", "npx", "pnpm", "yarn", "bun", "bunx", "deno") or (prog.startswith("python") and "pip" in args):
        check_installers(prog, args)
    elif prog == "cargo" and "install" in rest and "--git" in long_:
        g.deny("install-from-url", "cargo install --git builds and installs code fetched from a URL nobody has read (R2).")


URLISH = re.compile(r"(?i)^(?:https?|ftp|git|ssh|file)://|^git\+|^(?:github|gitlab|bitbucket|gist):|^[\w.-]+/[\w.-]+(?:#.*)?$|^[\w.-]+@[\w.-]+:")


def check_installers(prog, args):
    """Installing from a URL, a git address or an `owner/repo` shorthand fetches code nobody has read (R2). Plain registry
    names are allowed (see README: the package's own install scripts still run)."""
    words = [a for a in args if not a.startswith("-") or a.startswith(("-r", "-e", "-c", "--requirement", "--editable", "--index-url", "--extra-index-url", "--find-links", "--git", "-i", "-f"))]
    for i, a in enumerate(args):
        v = a.split("=", 1)[1] if "=" in a and a.startswith("--") else None
        if a in ("-i", "-f", "--index-url", "--extra-index-url", "--find-links", "-r", "--requirement", "-e", "--editable") and i + 1 < len(args):
            v = args[i + 1]
        if v is not None and URLISH.search(v) and not v.startswith(("./", "../", "/")):
            g.deny("install-from-url", f"{prog} would fetch from '{v[:50]}', an address or repository that is not the package registry: code nobody has read (R2).", "Ask the owner to vet it with the skill-vetting skill, then install it.")
    verbs = {"install", "i", "add", "ci", "run", "dlx", "exec", "x", "tool", "global", "update", "upgrade"}
    if prog in ("pip", "pip3", "pipx", "uv", "uvx", "poetry", "npm", "pnpm", "yarn", "bun", "bunx", "npx", "deno") or "pip" in args:
        for a in args:
            if a.startswith("-"):
                continue
            if a not in verbs and URLISH.search(a) and not a.startswith(("./", "../", "/")):
                g.deny("install-from-url", f"{prog} would fetch and run '{a[:50]}', an address, git repository or owner/repo shorthand: code nobody has read (R2).", "Ask the owner to vet it with the skill-vetting skill, then install it.")


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


def check_git(args, cwd, root, pol, sg, state):
    cdir, sub, a, cvals = git_parts(args)
    if any(re.match(r"(?i)(alias\.|core\.(hookspath|fsmonitor|sshcommand|pager|editor)|credential\.|url\.|http\.|include|protocol\.|remote\.|push\.|safe\.|submodule\.)", v) for v in cvals):
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
    if sub in GIT_READ_SUBS:
        for t in a:
            hit = g.credential_in_arg(t, cwd)
            if hit:
                g.deny("read-credential-file", f"git {sub} would print '{hit}', a file that normally holds a secret, from the working tree or from history; agents never see secret values (R5).", "Ask the owner to read it.")
    if sub in ("apply", "am"):
        check_patch(sub, a, sg, cwd, root, pol)
    if sub == "credential" or (sub == "config" and any(x.startswith("credential") for x in a) and False):
        g.deny("git-credential", "git credential fill/approve/reject reads or stores the credential helper's secrets; agents never see secret values (R5).", "Ask the owner.")
    if sub in ("commit", "tag"):  # a message read from a file becomes public text
        for fv in option_values(a, shorts=("-F",), longs=("--file",)):
            if fv != "-":
                scan_message_file(fv, cwd, f"git {sub} -F")
    on_known_prot = branch in prot
    if on_known_prot:
        if sub in ("commit", "cherry-pick", "revert", "am") and not (sub == "am" and set(a) & AM_STATE):
            g.deny("local-main-change", f"git {sub} while on {branch} adds commits straight to the main line. Work on a branch and open a pull request.", "git switch -c build/<role> first.")
        if sub == "pull" and len(rest) >= 2:
            g.deny("local-main-change", f"git pull from '{rest[0]} {rest[1]}' while on {branch} merges another branch into the main line. A plain `git pull` is fine.", "Work on a branch and open a pull request.")
        if sub == "reset" and rest and not {"--hard"} & set(a):
            g.deny("local-main-change", f"git reset to another commit while on {branch} moves the main line.", "Work on a branch.")
    if sub == "update-ref" and "d" not in short:
        for t in rest:
            if re.sub(r"^refs/heads/", "", t) in prot or re.sub(r"^refs/heads/", "", t) in pol.get("protected_push_refs", []):
                g.deny("local-main-change", f"git update-ref {t} moves a protected branch without a merge.")
    if sub == "branch" and (short & set("fmMcC") or long_ & {"--force", "--move", "--copy"}) and any(re.sub(r"^refs/heads/", "", r) in prot for r in rest):
        g.deny("local-main-change", "forcing, moving or copying over a protected branch name moves the main line.")
    if sub == "fetch":
        for r in rest[1:]:
            if ":" in r and re.sub(r"^\+?(?:refs/heads/)?", "", r.split(":")[-1]) in prot:
                g.deny("local-main-change", f"git fetch {r} overwrites a protected local branch.")
    if sub == "worktree" and rest and rest[0] in ("remove", "prune") and (short & set("f") or "--force" in long_):
        g.deny("worktree-force-remove", "git worktree remove --force deletes a working folder with uncommitted work (R3).")
    if sub == "push":
        if long_ & {"--repo", "--receive-pack", "--exec"}:
            g.deny("push-to-url", "--repo, --receive-pack and --exec change where a push goes or what runs on the way (R4).", "Push to the configured remote by name.")
        known = known_remotes(cwd)
        push_args = []
        skip = False
        for x in a:  # drop the value of -o / --push-option so it is not mistaken for the remote
            if skip:
                skip = False
            elif x in ("-o", "--push-option"):
                skip = True
            else:
                push_args.append(x)
        rest = flags_of(push_args)[2]
        if rest:
            for rem in g.brace_expand(rest[0]):
                if "$" in rem or "`" in rem or any(ch in rem for ch in "*?[{"):
                    g.deny("push-target-dynamic", f"the remote '{rem}' is built at run time or is a pattern, so the hook cannot tell where the push goes.", "Write the remote name out.")
                if rem not in known:
                    if re.search(r"[:/@\\]|^[.~]", rem):
                        g.deny("push-to-url", f"'{rem}' is an address, not a configured remote; a push there sends your commits to a place the owner never set up (R4).", "Push to the configured remote (origin) by name. Adding a remote is the owner's job.")
                    g.deny("push-unknown-remote", f"'{rem}' is not a remote this repository has configured (known: {', '.join(sorted(known)) or 'none'}).", "Push to a configured remote by name.")
        if long_ & {"--force", "--force-with-lease", "--force-if-includes", "--mirror", "--delete", "--prune"} or "f" in short or "d" in short:
            g.deny("force-push", "a forced or deleting push rewrites or removes history on the remote (R3, default deny).", "Ask the owner; use a normal push or a new branch.")
        if "--all" in long_:
            g.deny("push-all", "git push --all pushes every local branch, including main.", "Push the one branch you built, by name.")
        refspecs = []
        for r0 in (rest[1:] if len(rest) > 1 else []):
            refspecs += g.brace_expand(r0)
        for r in refspecs:
            if r.startswith("+"):
                g.deny("force-push", f"refspec '{r}' forces the update.")
            if r.startswith(":"):
                g.deny("delete-remote-ref", f"refspec '{r}' deletes a remote branch.")
            if "$" in r or "`" in r or any(ch in r for ch in "*?[{"):
                g.deny("push-target-dynamic", f"the push target '{r}' is built at run time or is a pattern, so the hook cannot tell whether it is main.", "Write the branch name out.")
            dest = r.split(":")[-1]
            if dest in ("HEAD", "@"):  # HEAD means the branch that is checked out
                dest = branch if branch not in ("", "?") else "main" if branch == "?" else dest
            if re.sub(r"^refs/heads/", "", dest) in prot:
                g.deny("push-to-main", f"pushing to {dest} changes the main line directly. Builders push a branch and open a pull request; only the owner merges.")
            if re.sub(r"^refs/heads/", "", dest) in pol.get("protected_push_refs", []):
                g.deny("push-to-protected-ref", f"pushing to {dest} would change the poster's claim state, which the poster gate owns; a wrong value there can cause a double post (R4).", "Use agents/03-guardian/poster-state/poster_gate.py, or ask the owner.")
        if not refspecs and on_prot:
            g.deny("push-to-main", f"the current branch is {branch}; pushing it changes the main line directly.", "Work on a branch and open a pull request.")
        if not refspecs and branch in pol.get("protected_push_refs", []):
            g.deny("push-to-protected-ref", f"the current branch is {branch}, the poster's claim state; push it only through the poster gate.")
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
    elif sub == "config" and not (set(a) & {"--get", "--get-all", "--get-regexp", "--list", "-l", "--show-origin", "--show-scope"}) and any(re.search(r"core\.hooksPath|core\.fsmonitor|credential\.helper|url\..*insteadof|core\.sshCommand|^alias\.|^remote\.|pushurl|^include", x, re.I) for x in a):
        g.deny("git-config", "this setting changes which hooks, helpers or hosts git trusts (R2/R5).")
    elif sub == "remote" and rest and rest[0] in ("add", "set-url", "set-head", "rename", "remove", "rm"):
        g.deny("git-remote", "adding or changing a remote can send commits somewhere else (R2/R4).", "The owner sets remotes up; push to the one that exists.")
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
    for t in sg.tokens:  # leading NAME=value settings and wrapper options, up to the program itself
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", t):
            if ENV_DANGER.fullmatch(t):
                g.deny("env-redirect", f"setting {t.split('=')[0]} for one command can send git's data elsewhere or run a program of the caller's choosing (R2/R4/R5).")
        elif os.path.basename(t) not in g.WRAPPER_OPTS and not t.startswith("-"):
            break
    prog, args = g.program_and_args(sg.tokens)
    if not prog:
        for op, target in sg.redirects:
            check_redirect(op, target, cwd, root, pol)
        return
    short, long_, rest = flags_of(args)
    for op, target in sg.redirects:
        check_redirect(op, target, cwd, root, pol, cwd_for_glob=cwd)
    check_more(prog, args, short, long_, rest, sg, cwd, root, pol)
    # A program that only names paths is exempt for its OWN arguments, but not for what a wrapper in front of it consumed
    # (`xargs -a .env echo` reads .env through xargs).
    wrapper_part = sg.tokens[:max(0, len(sg.tokens) - len(args))]
    for t in (wrapper_part if prog in NAME_ONLY else sg.tokens):
        hit = g.credential_in_arg(t, cwd)
        if hit:
            g.deny("read-credential-file", f"'{hit}' is a file that normally holds a secret; {prog} was given it, and agents never see secret values (R5).", "Ask the owner to read or move it.")
    if (prog in SHELLS or prog in INTERPRETERS or prog in ("source", ".", "eval", "exec")) and any(t.startswith(("<(", ">(")) for t in args):
        g.deny("process-substitution", f"{prog} was given the output of a command (<( ... )) to run as its script, which the hook cannot read.", "Write the script to a file, review it, and run the file.")
    if prog in ("sudo", "doas", "su", "pkexec"):
        g.deny("privilege-escalation", f"{prog} runs a command with higher privileges (R2/R5).")
    if prog in g.UNKNOWN_WRAPPERS:
        g.deny("unrecognised-wrapper", f"{prog} runs another command in a way this hook cannot follow, so what it would run is unknown.", "Write the inner command directly, without the wrapper.")
    if prog in INTERPRETERS and INLINE_FLAG.search(" ".join(a for a in args if a.startswith("-") and not a.startswith("--") or a in ("--eval", "--command"))):
        code = " ".join(args)
        if INLINE_CRED.search(code):
            g.deny("inline-credential", f"{prog} was given inline code that mentions a credential file or folder; agents never see secret values (R5).", "Ask the owner; do not read credentials from code either.")
        if INLINE_ENV.search(code) or (prog in ("ruby", "perl") and re.search(r"\bENV\b", code)):
            g.deny("print-secret-variable", f"{prog} was given inline code that reads the environment (os.environ, process.env, getenv ...), which can print tokens; agents never see secret values (R5).", "Ask the owner; name the one harmless variable you need in a script file that can be reviewed.")
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
        check_git(args, cwd, root, pol, sg, state)
    elif prog == "patch":
        check_patch("patch", args, sg, cwd, root, pol)
    elif prog == "gh":
        check_gh(args, cwd, root, pol)
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
    if prog in MUTATORS or (prog in ("sed", "perl", "awk") and ("i" in short or any(a.startswith("-i") for a in args))):
        for t in rest:
            p = g.resolve(t, cwd)
            if p is not None and g.is_protected(p, root, pol):
                g.deny("protected-path", f"{prog} would change {os.path.relpath(p, root)}, a protected path.", "Propose the change in a change request; the owner applies it.")
            if p is not None and g.git_config_file(p):
                g.deny("git-config", f"{prog} would change {t}, a git settings file that can redirect where pushes go (R2/R4).")
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


def check_redirect(op, target, cwd, root, pol, cwd_for_glob=None):
    if op == "<":
        hit = g.credential_in_arg(target, cwd_for_glob or cwd)
        if hit:
            g.deny("read-credential-file", f"'{hit}' is a file that normally holds a secret; reading it as input still shows its contents to the program (R5).", "Ask the owner to read or move it.")
        return
    if op != ">" or target in ("/dev/null", "/dev/stdout", "/dev/stderr", "&1", "&2"):
        return
    if target.startswith("/dev/") and not target.startswith("/dev/null"):
        g.deny("device-write", f"redirecting output to {target} writes to a device.")
    p = g.resolve(target, cwd)
    if p is not None and g.is_protected(p, root, pol):
        g.deny("protected-path", f"redirecting output to {os.path.relpath(p, root)} would change a protected path.")
    if p is not None and g.git_config_file(p):
        g.deny("git-config", f"redirecting output to {target} changes a git settings file, which can redirect where pushes go (R2/R4).")
    if g.risky_name(target) and not target.endswith((".example", ".sample", ".template")):
        g.deny("write-credential-file", f"writing to '{target}' stores a secret-bearing file; credentials are the owner's to place (R5).")
    if p is not None:
        real = os.path.realpath(p)
        if real != p and g.risky_name(real) and not real.endswith((".example", ".sample", ".template")):
            g.deny("write-credential-file", f"'{target}' is a link to {real}, a secret-bearing file; credentials are the owner's to place (R5).")


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
                    "run rerun", "auth token", "auth refresh", "auth login", "auth logout", "label delete", "ruleset", "alias", "extension", "codespace",
                    "gist create", "gist edit", "release create", "release upload", "release edit", "repo create", "repo fork", "repo sync",
                    # round 4: these change what other people see or what the owner is asked to decide (R2/R4)
                    "pr close", "pr ready", "pr reopen", "pr lock", "pr unlock", "pr edit", "pr update-branch", "pr checkout",
                    "issue close", "issue reopen", "issue delete", "issue lock", "issue unlock", "issue transfer", "issue pin", "issue unpin",
                    "release delete-asset", "cache delete", "run delete", "run cancel", "workflow delete", "label create", "label edit", "label clone")
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


def check_gh(args, cwd, root, pol):
    path, rest = gh_parts(args)
    s2 = " ".join(path[:2])
    if path[:1] == ["api"]:
        return check_gh_api(rest, cwd, root, pol)
    for d in GH_GROUPS_DENIED:
        if s2 == d or s2.startswith(d + " "):
            if d == "pr merge":
                g.deny("merge-pr", "merging a pull request is the owner's decision; builders open a PR and stop.")
            g.deny("gh-privileged", f"'gh {s2}' changes repository settings, secrets or tooling, publishes files, runs the poster, or prints a token. These are R2 to R5 actions for the owner.")
    if s2 == "pr review" and any(x in ("-a", "--approve", "-r", "--request-changes") for x in rest):
        g.deny("gh-privileged", "approving or blocking a pull request is the owner's decision (R4); a build session only comments.")
    if s2 == "auth status" and any(x in ("-t", "--show-token") for x in rest):
        g.deny("gh-privileged", "'gh auth status --show-token' prints the GitHub token; agents never see secret values (R5).")
    i = 0
    while i < len(rest):  # a file given as the text of a comment, review, issue or pull request is posted publicly
        a, val = rest[i], None
        if a in ("-F", "--body-file", "--notes-file"):
            val, i = (rest[i + 1] if i + 1 < len(rest) else ""), i + 2
        elif a.startswith(("--body-file=", "--notes-file=")):
            val, i = a.split("=", 1)[1], i + 1
        elif a.startswith("-F") and not a.startswith("--") and len(a) > 2:
            val, i = a[2:], i + 1
        else:
            i += 1
            continue
        check_publish_file(val, cwd, root, pol, f"gh {s2} {a.split('=')[0]}")


def check_gh_api(rest, cwd, root, pol):
    method, fields, positional, has_input, i = None, [], [], False, 0
    typed, input_file = [], None
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
            fields.append(rest[i + 1] if i + 1 < len(rest) else "")
            if a in ("-F", "--field"):
                typed.append(fields[-1])
            i += 2
        elif a.startswith(("--field=", "--raw-field=")):
            fields.append(a.split("=", 1)[1])
            if a.startswith("--field="):
                typed.append(fields[-1])
            i += 1
        elif len(a) > 2 and a[:2] in ("-f", "-F") and not a.startswith("--"):
            fields.append(a[2:])
            if a[:2] == "-F":
                typed.append(a[2:])
            i += 1
        elif a == "--input" or a.startswith("--input="):
            has_input = True
            input_file = a.split("=", 1)[1] if "=" in a else (rest[i + 1] if i + 1 < len(rest) else "")
            i += 2 if a == "--input" else 1
        elif a in GH_API_FLAGS_WITH_VALUE:
            i += 2
        elif a.startswith("-"):
            i += 1
        else:
            positional.append(a); i += 1
    for tf in typed:  # -F name=@file sends the file's contents as the field value
        value = tf.partition("=")[2]
        if value.startswith("@"):
            check_publish_file(value[1:], cwd, root, pol, "gh api -F " + tf.partition("=")[0] + "=@file")
    if input_file is not None:
        check_publish_file(input_file, cwd, root, pol, "gh api --input")
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


def scan_command_text(cmd, cwd):
    """A token typed into a commit message, tag, comment body, here-document or any argument is public once it is posted
    (this repository is public). The whole command line is scanned with the same scanner as files, and the value is never printed."""
    if len(cmd) > 2_000_000:
        g.deny("secret-in-command", "the command is too large to scan for secrets.", "Write the text to a file and review it first.")
    ok, f, err = g.run_scanner(["--text", "-"], cwd, stdin=cmd)
    if not ok:
        g.deny("scanner-unavailable", err)
    f = [x for x in f if x.get("rule") not in ("plan-handles-secret", "risky-filename")]
    if f:
        g.deny("secret-in-command", g.describe(f) + " in this command line (a commit or tag message, a comment body, a here-document or an argument). Commands, messages and comments end up in a public repository.",
               "Remove the value and describe it instead (\"a GitHub token, 40 characters\"); tell the owner to revoke it if it was ever real.")


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
    scan_command_text(cmd, cwd)
    if "commit_cwd" in state:
        scan_commit(state, root)
    if "scan_outgoing" in state:
        scan_outgoing(state["scan_outgoing"])
    sys.exit(0)


if __name__ == "__main__":
    g.run(main)
