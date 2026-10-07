"""Shared code for the Guardian's PreToolUse hooks. Standard library only; nothing here runs the command it reads.

THESE HOOKS ARE A GUARDRAIL, NOT A SECURITY BOUNDARY. They stop a mistaken or manipulated agent from walking into a
well-known mistake, with a clear message. They do not stop a determined program: a command can be built from a script
written earlier, a program the parser has never heard of, or an encoding. They parse text; they cannot see what a
program does. Real limits belong in GitHub (branch protection, push protection) and in what credentials a session holds.
Where the parser does not understand a form it fails closed (blocks) rather than guessing it is harmless.
"""
import fnmatch
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_FROM_HOOK = HERE.parents[2]
SCANNER = REPO_FROM_HOOK / ".claude/skills/secrets-hygiene/scripts/scan_secrets.py"
POLICY_PATH = HERE / "policy.json"


class ParseError(Exception):
    pass


def load_policy():
    try:
        return json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise RuntimeError(f"policy.json could not be read ({e.__class__.__name__})")


# ---------------------------------------------------------------- shell parsing (no execution)
HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1[^\n]*\n(.*?)\n[ \t]*\2[ \t]*(?=\n|$)", re.S)


def strip_heredocs(cmd):
    """Remove here-document bodies (they are data, usually a commit message) but keep the line that opens them."""
    out, pos = [], 0
    for m in HEREDOC.finditer(cmd):
        line_end = cmd.find("\n", m.start())
        out.append(cmd[pos:line_end if line_end != -1 else m.start()])
        out.append(" ")
        pos = m.end()
    out.append(cmd[pos:])
    return "".join(out)


class Seg:
    def __init__(self, tokens, redirects, piped):
        self.tokens, self.redirects, self.piped = tokens, redirects, piped


def _match_paren(s, i):
    """s[i] == '(' just after '$' or '<' ; return index of the matching ')' or raise."""
    depth, j, q = 0, i, None
    while j < len(s):
        c = s[j]
        if q:
            if c == q:
                q = None
            elif c == "\\" and q == '"':
                j += 1
        elif c in "'\"":
            q = c
        elif c == "\\":
            j += 1
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return j
        j += 1
    raise ParseError("unclosed $( ... )")


