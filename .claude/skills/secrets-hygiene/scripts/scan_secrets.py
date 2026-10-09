#!/usr/bin/env python3
"""secrets-hygiene scanner. Finds secret-like values and risky files. Standard library only.

It READS text to find patterns, but it never prints, stores or sends a secret value:
a finding carries only the rule id, the file, the line number and the length of the match.

Usage:
  scan_secrets.py --paths FILE_OR_DIR [...]    scan files and directories (skips .git, binaries, files over 2 MB)
  scan_secrets.py --staged                     scan what is staged in the git repo in the current directory
  scan_secrets.py --diff [FILE]                scan a unified diff (stdin if no FILE); only added lines count
  scan_secrets.py --text [FILE]                scan a plan or any text (stdin if no FILE); also flags plans that
                                               tell someone to paste, store or commit a secret
Output: JSON on stdout. Exit 0 when clean, 1 when there are findings, 2 on a usage error.
A line may carry the marker `secrets-hygiene:ignore` to suppress a finding; suppressed items are still listed.

The patterns are heuristics based on widely documented token prefixes. They are not exhaustive. GitHub secret
scanning and push protection are the primary layer; this script is a second one that also runs offline and in hooks.
"""
import argparse
import json
import math
import re
import subprocess
import sys

sys.dont_write_bytecode = True  # a vetted or scanned folder must not gain compiled files from our own run
from pathlib import Path

MAX_BYTES = 2_000_000
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv"}

