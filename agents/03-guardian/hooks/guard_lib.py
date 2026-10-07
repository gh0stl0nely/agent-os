"""Shared code for the Guardian's PreToolUse hooks. Standard library only; nothing here runs the command it reads.

The hooks are a speed bump with a clear message, not a sandbox: a determined program can build a command the parser
does not see (variables, eval, an encoded string). They sit beside GitHub's own controls, not in place of them.
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


def all_segments(cmd, depth=0):
    """Every segment in the command, including those inside $( ), backticks and sh -c strings."""
    segs, nested = parse(cmd, depth)
    out = list(segs)
    for sub in nested:
        out += all_segments(sub, depth + 1)
    extra = []
    for sg in segs:
        prog, args = program_and_args(sg.tokens)
        if prog in ("bash", "sh", "zsh", "dash", "ksh") and "-c" in args:
            k = args.index("-c")
            if k + 1 < len(args):
                extra.append(args[k + 1])
        if prog in ("eval",) and args:
            extra.append(" ".join(args))
    for sub in extra:
        out += all_segments(sub, depth + 1)
    return out


WRAPPERS = {"command", "builtin", "nohup", "time", "nice", "ionice", "exec", "stdbuf", "timeout", "setsid", "env", "xargs"}


def program_and_args(tokens):
    i = 0
    while i < len(tokens) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", tokens[i]):
        i += 1
    while i < len(tokens) and os.path.basename(tokens[i]) in WRAPPERS:
        w = os.path.basename(tokens[i])
        i += 1
        while i < len(tokens) and (tokens[i].startswith("-") or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", tokens[i]) or (w in ("timeout", "nice") and re.fullmatch(r"[\d.]+[smhd]?", tokens[i]))):
            i += 1
    if i >= len(tokens):
        return "", []
    return os.path.basename(tokens[i]), tokens[i + 1:]


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


def deny(rule, reason, how=None):
    msg = f"Blocked by Guardian hook [{rule}]: {reason}"
    if how:
        msg += f" {how}"
    msg += " This is a planning-time rule: write a Preflight Brief and ask the owner instead of working around it."
    print(msg, file=sys.stderr)
    sys.exit(2)