def parse(cmd, depth=0):
    """Split a command line into segments of tokens, with redirect targets and nested command strings.
    Returns (segments, nested) where nested are strings found in $( ), backticks and <( ), to parse the same way."""
    if depth > 6:
        raise ParseError("command nests too deeply")
    s = strip_heredocs(cmd)
    segs, nested = [], []
    tokens, redirects, buf, has_buf = [], [], [], False
    piped_next, expect_redirect = False, None

    def end_token():
        nonlocal buf, has_buf, expect_redirect
        if has_buf:
            t = "".join(buf)
            if expect_redirect:
                redirects.append((expect_redirect, t))
                expect_redirect = None
            else:
                tokens.append(t)
        buf, has_buf = [], False

    def end_seg(pipe=False):
        nonlocal tokens, redirects, piped_next
        end_token()
        if tokens or redirects:
            segs.append(Seg(tokens, redirects, piped_next))
        tokens, redirects, piped_next = [], [], pipe

    i, n, q = 0, len(s), None
    while i < n:
        c = s[i]
        if q == "'":
            if c == "'":
                q = None
            else:
                buf.append(c)
            i += 1
            continue
        if c == "\\" and i + 1 < n:
            if s[i + 1] == "\n":
                i += 2
                continue
            buf.append(s[i + 1]); has_buf = True
            i += 2
            continue
        if q == '"':
            if c == '"':
                q = None
                i += 1
                continue
            if c == "$" and i + 1 < n and s[i + 1] == "(":
                j = _match_paren(s, i + 1)
                nested.append(s[i + 2:j]); buf.append("$(...)"); i = j + 1; continue
            if c == "`":
                j = s.find("`", i + 1)
                if j < 0:
                    raise ParseError("unclosed backtick")
                nested.append(s[i + 1:j]); buf.append("`...`"); i = j + 1; continue
            buf.append(c); i += 1
            continue
        # unquoted
        if c in "'\"":
            q = c; has_buf = True; i += 1
            continue
        if c == "$" and i + 1 < n and s[i + 1] == "(":
            j = _match_paren(s, i + 1)
            nested.append(s[i + 2:j]); buf.append("$(...)"); has_buf = True; i = j + 1; continue
        if c in "<>" and i + 1 < n and s[i + 1] == "(":
            j = _match_paren(s, i + 1)
            nested.append(s[i + 2:j]); buf.append("<(...)"); has_buf = True; i = j + 1; continue
        if c == "`":
            j = s.find("`", i + 1)
            if j < 0:
                raise ParseError("unclosed backtick")
            nested.append(s[i + 1:j]); buf.append("`...`"); has_buf = True; i = j + 1; continue
        if c == "#" and not has_buf:
            while i < n and s[i] != "\n":
                i += 1
            continue
        if c in " \t":
            end_token(); i += 1; continue
        if c == "\n" or c == ";":
            end_seg(); i += 1; continue
        if c == "&":
            if i + 1 < n and s[i + 1] == ">":  # &> file
                end_token(); expect_redirect = ">"; i += 2; continue
            end_seg(); i += 2 if (i + 1 < n and s[i + 1] == "&") else 1; continue
        if c == "|":
            if i + 1 < n and s[i + 1] == "|":  # '||' joins commands; it is not a pipe
                end_seg(); i += 2
            else:
                end_seg(pipe=True); i += 1
            continue
        if c in "()":
            end_seg(); i += 1; continue
        if c in "<>":
            # file-descriptor prefix like 2> or 2>&1
            if has_buf and "".join(buf).isdigit():
                buf, has_buf = [], False
            else:
                end_token()
            op = c
            i += 1
            if i < n and s[i] == c:
                op += c; i += 1
            if i < n and s[i] == "&":  # 2>&1 : not a file
                i += 1
                while i < n and (s[i].isdigit() or s[i] == "-"):
                    i += 1
                continue
            if op.startswith("<"):
                expect_redirect = "<"
            else:
                expect_redirect = ">"
            continue
        buf.append(c); has_buf = True; i += 1
    if q:
        raise ParseError("unclosed quote")
    end_seg()
    return segs, nested


SHELL_NAMES = {"sh", "bash", "zsh", "dash", "ksh", "ash", "mksh", "csh", "tcsh", "fish"}
ASSIGN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=.*")
RESERVED = {"if", "then", "elif", "else", "while", "until", "do", "!", "{", "}", "(", ")"}