# (rule id, severity, regex). No literal secrets live here, only patterns.
TOKEN_RULES = [
    ("private-key-block", "high", r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY(?: BLOCK)?-----"),
    ("aws-access-key-id", "high", r"\b(?:AKIA|ASIA|AGPA|AIDA|AROA)[0-9A-Z]{16}\b"),
    ("github-token", "high", r"\bgh[pousr]_[A-Za-z0-9]{36,255}\b"),
    ("github-fine-grained-token", "high", r"\bgithub_pat_[A-Za-z0-9_]{22,255}\b"),
    ("slack-token", "high", r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"),
    ("stripe-key", "high", r"\b[rs]k_(?:live|test)_[A-Za-z0-9]{16,}\b"),
    ("anthropic-key", "high", r"\bsk-ant-[A-Za-z0-9_-]{20,}\b"),
    ("openai-style-key", "high", r"\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}\b"),
    ("google-api-key", "high", r"\bAIza[0-9A-Za-z_-]{35}\b"),
    ("square-token", "high", r"\b(?:sq0atp-|sq0csp-)[A-Za-z0-9_-]{22,}\b|\bEAAA[A-Za-z0-9_-]{40,}\b"),
    ("meta-or-threads-token", "high", r"\b(?:THAA|IGAA|EAA)[A-Za-z0-9_-]{50,}\b"),
    ("jwt", "medium", r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    ("url-with-password", "high", r"\bhttps?://[^/\s:@]{1,64}:[^/\s:@]{3,}@[^\s/]+"),
]
TOKEN_RULES = [(r, s, re.compile(p)) for r, s, p in TOKEN_RULES]

ASSIGN = re.compile(
    r"""(?ix)\b[\w.-]*(?:api[_-]?key|secret|token|passwd|password|pwd|auth[_-]?key|private[_-]?key|access[_-]?key)[\w.-]*
        ["']?\s*[:=]\s*["']?(?P<val>[A-Za-z0-9/+_\-.=]{16,})["']?""")
PLACEHOLDER = re.compile(r"(?i)example|changeme|placeholder|your[_-]|xxxx|dummy|sample|fake|test[_-]?value|redacted|<|\{\{|\*\*\*|^\$")
ENV_NAME = re.compile(r"^[A-Z0-9]+(?:_[A-Z0-9]+)+$")

PLAN_RULE = re.compile(
    r"\b(?P<verb>paste|type|enter|store|save|put|write|commit|echo|export|hard-?code|embed|include|send|share|upload)\b"
    r".{0,40}\b(?P<noun>api[ _-]?keys?|tokens?|passwords?|passphrases?|secrets?|credentials?|private keys?)\b", re.I)

RISKY_NAMES = [
    (re.compile(r"^\.env(?!\.(?:example|sample|template)$)(?:\..+)?$"), "env file"),
    (re.compile(r"\.(?:pem|key|p12|pfx|keystore|jks)$"), "key or certificate file"),
    (re.compile(r"^id_(?:rsa|dsa|ecdsa|ed25519)$"), "ssh private key"),
    (re.compile(r"^(?:\.netrc|\.npmrc|\.pypirc|credentials\.json|service-account.*\.json)$"), "credentials file"),
]

STEPS = {
    "secret-in-file": [
        "1. Treat the value as exposed. Do not paste it anywhere, including this chat.",
        "2. Open the provider's own settings page (for example GitHub, Square, Meta or the supplier) and revoke or rotate the credential there. Do this first.",
        "3. Put the new value only in your password manager. For a value a GitHub Action needs, add it in the repository: Settings, Secrets and variables, Actions, New repository secret. Never put it in a file in the repository.",
        "4. Replace the value in the file with a reference to an environment variable or a GitHub secret, then commit the fix.",
        "5. If the value was ever pushed, rotating it (step 2) is what makes it safe. Removing it from git history is a separate, destructive step (class R3) that needs its own Preflight Brief.",
    ],
    "plan-handles-secret": [
        "1. Agents never type, store or paste secrets, so this step of the plan must be done by the owner.",
        "2. Ask the owner to create or rotate the credential at the provider's own page and keep it in the password manager.",
        "3. If a GitHub Action needs it, the owner adds it under Settings, Secrets and variables, Actions, New repository secret.",
        "4. The agent then uses the secret by its name only (for example an environment variable or a secrets reference), never by value.",
    ],
    "risky-filename": [
        "1. Do not commit this file. Remove it from the staged changes (git restore --staged on the path).",
        "2. Keep the real file outside the repository, or in a secrets store. Commit only a template with placeholders, such as .env.example.",
        "3. If it was already pushed, treat every value in it as exposed and follow the 'secret-in-file' steps.",
    ],
}
RULE_TO_STEPS = {"plan-handles-secret": "plan-handles-secret", "risky-filename": "risky-filename"}


def entropy(s):
    if not s:
        return 0.0
    freq = {c: s.count(c) for c in set(s)}
    return -sum(n / len(s) * math.log2(n / len(s)) for n in freq.values())


def _line_findings(line, lineno, source, include_plan_rules):
    out = []
    spans = []
    for rule, sev, rx in TOKEN_RULES:
        for m in rx.finditer(line):
            if any(m.start() < e and s < m.end() for s, e in spans):
                continue  # one finding per span; first matching rule wins
            spans.append((m.start(), m.end()))
            out.append({"source": source, "line": lineno, "rule": rule, "severity": sev, "length": m.end() - m.start()})
    for m in ASSIGN.finditer(line):
        val = m.group("val")
        if any(m.start("val") < e and s < m.end("val") for s, e in spans):
            continue
        if PLACEHOLDER.search(val) or ENV_NAME.match(val) or entropy(val) < 3.5:
            continue
        out.append({"source": source, "line": lineno, "rule": "generic-secret-assignment", "severity": "medium", "length": len(val)})
    if include_plan_rules and PLAN_RULE.search(line):
        out.append({"source": source, "line": lineno, "rule": "plan-handles-secret", "severity": "medium", "length": 0})
    return out


def scan_text(text, source="<text>", include_plan_rules=False, first_line=1):
    """Return findings for a block of text. Values are never included."""
    findings = []
    for i, line in enumerate(text.splitlines(), first_line):
        found = _line_findings(line, i, source, include_plan_rules)
        if found and "secrets-hygiene:ignore" in line:
            for f in found:
                f["suppressed"] = True
        findings += found
    return findings


def _risky_name(path):
    for rx, label in RISKY_NAMES:
        if rx.search(Path(path).name):
            return label
    return None


def scan_file(path):
    p = Path(path)
    label = _risky_name(p)
    findings = []
    if label:
        findings.append({"source": str(path), "line": 0, "rule": "risky-filename", "severity": "medium", "length": 0, "detail": label})
    try:
        if p.stat().st_size > MAX_BYTES:
            return findings, "too large"
        data = p.read_bytes()
    except OSError as e:
        return findings, f"unreadable: {e.__class__.__name__}"
    if b"\x00" in data[:8192]:
        return findings, "binary"
    findings += scan_text(data.decode("utf-8", errors="replace"), str(path))
    return findings, None


def iter_files(paths):
    for raw in paths:
        p = Path(raw)
        if p.is_file():
            yield p
        elif p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.is_file() and not any(part in SKIP_DIRS for part in f.relative_to(p).parts):
                    yield f


def scan_paths(paths):
    findings, skipped, n = [], [], 0
    for f in iter_files(paths):
        got, skip = scan_file(f)
        findings += got
        n += 1
        if skip:
            skipped.append({"source": str(f), "reason": skip})
    return findings, skipped, n


def scan_diff(diff_text):
    """Scan only the added lines of a unified diff. A new risky file name counts too."""
    findings, source, lineno = [], "<diff>", 0
    for line in diff_text.splitlines():
        if line.startswith("+++ "):
            source = line[4:].strip()
            source = source[2:] if source.startswith("b/") else source
            if source != "/dev/null":
                label = _risky_name(source)
                if label:
                    findings.append({"source": source, "line": 0, "rule": "risky-filename", "severity": "medium", "length": 0, "detail": label})
        elif line.startswith("@@"):
            m = re.search(r"\+(\d+)", line)
            lineno = int(m.group(1)) - 1 if m else 0
        elif line.startswith("+") and not line.startswith("+++"):
            lineno += 1
            findings += scan_text(line[1:], source, first_line=lineno)
        elif not line.startswith("-"):
            lineno += 1
    return findings


def report(findings, skipped=None, files=None):
    live = [f for f in findings if not f.get("suppressed")]
    supp = [f for f in findings if f.get("suppressed")]
    kinds = []
    for f in live:
        k = RULE_TO_STEPS.get(f["rule"], "secret-in-file")
        if k not in kinds:
            kinds.append(k)
    out = {"status": "findings" if live else "clean", "action_class_if_acted_on": "R5" if live else "R0",
           "findings": live, "suppressed": supp, "skipped": skipped or [],
           "owner_instructions": {k: STEPS[k] for k in kinds},
           "note": "No secret value is included in this report, by design."}
    if files is not None:
        out["files_scanned"] = files
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--paths", nargs="+")
    g.add_argument("--staged", action="store_true")
    g.add_argument("--diff", nargs="?", const="-")
    g.add_argument("--text", nargs="?", const="-")
    args = ap.parse_args()
    skipped, files = None, None
    if args.paths:
        findings, skipped, files = scan_paths(args.paths)
    elif args.staged:
        p = subprocess.run(["git", "diff", "--cached", "-U0", "--no-color"], capture_output=True, text=True)
        if p.returncode != 0:
            print(json.dumps({"status": "error", "error": "git diff --cached failed"}))
            sys.exit(2)
        findings = scan_diff(p.stdout)
    elif args.diff:
        findings = scan_diff(sys.stdin.read() if args.diff == "-" else Path(args.diff).read_text(encoding="utf-8"))
    else:
        text = sys.stdin.read() if args.text == "-" else Path(args.text).read_text(encoding="utf-8")
        findings = scan_text(text, "<plan>", include_plan_rules=True)
    res = report(findings, skipped, files)
    print(json.dumps(res, indent=2))
    sys.exit(1 if res["status"] == "findings" else 0)


if __name__ == "__main__":
    main()
