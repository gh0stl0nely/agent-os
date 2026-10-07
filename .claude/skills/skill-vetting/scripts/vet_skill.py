#!/usr/bin/env python3
"""Vet a third-party skill folder against the OWASP Agentic Skills Top 10 (AST01-AST10). Standard library only.

  vet_skill.py SKILL_DIR --source URL --commit SHA40 [--reviewer NAME] [--reviewed-at YYYY-MM-DD]
               [--installed-dir .claude/skills] [--inventory agents/03-guardian/skill-inventory.md]

The folder is untrusted data. This script reads every file as bytes, parses Python only with ast.parse, and never
imports, runs or follows anything inside it. Symlinks are listed, not followed. Output is JSON on stdout.

For each AST item it gives checks, each with result pass | fail | manual and evidence (file, line, rule). A pass
carries the count of files examined and the rules that found nothing. The verdict is never "approved":
  reject                  at least one check failed
  needs-manual-review     no check failed (automated_result says "no-findings" or "manual-items"); a person
                          still reads every file, because a pattern scan cannot see logic that avoids the patterns
Exit 0 = no failed check, 1 = reject, 2 = usage or read error.
"""
import argparse
import ast
import hashlib
import json
import os
import re
import sys
import unicodedata
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / ".claude/skills/risk-classify/scripts"))
sys.path.insert(0, str(REPO / ".claude/skills/secrets-hygiene/scripts"))
import classify  # noqa: E402
import scan_secrets  # noqa: E402