# For each wrapper, its options and how many arguments each takes. An option not listed here is not guessed at: the
# command is refused as unparseable, so a new spelling cannot slip through as "just an option".
WRAPPER_OPTS = {
    "command": {"-p": 0, "-v": 0, "-V": 0},
    "builtin": {},
    "exec": {"-a": 1, "-c": 0, "-l": 0},
    "nohup": {},
    "time": {"-p": 0, "-v": 0, "-a": 0, "-f": 1, "-o": 1, "--portability": 0, "--verbose": 0, "--append": 0, "--format": 1, "--output": 1},
    "nice": {"-n": 1, "--adjustment": 1},
    "ionice": {"-c": 1, "-n": 1, "-p": 1, "-P": 1, "-u": 1, "-t": 0},
    "stdbuf": {"-i": 1, "-o": 1, "-e": 1},
    "timeout": {"-s": 1, "-k": 1, "-v": 0, "--signal": 1, "--kill-after": 1, "--preserve-status": 0, "--foreground": 0, "--verbose": 0},
    "setsid": {"-c": 0, "-f": 0, "-w": 0, "--ctty": 0, "--fork": 0, "--wait": 0},
    "env": {"-i": 0, "-0": 0, "-v": 0, "-u": 1, "-C": 1, "-S": "split", "--ignore-environment": 0, "--null": 0, "--unset": 1, "--chdir": 1, "--split-string": "split"},
    "xargs": {"-0": 0, "-r": 0, "-t": 0, "-p": 0, "-x": 0, "-o": 0, "-I": 1, "-i": 0, "-n": 1, "-P": 1, "-d": 1, "-E": 1, "-e": 0, "-L": 1, "-l": 0, "-s": 1, "-a": 1,
              "--null": 0, "--no-run-if-empty": 0, "--verbose": 0, "--max-args": 1, "--max-procs": 1, "--delimiter": 1, "--arg-file": 1, "--replace": 0},
    "busybox": {},
}
# Programs that run another command in a way this parser does not follow. Refused, not guessed at: write the inner command directly.
UNKNOWN_WRAPPERS = {"watch", "flock", "unshare", "chroot", "nsenter", "strace", "ltrace", "setpriv", "script", "parallel", "expect", "unbuffer",
                    "at", "batch", "start-stop-daemon", "systemd-run", "runuser", "capsh", "taskset", "chrt", "numactl", "fakeroot", "firejail",
                    "bwrap", "proot", "gdb", "valgrind", "sg", "newgrp", "run-parts", "ssh-agent", "dbus-launch", "xvfb-run", "cpulimit", "sshpass"}


def shell_command_string(args):
    """For `sh|bash|zsh [options] -c STRING [...]` return STRING. None if the shell is not given -c (it runs a file or
    stdin, which cannot be read here). Raises ParseError when -c has no string. Handles -lc, -ec, -xc, --login -c, -o NAME -c."""
    i, c_seen = 0, False
    while i < len(args):
        a = args[i]
        if a == "--":
            i += 1
            break
        if a.startswith("--"):
            i += 2 if a in ("--rcfile", "--init-file") else 1
            continue
        if re.fullmatch(r"[-+][A-Za-z]+", a):
            if a[0] == "-" and "c" in a[1:]:
                c_seen = True
            i += 2 if a[-1] in "oO" else 1  # a cluster ending in o/O takes a name: -eo pipefail
            continue
        break
    if not c_seen:
        return None
    if i >= len(args):
        raise ParseError("a shell was given -c with no command string")
    return args[i]


def _unwrap_options(w, tokens, i):
    """Skip the options (and their arguments) of wrapper `w`. Returns (index of next token, extra tokens from env -S)."""
    table, extra = WRAPPER_OPTS[w], []
    while i < len(tokens) and tokens[i].startswith("-") and tokens[i] != "-":
        t = tokens[i]
        if t == "--":
            i += 1
            break
        name, val = (t.split("=", 1) + [None])[:2] if t.startswith("--") else (t, None)
        if name not in table and not t.startswith("--"):
            # an option with its value attached: -n5, -I{}, -sKILL
            if len(t) > 2 and t[:2] in table and table[t[:2]]:
                name, val = t[:2], t[2:]
            elif w == "nice" and re.fullmatch(r"-\d+", t):
                i += 1
                continue
        if name not in table:
            raise ParseError(f"'{w}' was given an option this hook does not recognise ({t}); write the command without the wrapper")
        arity = table[name]
        i += 1
        if arity:
            if val is None:
                if i >= len(tokens):
                    raise ParseError(f"'{w} {name}' has no value")
                val, i = tokens[i], i + 1
            if arity == "split":
                import shlex
                try:
                    extra = shlex.split(val)
                except ValueError:
                    raise ParseError("env -S has an unreadable string")
    return i, extra


def program_and_args(tokens):
    """The program that will really run and its arguments, after variable assignments, shell keywords (if, then, do, !,
    braces) and the wrappers in WRAPPER_OPTS are peeled off. Raises ParseError for a form it cannot follow."""
    tokens = list(tokens)
    i = 0
    for _ in range(40):
        while i < len(tokens) and (ASSIGN.fullmatch(tokens[i]) or tokens[i] in RESERVED):
            i += 1
        if i >= len(tokens):
            return "", []
        w = os.path.basename(tokens[i])
        if w not in WRAPPER_OPTS:
            break
        i += 1
        if w == "busybox":
            continue  # the next token is the applet name: treat it as the program
        i, extra = _unwrap_options(w, tokens, i)
        if extra:
            tokens = tokens[:i] + extra + tokens[i:]
        if w == "timeout":
            if i < len(tokens) and re.fullmatch(r"[\d.]+[smhd]?", tokens[i]):
                i += 1
            else:
                raise ParseError("'timeout' without a duration")
        if w == "env":
            while i < len(tokens) and ASSIGN.fullmatch(tokens[i]):
                i += 1
    else:
        raise ParseError("wrappers nest too deeply")
    prog = os.path.basename(tokens[i])
    if tokens[i] not in ("[", "[[") and ("$" in tokens[i] or "`" in tokens[i] or any(ch in tokens[i] for ch in "*?[")):
        raise ParseError(f"the program to run ('{tokens[i][:40]}') is built at run time, so the hook cannot tell what it is; write its name directly")
    return prog, tokens[i + 1:]


def find_exec_commands(args):
    """The commands inside `find ... -exec CMD ... ;` (also -execdir, -ok, -okdir), as token lists."""
    out, i = [], 0
    while i < len(args):
        if args[i] in ("-exec", "-execdir", "-ok", "-okdir"):
            j = i + 1
            while j < len(args) and args[j] not in (";", "+"):
                j += 1
            out.append(args[i + 1:j])
            i = j
        i += 1
    return out


def all_segments(cmd, depth=0):
    """Every segment in the command, including those inside $( ), backticks, `sh -c` strings (any option cluster such as
    -lc, -ec), `eval`, and `find -exec`."""
    segs, nested = parse(cmd, depth)
    out = list(segs)
    for sub in nested:
        out += all_segments(sub, depth + 1)
    extra_cmds, extra_segs = [], []
    for sg in segs:
        prog, args = program_and_args(sg.tokens)
        if prog in SHELL_NAMES:
            sc = shell_command_string(args)
            if sc is not None:
                extra_cmds.append(sc)
        elif prog == "eval" and args and not any("$(" in t or "`" in t for t in args):
            extra_cmds.append(" ".join(args))  # eval of a substitution is refused by the bash hook itself
        elif prog == "find":
            for toks in find_exec_commands(args):
                if toks:
                    extra_segs.append(Seg(toks, [], False))
    for sub in extra_cmds:
        out += all_segments(sub, depth + 1)
    for sg in extra_segs:
        out.append(sg)
        prog, args = program_and_args(sg.tokens)
        if prog in SHELL_NAMES:
            sc = shell_command_string(args)
            if sc is not None:
                out += all_segments(sc, depth + 1)
    return out


# ---------------------------------------------------------------- paths
def resolve(tok, cwd):
    """Absolute path for a token, or None when it cannot be known (variable, glob, substitution)."""
    if any(ch in tok for ch in "*?[") or "$" in tok and not tok.startswith(("$HOME", "${HOME}")) or "`" in tok or "..." in tok and "$(" in tok:
        return None
    t = tok.replace("${HOME}", "~").replace("$HOME", "~")
    t = os.path.expanduser(t)
    return os.path.normpath(os.path.join(cwd, t))