VERSION = "1.0"
MAX_FILES, MAX_DEPTH, MAX_BYTES = 500, 8, 5_000_000
CODE_EXT = {".py", ".sh", ".bash", ".zsh", ".js", ".mjs", ".cjs", ".ts", ".rb", ".pl", ".ps1", ".bat", ".cmd", ".php", ".lua"}
TEXT_EXT = CODE_EXT | {".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".cfg", ".ini", ".csv", ".html", ".css", ".xml", ".rst", ""}
BINARY_MAGIC = [(b"\x7fELF", "ELF executable"), (b"MZ", "Windows executable"), (b"\xcf\xfa\xed\xfe", "Mach-O executable"),
                (b"\xca\xfe\xba\xbe", "Mach-O or Java class"), (b"PK\x03\x04", "zip/jar/wheel archive"), (b"\x1f\x8b", "gzip archive"),
                (b"\x89PNG", "PNG image"), (b"%PDF", "PDF document"), (b"\x00asm", "WebAssembly")]
EXEC_EXT = {".exe", ".dll", ".so", ".dylib", ".jar", ".class", ".pyc", ".pyo", ".whl", ".wasm", ".msi", ".app", ".node"}
ZERO_WIDTH = re.compile("[\u200b-\u200f\u202a-\u202e\u2060-\u2064\u2066-\u2069\ufeff\U000e0000-\U000e007f]")
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SEV = {"pass": 0, "manual": 1, "fail": 2}

AST_TITLES = {
    "AST01": "Malicious skills", "AST02": "Supply chain compromise", "AST03": "Over-privileged skills",
    "AST04": "Insecure metadata", "AST05": "Untrusted external instructions", "AST06": "Weak isolation",
    "AST07": "Update drift", "AST08": "Poor scanning", "AST09": "No governance", "AST10": "Cross-platform reuse"}

# (check id, AST id, title, [(rule id, regex, severity in code, severity in prose)], scope)  scope: code | all
R = re.compile
CHECKS = [
    ("AST01-exec", "AST01", "No dynamic or shell execution, no download-and-run", [
        ("pipe-to-shell", R(r"\b(?:curl|wget|iwr|Invoke-WebRequest)\b[^\n|;]{0,200}\|\s*(?:sudo\s+)?(?:ba|z|da)?sh\b|\|\s*(?:python3?|node|perl|ruby)\s*(?:-\s*)?$", re.M), "fail", "fail"),
        ("dynamic-exec", R(r"\b(?:eval|exec)\s*\(|\bos\.(?:system|popen)\s*\(|shell\s*=\s*True|\bpickle\.loads?\s*\(|\bmarshal\.loads?\s*\(|__import__\s*\(|\bFunction\s*\(|child_process"), "fail", "manual"),
        ("destructive", R(r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f|\brm\s+-[a-zA-Z]*f[a-zA-Z]*r|\bmkfs\b|\bdd\s+if=|\bshutil\.rmtree\s*\(|git\s+push\s+(?:-f|--force)|git\s+reset\s+--hard|:\(\)\s*\{"), "fail", "manual"),
        ("reverse-shell", R(r"/dev/tcp/|\bnc\s+(?:-[a-z]*e|-e)\b|\bncat\b.{0,30}-e|bash\s+-i\s*>&|socket\.socket\s*\(.{0,120}connect", re.S), "fail", "fail"),
        ("encoded-exec", R(r"base64\s+(?:-d|--decode)|b64decode|fromhex|\bzlib\.decompress|codecs\.decode\([^)]*rot"), "manual", "manual")], "all"),
    ("AST01-obfuscation", "AST01", "No obfuscated payloads", [
        ("long-encoded-blob", R(r"[A-Za-z0-9+/]{120,}={0,2}"), "fail", "manual"),
        ("hex-escapes", R(r"(?:\\x[0-9a-fA-F]{2}){8,}"), "fail", "manual"),
        ("char-assembly", R(r"(?:chr\(\d+\)\s*\+\s*){4,}|(?:\\u[0-9a-fA-F]{4}){6,}"), "fail", "manual")], "all"),
    ("AST01-exfil", "AST01", "No credential reads or data sent to unknown hosts", [
        ("credential-path", R(r"~?/?\.ssh\b|\.aws/credentials|\.netrc|\.npmrc|\.pypirc|\.git-credentials|\.docker/config|\bid_rsa\b|\.config/gh|\bkeychain\b|\bcookies?\.sqlite|Login Data"), "fail", "manual"),
        ("env-dump", R(r"os\.environ(?!\s*\.get\(\s*[\"'][A-Z0-9_]*(?:HOME|PATH|LANG|TZ|USER)[\"'])\s*(?:\)|\.items|\.copy|$)|\bprintenv\b|\benv\s*\|\s*(?:curl|nc|base64)|dict\(os\.environ\)"), "fail", "manual"),
        ("exfil-endpoint", R(r"webhook\.site|requestbin|pastebin\.com|transfer\.sh|ngrok\.|discord(?:app)?\.com/api/webhooks|hooks\.slack\.com|burpcollaborator|interact\.sh|\.invalid\b/(?:collect|upload|exfil)"), "fail", "fail")], "all"),
    ("AST01-persistence", "AST01", "No persistence or edits to agent settings", [
        ("persistence", R(r"\bcrontab\b|\.bashrc|\.zshrc|\.profile\b|launchctl|LaunchAgents|systemctl\s+enable|authorized_keys|\.git/hooks|schtasks"), "fail", "manual"),
        ("agent-config-write", R(r"\.claude/settings|\.claude/hooks|CLAUDE\.md|\.mcp\.json|\.claude\.json"), "fail", "manual")], "all"),
    ("AST02-deps", "AST02", "Dependencies pinned, none fetched at run time", [
        ("runtime-install", R(r"\b(?:pip3?|pipx|npm|npx|yarn|pnpm|gem|cargo|go)\s+(?:install|add|get|i)\b|\buv\s+(?:pip|add|run\s+--with)|\bapt(?:-get)?\s+install\b|\bbrew\s+install\b"), "manual", "manual")], "all"),
    ("AST03-secrets", "AST03", "The skill asks for no secret or credential", [
        ("secret-var", R(r"\b[A-Z][A-Z0-9_]*(?:API_?KEY|SECRET|TOKEN|PASSWORD|PASSWD|PRIVATE_KEY|ACCESS_KEY)[A-Z0-9_]*\b"), "manual", "manual"),
        ("asks-for-secret", R(r"(?i)\b(?:paste|enter|provide|send|share|type)\b[^.\n]{0,40}\b(?:api key|password|token|secret|credential|private key)s?\b"), "fail", "fail")], "all"),
    ("AST05-follow-remote", "AST05", "No instruction fetched from a URL and followed", [
        ("fetch-and-follow", R(r"(?i)\b(?:fetch|download|load|read|curl|wget|open|retrieve)\b[^.\n]{0,80}https?://[^\s)]+[^.\n]{0,100}\b(?:follow|execute|run|obey|apply|do what|instructions?)\b|(?i:follow|obey|execute)\s+(?:the\s+)?(?:instructions?|commands?|steps)\s+(?:at|in|from)\s+(?:https?://|the (?:url|link|page))|(?i:\bat runtime\b[^.\n]{0,50}(?:fetch|download))"), "fail", "fail"),
        ("remote-code-source", R(r"(?:raw\.githubusercontent\.com|gist\.github(?:usercontent)?\.com|pastebin\.com/raw|bit\.ly|tinyurl\.com)"), "manual", "manual")], "all"),
    ("AST05-hidden-intent", "AST05", "No text that hides behaviour or addresses the reviewer", [
        ("hide-from-user", R(r"(?i)\b(?:do not|don't|never|without)\b[^.\n]{0,25}\b(?:tell|mention|show|inform|notify|alert|reveal|disclose)\b[^.\n]{0,25}\b(?:user|owner|human|reviewer|anyone)\b|\bsilently\b|\bin the background without\b|\bsecretly\b"), "fail", "fail"),
        ("self-attestation", R(r"(?i)\b(?:this skill is (?:safe|trusted|verified|reviewed|approved)|already (?:vetted|reviewed|scanned|approved)|scanner[: ]+(?:ignore|skip|pass)|ignore (?:the )?(?:scanner|vetting|guardian|reviewer)|verified by\b|security[- ]audited)"), "fail", "fail")], "all"),
    ("AST06-scope", "AST06", "Stays inside its own folder; no privilege escalation", [
        ("escalation", R(r"\bsudo\b|\bsu\s+-|chmod\s+(?:-R\s+)?(?:7[0-7][0-7]|\+s|a\+)|chown\s|docker\.sock|--privileged|setuid|\bdoas\b"), "fail", "manual"),
        ("outside-folder", R(r"(?<![\w.])\.\./|(?<![\w/])~/|(?<![\w:/.])/(?:etc|home|root|usr|var|opt|tmp|Users|proc|sys)/|\$HOME|\bos\.path\.expanduser|Path\.home\(\)|os\.walk\(\s*[\"']/"), "manual", "manual")], "all"),
    ("AST07-selfupdate", "AST07", "The skill does not update itself", [
        ("self-update", R(r"(?i)\bgit\s+(?:pull|fetch|clone|submodule)\b|auto[- ]?update|self[- ]?update|pip3?\s+install\s+(?:-U|--upgrade)|npm\s+(?:update|upgrade)|\bfetch the latest\b|\blatest version of (?:this|the) skill"), "fail", "manual")], "all"),
    ("AST10-other-platform", "AST10", "No assumptions about, or writes to, other agent platforms", [
        ("other-agent-config", R(r"\.cursor(?:rules|/)|\.windsurf|\.codex\b|AGENTS\.md|GEMINI\.md|\.github/copilot-instructions|\.continue/|\.aider|\.clinerules|\.roo/"), "manual", "manual")], "all"),
]
PY_DANGER_CALLS = {"eval", "exec", "compile", "__import__", "open_url"}
PY_NET_MODULES = {"socket", "urllib", "urllib.request", "http.client", "requests", "httpx", "aiohttp", "ftplib", "smtplib", "paramiko", "telnetlib", "websocket", "websockets"}
PY_RISK_MODULES = {"ctypes", "cffi", "pty", "pexpect", "marshal", "pickle", "shelve", "importlib", "runpy", "code", "codeop"}
KNOWN_FRONTMATTER = {"name", "description", "allowed-tools", "license", "version", "metadata", "model", "argument-hint", "compatibility"}
READONLY_TOOLS = {"Read", "Grep", "Glob", "LS"}


def clean_excerpt(s, n=70):
    s = unicodedata.normalize("NFKC", s)
    s = "".join(ch if ch.isprintable() else " " for ch in s).strip()
    return s[:n] + ("..." if len(s) > n else "")


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def parse_frontmatter(text):
    """Minimal parser: key: value, folded continuation lines, and '- item' lists. Returns (dict, error)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, "SKILL.md does not start with a '---' frontmatter block"
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        return None, "frontmatter block is never closed"
    fm, key = {}, None
    for l in lines[1:end]:
        m = re.match(r"^([A-Za-z][\w-]*):\s*(.*)$", l)
        if m and not l.startswith(" "):
            key = m.group(1)
            fm[key] = m.group(2).strip().strip("'\"")
        elif key and l.strip().startswith("- "):
            fm[key] = (fm[key] + "," if fm[key] else "") + l.strip()[2:].strip()
        elif key and l.strip():
            fm[key] = (fm[key] + " " + l.strip()).strip()
    return fm, None


def enumerate_files(root):
    files, unread, symlinks, notes = [], [], [], []
    count = 0
    for dirpath, dirs, names in os.walk(root, followlinks=False):
        rel_dir = os.path.relpath(dirpath, root)
        depth = 0 if rel_dir == "." else rel_dir.count(os.sep) + 1
        if ".git" in dirs:
            dirs.remove(".git")
            unread.append({"path": os.path.join(rel_dir, ".git") if rel_dir != "." else ".git", "reason": "version-control data is not read; review the tree you pin, not the history"})
        for d in list(dirs):
            full = os.path.join(dirpath, d)
            if os.path.islink(full):
                symlinks.append(os.path.relpath(full, root))
                dirs.remove(d)
        if depth >= MAX_DEPTH:
            if dirs:
                unread.append({"path": rel_dir + "/*", "reason": f"deeper than {MAX_DEPTH} levels"})
            dirs[:] = []
        for n in sorted(names):
            full = os.path.join(dirpath, n)
            rel = os.path.relpath(full, root)
            if os.path.islink(full):
                symlinks.append(rel)
                continue
            count += 1
            if count > MAX_FILES:
                unread.append({"path": rel, "reason": f"more than {MAX_FILES} files"})
                continue
            files.append((rel, full))
    return files, unread, symlinks


def read_all(files, unread):
    """Return list of file records. Anything not decoded as UTF-8 text goes to unread with a reason."""
    recs = []
    for rel, full in files:
        try:
            size = os.path.getsize(full)
            if size > MAX_BYTES:
                unread.append({"path": rel, "reason": f"larger than {MAX_BYTES} bytes"})
                continue
            data = Path(full).read_bytes()
        except OSError as e:
            unread.append({"path": rel, "reason": f"could not be read ({e.__class__.__name__})"})
            continue
        ext = Path(rel).suffix.lower()
        magic = next((d for m, d in BINARY_MAGIC if data.startswith(m)), None)
        if ext in EXEC_EXT or magic in ("ELF executable", "Windows executable", "Mach-O executable", "Mach-O or Java class", "WebAssembly"):
            unread.append({"path": rel, "reason": f"executable or compiled file ({magic or ext}); cannot be read as source", "kind": "executable", "sha256": sha256(data)})
            continue
        if b"\x00" in data or magic:
            unread.append({"path": rel, "reason": f"binary data ({magic or 'contains NUL bytes'}); not read", "kind": "binary", "sha256": sha256(data)})
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            unread.append({"path": rel, "reason": "not valid UTF-8; not read", "kind": "binary", "sha256": sha256(data)})
            continue
        recs.append({"path": rel, "sha256": sha256(data), "bytes": len(data), "lines": text.count("\n") + (0 if text.endswith("\n") or not text else 1),
                     "text": text, "ext": ext, "is_code": ext in CODE_EXT or text.startswith("#!")})
    return recs


class Checks:
    def __init__(self):
        self.items = {}

    def add(self, cid, ast, title):
        self.items.setdefault(cid, {"id": cid, "ast": ast, "title": title, "result": "pass", "evidence": [], "examined": 0, "rules_clear": []})
        return self.items[cid]

    def hit(self, cid, sev, path, line, rule, excerpt=None, note=None):
        c = self.items[cid]
        if SEV[sev] > SEV[c["result"]]:
            c["result"] = sev
        e = {"file": path, "line": line, "rule": rule, "result": sev}
        if excerpt:
            e["excerpt"] = excerpt
        if note:
            e["note"] = note
        if len(c["evidence"]) < 25:
            c["evidence"].append(e)
        else:
            c["truncated"] = c.get("truncated", 0) + 1


def py_findings(rec, ck):
    try:
        tree = ast.parse(rec["text"])
    except (SyntaxError, ValueError, RecursionError) as e:
        ck.hit("AST08-coverage", "manual", rec["path"], getattr(e, "lineno", None), "python-unparseable", note="the file does not parse, so its calls could not be listed; read it by hand")
        return
    for node in ast.walk(tree):
        line = getattr(node, "lineno", None)
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            mods = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            for m in mods:
                root = m.split(".")[0]
                if m in PY_NET_MODULES or root in PY_NET_MODULES:
                    ck.hit("AST05-network", "manual", rec["path"], line, "network-import", note=f"imports {m}; every host it contacts must be named and justified")
                if root in PY_RISK_MODULES:
                    ck.hit("AST01-exec", "manual", rec["path"], line, "risky-import", note=f"imports {m}")
                if root in ("subprocess", "os") and isinstance(node, ast.ImportFrom) and any(a.name in ("system", "popen", "Popen", "run", "call") for a in node.names):
                    ck.hit("AST01-exec", "manual", rec["path"], line, "process-import", note=f"imports process functions from {m}")
        if isinstance(node, ast.Call):
            f = node.func
            name = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else "")
            full = ""
            if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
                full = f"{f.value.id}.{f.attr}"
            if name in ("getattr", "setattr", "delattr") and node.args:
                first_builtin = isinstance(node.args[0], ast.Name) and node.args[0].id in ("__builtins__", "builtins", "globals", "locals")
                computed = len(node.args) > 1 and not isinstance(node.args[1], ast.Constant)
                if first_builtin:
                    ck.hit("AST01-exec", "fail", rec["path"], line, "ast-builtins-lookup", note=f"{name}() on the builtins table, a way to reach eval or exec without naming it")
                elif computed:
                    ck.hit("AST01-exec", "manual", rec["path"], line, "ast-computed-attribute", note=f"{name}() with a computed name; what it reaches cannot be listed")
            if name in ("globals", "locals", "vars") and not node.args:
                ck.hit("AST01-exec", "manual", rec["path"], line, "ast-namespace-access", note=f"{name}() exposes the module namespace")
            if name in PY_DANGER_CALLS:
                ck.hit("AST01-exec", "fail", rec["path"], line, "ast-dynamic-call", note=f"calls {name}()")
            if full in ("os.system", "os.popen", "os.execv", "os.execl", "os.spawnl") or (isinstance(f, ast.Attribute) and f.attr in ("check_output", "check_call", "Popen", "run", "call", "getoutput") and isinstance(f.value, ast.Name) and f.value.id == "subprocess"):
                shell = any(k.arg == "shell" and isinstance(k.value, ast.Constant) and k.value.value is True for k in node.keywords)
                ck.hit("AST01-exec", "fail" if (shell or full.startswith("os.")) else "manual", rec["path"], line, "ast-process", note=f"calls {full or 'subprocess'}" + (" with shell=True" if shell else "; the command and its arguments must be read"))
            if name in ("urlopen", "urlretrieve", "get", "post", "put", "request", "create_connection", "connect") and isinstance(f, ast.Attribute):
                base = f.value.id if isinstance(f.value, ast.Name) else ""
                if base in ("requests", "httpx", "urllib", "request", "socket", "session", "client", "aiohttp"):
                    ck.hit("AST05-network", "manual", rec["path"], line, "network-call", note=f"{base}.{name}()")
            if name in ("write_text", "write_bytes", "unlink", "rmtree", "remove", "rmdir", "chmod", "rename", "replace", "symlink_to", "makedirs", "mkdir", "copy", "copytree", "move"):
                ck.hit("AST06-writes", "manual", rec["path"], line, "filesystem-change", note=f"calls {name}(); the paths it touches must stay inside the skill's own scope")
            if name == "open" and len(node.args) > 1 and isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str) and any(c in node.args[1].value for c in "wax+"):
                ck.hit("AST06-writes", "manual", rec["path"], line, "file-open-for-write", note="opens a file for writing")


def run_rules(recs, ck):
    for cid, ast_id, title, rules, scope in CHECKS:
        ck.add(cid, ast_id, title)
    for extra in (("AST06-links", "AST06", "No symbolic links"), ("AST05-network", "AST05", "Network use is named and justified"), ("AST06-writes", "AST06", "File changes stay inside the skill's scope"),
                  ("AST01-hidden-unicode", "AST01", "No hidden or direction-changing characters"), ("AST05-injection", "AST05", "No instruction-like text aimed at an agent or reviewer"),
                  ("AST01-secrets", "AST01", "No secret-like values shipped in the skill"), ("AST08-coverage", "AST08", "Every file was read in full")):
        ck.add(*extra)
    for rec in recs:
        text, path = rec["text"], rec["path"]
        for cid in ck.items:
            ck.items[cid]["examined"] += 1
        # hidden characters
        for ln, l in enumerate(text.splitlines(), 1):
            m = ZERO_WIDTH.search(l)
            if m:
                ck.hit("AST01-hidden-unicode", "fail", path, ln, "hidden-character", note=f"U+{ord(m.group(0)):04X} ({unicodedata.name(m.group(0), 'unnamed')}); text a person cannot see")
        norm = classify.prepare(text)[0] if len(text) < 400_000 else text.lower()
        for rx in classify.INJECTION_RX:
            m = rx.search(norm)
            if m:
                ln = text.lower().count("\n", 0, max(0, text.lower().find(m.group(0)[:12]))) + 1 if m.group(0)[:12] in text.lower() else None
                ck.hit("AST05-injection", "fail", path, ln, "instruction-like-text", excerpt=clean_excerpt(m.group(0)), note="treated as data, not followed")
        for h in scan_secrets.scan_text(text, path):
            ck.hit("AST01-secrets", "fail", path, h["line"], h["rule"], note=f"secret-like value of length {h['length']}; not repeated")
        # rule table
        prose = rec["ext"] in (".md", ".txt", ".rst", "") and not rec["is_code"]
        if text.startswith("#!"):
            nl = text.find("\n")
            text = " " * (nl if nl >= 0 else len(text)) + (text[nl:] if nl >= 0 else "")  # a shebang line names an interpreter, not a path the skill uses
        for cid, ast_id, title, rules, scope in CHECKS:
            for rid, rx, sev_code, sev_prose in rules:
                for m in rx.finditer(text):
                    ln = text.count("\n", 0, m.start()) + 1
                    ck.hit(cid, sev_prose if prose else sev_code, path, ln, rid, excerpt=None if rid in ("long-encoded-blob", "secret-var") else clean_excerpt(m.group(0)))
                    if len(ck.items[cid]["evidence"]) >= 25:
                        break
        if rec["ext"] == ".py":
            py_findings(rec, ck)
        # risky file names
        base = Path(path).name.lower()
        if base in ("requirements.txt", "package.json", "pyproject.toml", "package-lock.json", "pipfile", "poetry.lock", "go.mod", "gemfile"):
            ck.hit("AST02-deps", "manual", path, None, "dependency-manifest", note="lists packages; each name must be read and checked as a real project")
            if base == "requirements.txt":
                for ln, l in enumerate(text.splitlines(), 1):
                    s = l.strip()
                    if s and not s.startswith("#") and "==" not in s and "--hash" not in s:
                        ck.hit("AST02-deps", "fail", path, ln, "unpinned-dependency", excerpt=clean_excerpt(s, 40), note="not pinned to an exact version")
            if base == "package.json":
                for ln, l in enumerate(text.splitlines(), 1):
                    if re.search(r'"[^"]+"\s*:\s*"[\^~*]|"latest"|"[^"]+"\s*:\s*"(?:git|http|github)', l):
                        ck.hit("AST02-deps", "fail", path, ln, "unpinned-dependency", excerpt=clean_excerpt(l, 50), note="range, latest or URL dependency")
        if base in ("setup.py", "postinstall.sh", "install.sh", "preinstall.sh", "makefile") or re.search(r'"(?:pre|post)install"\s*:', text):
            ck.hit("AST01-exec", "manual", path, None, "install-time-script", note="runs when the skill is set up; read it line by line")
        if base in (".env", ".npmrc", ".pypirc", "id_rsa", "id_ed25519", "credentials", ".netrc") or base.endswith((".pem", ".key", ".p12", ".pfx")):
            ck.hit("AST01-secrets", "fail", path, None, "risky-filename", note="a file that normally holds a credential")


def check_metadata(skill_dir, recs, ck, fm_info):
    for cid, a, t in (("AST03-tools", "AST03", "Tool permissions are minimal and scoped"), ("AST04-frontmatter", "AST04", "Metadata is well formed and honest"),
                      ("AST04-description", "AST04", "The description is plain and matches the folder")):
        ck.add(cid, a, t)
    skill_md = next((r for r in recs if r["path"] == "SKILL.md"), None)
    if skill_md is None:
        ck.hit("AST04-frontmatter", "fail", "SKILL.md", None, "no-skill-md", note="the folder has no readable SKILL.md at its top level")
        return None
    fm, err = parse_frontmatter(skill_md["text"])
    if fm is None:
        ck.hit("AST04-frontmatter", "fail", "SKILL.md", 1, "bad-frontmatter", note=err)
        return None
    fm_info.update(fm)
    name, desc = fm.get("name", ""), fm.get("description", "")
    ck.items["AST04-frontmatter"]["examined"] = 1
    ck.items["AST04-description"]["examined"] = 1
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", name):
        ck.hit("AST04-frontmatter", "fail", "SKILL.md", 2, "bad-name", note="name must be 1-64 lowercase letters, digits and hyphens")
    elif name != Path(skill_dir).resolve().name and not Path(skill_dir).resolve().name.startswith(("tmp", "vet-")):
        ck.hit("AST04-frontmatter", "fail", "SKILL.md", 2, "name-folder-mismatch", note=f"name '{name}' differs from folder '{Path(skill_dir).resolve().name}'")
    if re.search(r"claude|anthropic", name):
        ck.hit("AST04-frontmatter", "fail", "SKILL.md", 2, "reserved-name", note="names containing claude or anthropic are reserved; this one imitates a vendor skill")
    if not desc:
        ck.hit("AST04-description", "fail", "SKILL.md", 3, "no-description", note="a skill without a description cannot be judged for what it triggers on")
    else:
        if len(desc) > 1500:
            ck.hit("AST04-description", "fail", "SKILL.md", 3, "description-too-long", note=f"{len(desc)} characters; long descriptions can hide trigger phrases")
        if "<" in desc or ">" in desc:
            ck.hit("AST04-description", "fail", "SKILL.md", 3, "markup-in-description", note="angle brackets in a description")
        if re.search(r"(?i)\b(?:always|every (?:message|request|task|turn)|any (?:message|request|task)|whenever the user says anything|all conversations)\b", desc):
            ck.hit("AST04-description", "manual", "SKILL.md", 3, "over-broad-trigger", note="the description makes the skill load on almost any request")
    unknown = sorted(set(fm) - KNOWN_FRONTMATTER)
    if unknown:
        ck.hit("AST04-frontmatter", "manual", "SKILL.md", 2, "unknown-frontmatter-key", note="keys this review does not understand: " + ", ".join(unknown))
    tools_raw = fm.get("allowed-tools", "")
    tools = [t.strip() for t in re.split(r",\s*(?![^()]*\))", tools_raw) if t.strip()]
    ck.items["AST03-tools"]["examined"] = 1
    if not tools_raw:
        ck.hit("AST03-tools", "manual", "SKILL.md", None, "no-allowed-tools", note="no tool list declared, so the skill inherits whatever the session allows; ask for an explicit minimal list")
    for t in tools:
        base = t.split("(")[0]
        if t in ("*", "all") or base == "*":
            ck.hit("AST03-tools", "fail", "SKILL.md", None, "wildcard-tools", note="allows every tool")
        elif base == "Bash" and "(" not in t:
            ck.hit("AST03-tools", "fail", "SKILL.md", None, "unscoped-bash", note="Bash without a command pattern allows any shell command")
        elif base == "Bash":
            ck.hit("AST03-tools", "manual", "SKILL.md", None, "scoped-bash", note=f"allows {t}; confirm the pattern is as narrow as the work needs")
        elif base.startswith("mcp__"):
            ck.hit("AST03-tools", "manual", "SKILL.md", None, "mcp-tool", note=f"uses connector tool {base}; this reaches the owner's apps")
        elif base in ("WebFetch", "WebSearch"):
            ck.hit("AST03-tools", "manual", "SKILL.md", None, "web-tool", note=f"{base} brings outside text into the session")
        elif base in ("Write", "Edit", "NotebookEdit", "MultiEdit"):
            ck.hit("AST03-tools", "manual", "SKILL.md", None, "write-tool", note=f"{base} changes files")
        elif base not in READONLY_TOOLS:
            ck.hit("AST03-tools", "manual", "SKILL.md", None, "unrecognised-tool", note=f"tool '{base}' is not one this review knows")
    return fm


def finish(skill_dir, recs, unread, symlinks, fm, ck, args, inventory_rows):
    # AST08 coverage, symlinks, executables
    for u in unread:
        sev = "fail" if u.get("kind") == "executable" else "manual"
        ck.hit("AST08-coverage", sev, u["path"], None, "file-not-read", note=u["reason"])
        if u.get("kind") == "executable":
            ck.hit("AST01-exec", "fail", u["path"], None, "compiled-or-executable-file", note="a file that cannot be read as source ships inside the skill")
    for s in symlinks:
        ck.hit("AST06-links", "fail", s, None, "symlink", note="a link can point outside the skill folder; not followed")
        ck.hit("AST08-coverage", "manual", s, None, "symlink-not-read", note="target not read")
    # drift and governance
    file_hashes = sorted((r["path"], r["sha256"]) for r in recs) + sorted((u["path"], u.get("sha256", "unread")) for u in unread)
    content = sha256("\n".join(f"{p}:{h}" for p, h in file_hashes).encode())
    ck.add("AST02-provenance", "AST02", "Source and pinned commit are recorded").update(examined=1)
    ck.add("AST07-pin", "AST07", "Pinned to a full commit SHA, with a content hash for re-review").update(examined=1)
    ck.add("AST07-drift", "AST07", "Unchanged since the last review").update(examined=1)
    ck.add("AST09-governance", "AST09", "Inventory entry is complete and approval stays with the owner").update(examined=1)
    host = urlparse(args.source).hostname if args.source else None
    if not args.source or not host or urlparse(args.source).scheme != "https":
        ck.hit("AST02-provenance", "fail", "(arguments)", None, "no-source", note="give the https URL of the repository the folder came from")
    elif host not in ("github.com", "gitlab.com", "codeberg.org", "bitbucket.org"):
        ck.hit("AST02-provenance", "manual", "(arguments)", None, "unusual-host", note=f"source host {host} is not a major code host")
    if not args.commit or not SHA40.match(args.commit):
        ck.hit("AST07-pin", "fail", "(arguments)", None, "no-pinned-sha", note="a full 40-character lowercase commit SHA is required; a branch or tag can move")
    lic = next((r["path"] for r in recs if Path(r["path"]).name.lower().startswith(("license", "copying", "notice"))), None)
    if not lic and not fm.get("license"):
        ck.hit("AST09-governance", "manual", "(folder)", None, "no-license", note="no LICENSE file or license key; reuse terms are unknown")
    for k in ("source", "commit", "reviewer"):
        if not getattr(args, k):
            ck.hit("AST09-governance", "fail", "(arguments)", None, f"missing-{k}", note=f"inventory entry needs --{k}")
    prev = [r for r in inventory_rows if r.get("name") == fm.get("name")]
    if prev:
        last = prev[-1]
        if last.get("content_sha256") and last["content_sha256"] != content:
            ck.hit("AST07-drift", "fail", "(inventory)", None, "content-changed", note=f"content hash differs from the reviewed entry ({last['content_sha256'][:12]}...); re-review everything")
        elif last.get("commit") and args.commit and last["commit"] != args.commit:
            ck.hit("AST07-drift", "fail", "(inventory)", None, "commit-changed", note="commit differs from the reviewed entry; re-review")
        else:
            ck.items["AST07-drift"]["evidence"].append({"file": "(inventory)", "rule": "matches-reviewed-entry", "result": "pass"})
    if args.installed_dir and fm.get("name"):
        d = Path(args.installed_dir) / fm["name"]
        if d.exists() and d.resolve() != Path(args.skill_dir).resolve():
            ck.add("AST04-shadowing", "AST04", "Name does not shadow an installed skill").update(examined=1)
            ck.hit("AST04-shadowing", "fail", str(d), None, "name-collision", note="a skill with this name is already installed; installing would replace or shadow it")
    ck.items["AST06-links"]["examined"] = len(recs)
    return content


def load_inventory(path):
    rows = []
    if path and Path(path).exists():
        for l in Path(path).read_text(encoding="utf-8").splitlines():
            cells = [c.strip().strip("`") for c in l.strip().strip("|").split("|")]
            if l.strip().startswith("|") and len(cells) >= 8 and re.fullmatch(r"[a-z0-9-]+", cells[0]) and cells[0] != "skill":
                rows.append({"name": cells[0], "source": cells[1], "commit": cells[2], "content_sha256": cells[3]})
    return rows


def vet(args):
    root = Path(args.skill_dir)
    if not root.is_dir():
        raise OSError("not a directory")
    files, unread, symlinks = enumerate_files(str(root))
    recs = read_all(files, unread)
    ck = Checks()
    run_rules(recs, ck)
    fm_info = {}
    check_metadata(args.skill_dir, recs, ck, fm_info)
    content = finish(args.skill_dir, recs, unread, symlinks, fm_info, ck, args, load_inventory(args.inventory))
    for rec in recs:
        ck.items["AST08-coverage"]["examined"] = len(recs)
    # AST08: the scanner is not the judge
    ck.add("AST08-scanner-limits", "AST08", "An automated pass is not an approval").update(examined=1)
    ck.hit("AST08-scanner-limits", "manual", "(this tool)", None, "pattern-scan-only", note="this review matches patterns; it cannot see logic that avoids them. A person reads every file before the owner decides")

    by_ast = {}
    for c in ck.items.values():
        a = by_ast.setdefault(c["ast"], {"title": AST_TITLES[c["ast"]], "result": "pass", "checks": []})
        if SEV[c["result"]] > SEV[a["result"]]:
            a["result"] = c["result"]
        if c["result"] == "pass" and not c["evidence"]:
            c["evidence"] = [{"file": f"{c['examined']} item(s) examined", "rule": "no match", "result": "pass"}]
        c.pop("rules_clear", None)
        a["checks"].append(c)
    for a in by_ast.values():
        a["checks"].sort(key=lambda c: c["id"])
    by_ast = {k: by_ast[k] for k in sorted(by_ast)}
    missing = [a for a in AST_TITLES if a not in by_ast]
    assert not missing, f"AST items without a check: {missing}"
    worst = max((SEV[a["result"]] for a in by_ast.values()), default=0)
    verdict = "reject" if worst == 2 else "needs-manual-review"
    manual_n = sum(1 for a in by_ast.values() for c in a["checks"] if c["result"] == "manual" and c["id"] != "AST08-scanner-limits")
    automated = "findings" if worst == 2 else ("manual-items" if (manual_n or unread or symlinks) else "no-findings")
    reasons = [f"{c['id']}: " + (c["evidence"][0].get("note") or c["evidence"][0]["rule"]) for a in by_ast.values() for c in a["checks"] if c["result"] == "fail"]
    reviewed = args.reviewed_at or date.today().isoformat()
    name = fm_info.get("name") or Path(args.skill_dir).resolve().name
    entry = {"skill": name, "source": args.source, "commit": args.commit, "content_sha256": content, "license": fm_info.get("license") or ("file" if next((r for r in recs if Path(r["path"]).name.lower().startswith(("license", "copying"))), None) else "unknown"),
             "files_read": len(recs), "files_unread": len(unread), "reviewed_by": f"{args.reviewer or 'unassigned'} (proposal)", "reviewed_at": reviewed,
             "verdict": verdict, "decision": "pending owner", "approved_by": None, "re_review_by": (date.fromisoformat(reviewed) + timedelta(days=90)).isoformat()}
    cells = [entry["skill"], entry["source"] or "-", entry["commit"] or "-", entry["content_sha256"], entry["license"], entry["reviewed_by"], entry["reviewed_at"], f"{verdict}; pending owner"]
    return {"tool": f"skill-vetting/vet_skill.py {VERSION}", "skill_name": name, "skill_path": str(root), "verdict": verdict, "automated_result": automated, "approved": False,
            "approval": "only the owner approves, in writing, after a person has read every file; this report is not an approval",
            "reasons": reasons, "by_ast": by_ast,
            "files_read": [{k: r[k] for k in ("path", "sha256", "bytes", "lines")} for r in recs],
            "unread": [{k: u[k] for k in ("path", "reason") if k in u} for u in unread], "symlinks_not_followed": symlinks,
            "executed_anything": False, "content_sha256": content, "frontmatter_keys": sorted(fm_info),
            "inventory_entry": entry, "inventory_row": "| " + " | ".join(f"`{c}`" if i in (2, 3) and c != "-" else c for i, c in enumerate(cells)) + " |"}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("skill_dir")
    ap.add_argument("--source")
    ap.add_argument("--commit")
    ap.add_argument("--reviewer")
    ap.add_argument("--reviewed-at")
    ap.add_argument("--installed-dir")
    ap.add_argument("--inventory")
    a = ap.parse_args()
    try:
        res = vet(a)
    except (OSError, ValueError) as e:
        print(json.dumps({"status": "error", "error": e.__class__.__name__, "detail": str(e)[:100]}))
        sys.exit(2)
    print(json.dumps(res, indent=2, ensure_ascii=True))
    sys.exit(1 if res["verdict"] == "reject" else 0)


if __name__ == "__main__":
    main()