def repo_root(cwd):
    p = subprocess.run(["git", "-C", cwd, "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    return p.stdout.strip() if p.returncode == 0 and p.stdout.strip() else cwd


NEVER_UNLOCK = {".git/", ".claude/settings.json", ".claude/settings.local.json", ".claude/hooks/", "agents/03-guardian/hooks/"}


def unlocked(pattern):
    """The OWNER may unlock a protected path for one session by starting Claude Code with GUARDIAN_UNLOCK set to a
    comma-separated list of exact entries from policy.json (for example ".github/workflows/"). The hook reads its own
    environment, which a command run by the agent cannot change. Git internals, the settings and the hooks themselves
    can never be unlocked this way."""
    wanted = {x.strip() for x in os.environ.get("GUARDIAN_UNLOCK", "").split(",") if x.strip()}
    return pattern in wanted and pattern not in NEVER_UNLOCK


def is_protected(path, root, policy):
    if path is None:
        return False
    try:
        rel = os.path.relpath(path, root)
    except ValueError:
        return False
    if rel.startswith(".."):
        return False
    rel = rel.replace(os.sep, "/")
    for pat in policy["protected_paths"]:
        if unlocked(pat):
            continue
        if pat.endswith("/"):
            if rel == pat[:-1] or rel.startswith(pat):
                return True
        elif fnmatch.fnmatch(rel, pat):
            return True
    return False


RISKY_NAME = re.compile(r"(?i)(?:^|/)(?:\.env(?:\.(?!example$|sample$|template$|dist$)[^/]+)?|id_(?:rsa|dsa|ecdsa|ed25519)|\.netrc|\.pypirc|\.npmrc|\.git-credentials|credentials(?:\.json)?|service-account[^/]*\.json|[^/]+\.(?:pem|key|p12|pfx|ppk|keystore|jks))$|(?:^|/)\.(?:ssh|aws|gnupg|kube|docker)/|(?:^|/)\.config/gh/")


def risky_name(path):
    return bool(RISKY_NAME.search(path.replace(os.sep, "/")))


# ---------------------------------------------------------------- scanning
def run_scanner(args, cwd, stdin=None):
    """Return (ok, findings, error). Fails closed: a scanner that cannot run is an error, not a pass."""
    if not SCANNER.exists():
        return False, [], f"the secret scanner was not found at {SCANNER}; the hook cannot confirm the commit is clean"
    p = subprocess.run([sys.executable, "-I", str(SCANNER), *args], cwd=cwd, capture_output=True, text=True, input=stdin)
    try:
        out = json.loads(p.stdout)
    except ValueError:
        return False, [], "the secret scanner gave no readable result; the hook cannot confirm the commit is clean"
    return True, out.get("findings", []), None


def describe(findings):
    first = findings[0]
    where = f"{first.get('source') or first.get('file') or '?'}:{first.get('line', '?')}"
    return f"{len(findings)} secret-like finding(s), first: rule {first.get('rule')} at {where} (the value is not shown)"


# ---------------------------------------------------------------- hook I/O
def read_input():
    try:
        data = json.load(sys.stdin)
        if not isinstance(data, dict):
            raise ValueError
        return data
    except ValueError:
        print("Guardian hook: the tool call could not be read, so it is blocked. Try again; if it keeps happening tell the owner.", file=sys.stderr)
        sys.exit(2)


def run(main_fn):
    """Run a hook. Any unexpected error blocks (exit 2). Claude Code treats other non-zero exits as a harmless warning
    and carries on, so a crash must never be allowed to exit 1."""
    try:
        main_fn()
    except SystemExit:
        raise
    except BaseException as e:
        deny("hook-error", f"the hook failed unexpectedly ({e.__class__.__name__}), so the call is blocked rather than waved through.", "Tell the owner; do not work around it.")


def deny(rule, reason, how=None):
    msg = f"Blocked by Guardian hook [{rule}]: {reason}"
    if how:
        msg += f" {how}"
    msg += " This is a planning-time rule: write a Preflight Brief and ask the owner instead of working around it."
    print(msg, file=sys.stderr)
    sys.exit(2)
